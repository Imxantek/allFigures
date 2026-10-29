import re
import os
import csv
import time
import requests
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from sympy.plotting.textplot import is_valid

from services.Image_comparator import compare, compare_prepared, prepare_image

CURRENT_FILE = os.path.abspath(__file__)
SCRAPES_DIR = os.path.dirname(CURRENT_FILE)
ALLFIGURES_DIR = os.path.dirname(SCRAPES_DIR)
SRC_DIR = os.path.dirname(ALLFIGURES_DIR)
APP_DIR = os.path.dirname(SRC_DIR)

from io import BytesIO
from bs4 import BeautifulSoup
from pydantic import ValidationError
from fake_useragent import UserAgent
from schemas.schemas import ScrapedOffer
from PIL import Image as PILImage, UnidentifiedImageError
from models.models import db, Character, Series, Offer, Figure, Image, SeriesAlias, CharacterAlias

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.google.com/"
}

# cache structure:
# key (lowercase) -> value: (normal name, series set)
# {"chinatsu kano" : ("Chinatsu Kano", {Blue Box})
KNOWN_CHARACTERS_CACHE: dict[str, tuple[str, set[str]]] = {}

def init_cache_from_db():
    # get all of the figs and series, and add them to the cache
    query=db.session.query(Character.name, Series.title)\
        .join(Series, Character.S_ID == Series.S_ID)\
        .all()

    for char_name, series_title in query:
        add_to_cache(char_name, series_title)

    query_series_alias=db.session.query(Character.name, SeriesAlias.alias) \
        .join(Series, Character.S_ID == Series.S_ID) \
        .join(SeriesAlias, SeriesAlias.S_ID == Series.S_ID) \
        .all()
    for char_name, series_alias in query_series_alias:
        add_to_cache(char_name, series_alias)

    query_char_alias=db.session.query(Character.name, CharacterAlias.alias)\
        .join(CharacterAlias, Character.C_ID==CharacterAlias.C_ID)\
        .all()
    for char_name, char_alias in query_char_alias:
        add_char_alias_to_cache(char_name, char_alias)

    print(f"Loaded {len(KNOWN_CHARACTERS_CACHE)} characters from the db")



def add_to_cache(name: str, series_title: str):
    if not name:
        return

    lower_name=name.lower()
    if lower_name not in KNOWN_CHARACTERS_CACHE:
        # create a set of series, that have a such a character
        # for example, Thor can appear both in Marvel and God of War
        KNOWN_CHARACTERS_CACHE[lower_name]=(name, set())

    if series_title:
        KNOWN_CHARACTERS_CACHE[lower_name][1].add(series_title.lower())

def add_char_alias_to_cache(char_name: str, char_alias: str):
    if not char_name or not char_alias:
        return

    lower_char_name=char_name.strip().lower()
    lower_char_alias=char_alias.strip().lower()

    if lower_char_name not in KNOWN_CHARACTERS_CACHE:
        KNOWN_CHARACTERS_CACHE[lower_char_name] = (char_name.strip(), set())

    name, series_set=KNOWN_CHARACTERS_CACHE[lower_char_name]

    if lower_char_alias not in KNOWN_CHARACTERS_CACHE:
        KNOWN_CHARACTERS_CACHE[lower_char_alias] = (char_name.strip(), series_set)
    else:
        KNOWN_CHARACTERS_CACHE[lower_char_alias][1].update(series_set)


def process_scraped_data(raw_data):
    if not raw_data:
        return

    if not raw_data.get("ch_name"):
        raw_data["error_reason"]="No character name"
        save_failures_to_csv(raw_data)
        return

    try:
        valid_offer = ScrapedOffer.model_validate(raw_data)
        try:
            save_to_mysql(valid_offer)
        except:
            db.session.rollback()
            print("Error saving offer")
    except ValidationError:
        raw_data["error_reason"]="Pydantic data validation error"
        save_failures_to_csv(raw_data)


def save_to_mysql(data: ScrapedOffer):
    # first, check if such offer already exists
    offer_link = str(data.link)
    offer = db.session.query(Offer).filter_by(link=offer_link).first()
    if offer:
        # update price, status, and check if any new images appeared
        offer.price = data.price
        offer.status = data.status
        process_offer_images(offer.O_ID, data.imgs)
        db.session.commit()
        return

    # if not lets check the code - if a figure with such code already exists
    # then the only thing we need to do is to create a new offer for this figure
    clean_scraped_series = data.series_title.strip() if data.series_title else ""
    clean_scraped_character = data.ch_name.strip() if data.ch_name else ""
    if data.code:
        # search for a code in db
        code_query=db.session.query(Figure).filter_by(code=data.code).first()
        if code_query:


            db_char=code_query.character
            db_series=db_char.series if db_char else None
            # if found anything, and the title doesnt add up
            # create a new alias for this series
            if (db_series
                and clean_scraped_series
                and clean_scraped_series.lower() != db_series.title.lower()
                and db_series.title.lower() != "original character / unknown"
                and clean_scraped_series.lower() != "original character / unknown"
            ):
                existing_alias=db.session.query(SeriesAlias)\
                    .filter(func.lower(SeriesAlias.alias) == clean_scraped_series.lower())\
                    .first()
                if not existing_alias:
                    alias=SeriesAlias(alias=clean_scraped_series, S_ID=db_series.S_ID)
                    db.session.add(alias)
                    add_to_cache(db_char.name, clean_scraped_series)
            # then, do the same for name aliases

            if (db_char
                and clean_scraped_character
                # this here below removes all the cases of aliases with just different ordering
                # this case is already solved by the sliding window logic
                and set(clean_scraped_character.lower().split())!=set(db_char.name.lower().split())
                and clean_scraped_character.lower()!=clean_scraped_series.lower()
                and clean_scraped_character.lower() != "original character"
                and (not db_series or clean_scraped_character.lower() != db_series.title.lower())
            ):
                db_chars_from_series=db.session.query(Character).filter(Character.S_ID == db_series.S_ID).all()
                is_safe_to_add=True
                for c in db_chars_from_series:
                    if set(clean_scraped_character.lower().split())==set(c.name.lower().split()):
                        is_safe_to_add=False
                        break
                if is_safe_to_add:
                    existing_char_alias=db.session.query(CharacterAlias)\
                            .filter(func.lower(CharacterAlias.alias) == clean_scraped_character.lower())\
                            .first()
                    if not existing_char_alias:
                        alias=CharacterAlias(alias=clean_scraped_character, C_ID=db_char.C_ID)
                        db.session.add(alias)
                        add_char_alias_to_cache(db_char.name, clean_scraped_character)
            # lastly, create a new offer
            offer=Offer(F_ID=code_query.F_ID,
                            link=offer_link,
                            store=data.store,
                            price=data.price,
                            status=data.status)
            db.session.add(offer)
            db.session.flush()
            process_offer_images(offer.O_ID, data.imgs)
            db.session.commit()
            return

    # secondly, lets add the series
    # if no series in results, the character is "Original Character / Unknown"
    title=data.series_title.strip() if data.series_title else "Original Character / Unknown"
    title_lower=title.lower()
    # check if the series exists
    series=db.session.query(Series).filter_by(title=title).first()
    if not series:
        # run the query in SeriesAliases table
        alias = db.session.query(SeriesAlias)\
            .options(joinedload(SeriesAlias.series))\
            .filter(func.lower(SeriesAlias.alias) == title_lower)\
            .first()
        if alias:
            series=alias.series
        else:
            # if not, add one by taking the title
            series=Series(title=title)
            db.session.add(series)
            db.session.flush()


    # now character logic
    # get all characters named like the one we are adding
    # and also coming from the same series we are adding
    char=db.session.query(Character)\
        .filter(Character.S_ID == series.S_ID,
            func.lower(Character.name) == clean_scraped_character.lower())\
        .first()
    # flag for image comparison logic
    created_new=False
    if not char:
        # if we still havent found any characters,
        # we must search the aliases table
        # load all of the aliases and characters connected with them
        # if the character has the same C_ID as the alias
        # and the characters series is the one we just scrapped
        # and the alias already exists in the table
        # then the character connected to this alias can be set as the current character
        char_alias_match=db.session.query(CharacterAlias)\
        .options(joinedload(CharacterAlias.character))\
        .join(Character, CharacterAlias.C_ID==Character.C_ID)\
        .filter(
            Character.S_ID==series.S_ID,
            func.lower(CharacterAlias.alias) == clean_scraped_character.lower()
        ).first()
        if char_alias_match:
            char=char_alias_match.character
        else:
            # if no one is named like this, add a new character
            created_new=True
            char=Character(name=clean_scraped_character, S_ID=series.S_ID, is_valid=False)
            add_to_cache(char.name, series.title)
            db.session.add(char)
            db.session.flush()


    # now lets check the figs
    # if we have a character, and it wasn't created just yet,
    # then there is a chance that the figure already exists in the db
    if not created_new and data.imgs:
        imgs=db.session.query(Figure.F_ID, Image.path)\
            .select_from(Image)\
            .join(Offer, Image.O_ID==Offer.O_ID)\
            .join(Figure, Offer.F_ID==Figure.F_ID)\
            .filter(Figure.C_ID==char.C_ID)\
            .all()
        if imgs:
            # scrapped image
            temp_path=os.path.join(APP_DIR, "static", "images", "figures", "TEMP.png")
            for scr_img in list(data.imgs)[:3]:
                temp_img=download_figure_image(scr_img, "TEMP.png")
                if not temp_img:
                    continue

                img1, mask1 = prepare_image(temp_path)
                if img1 is None or mask1 is None:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    continue
                rejected_figs=set()

                for db_img in imgs:
                    if db_img.F_ID in rejected_figs:
                        continue
                    db_path=os.path.join(APP_DIR, "static", db_img.path)
                    print(f"comparing: {temp_img} -> {db_path}" )
                    # calculate the visual comparison score
                    is_match, is_fig_rejected =compare_prepared(img1, mask1, db_path)
                    # if the score is good enough, we know the figures are the same
                    # So we can create a new offer under the same F_ID
                    if is_fig_rejected:
                        print("score too low! rejecting...")
                        rejected_figs.add(db_img.F_ID)
                        continue
                    if is_match:
                        matched_fig = db.session.query(Figure).filter_by(F_ID=db_img.F_ID).first()
                        if matched_fig and not matched_fig.code and data.code:
                            matched_fig.code = data.code

                        offer = Offer(
                            F_ID=db_img.F_ID,
                            link=offer_link,
                            store=data.store,
                            price=data.price,
                            status=data.status
                        )
                        db.session.add(offer)
                        db.session.flush()
                        process_offer_images(offer.O_ID, data.imgs)
                        db.session.commit()
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                        return
                if os.path.exists(temp_path):
                    os.remove(temp_path)





    fig=None
    # search for the name match
    if not fig:
        fig=db.session.query(Figure).filter(func.lower(Figure.name)==data.fig_name.lower()).first()
        if fig and not fig.code and data.code:
            fig.code = data.code

    if not fig:
        # if we still haven't found anything, the fig is most likely new. lest add it
        fig=Figure(name=data.fig_name,
                   C_ID=char.C_ID,
                   code=data.code,
                   manufacturer=data.manufacturer,
                   scale=data.scale
                   )
        db.session.add(fig)
        db.session.flush()

    # lastly, the offer must also be new
    new_offer=Offer(F_ID=fig.F_ID,
                    link=offer_link,
                    store=data.store,
                    price=data.price,
                    status=data.status)
    db.session.add(new_offer)
    db.session.flush()

    # uncomment when done testing
    # process all of the images
    process_offer_images(new_offer.O_ID, data.imgs)
    db.session.commit()
    # db.session.rollback()
    print(f"Saved offer")
    temp_clean_path = os.path.join(APP_DIR, "static", "images", "figures", "TEMP.png")
    if os.path.exists(temp_clean_path):
        os.remove(temp_clean_path)


def process_offer_images(o_id, img_links):
    if not img_links:
        return

    # get all currently existing images
    existing_images=db.session.query(Image).filter_by(O_ID=o_id).all()

    existing_urls={img.link for img in existing_images if hasattr(img, "link")}
    # count them for naming purposes
    count=len(existing_urls)

    for img_link in img_links:
        # if the link already appears in the db, then the photo has already been added
        if img_link in existing_urls:
            continue

        # increase the counter, so the names wont be the same
        count+=1
        local_filename=f"{o_id}_{count}.png"
        # run the downloader function
        path=download_figure_image(img_link, local_filename)

        # add the image path to the db
        if path:
            image=Image(O_ID=o_id, path=path, link=img_link)
            db.session.add(image)
    db.session.flush()



def download_figure_image(img_url, local_filename):
    target_dir = os.path.join(APP_DIR, "static", "images", "figures")
    os.makedirs(target_dir, exist_ok=True)
    local_path = os.path.join(target_dir, local_filename)

    try:
        response = requests.get(img_url, headers=headers, timeout=60)

        if response.ok:
            try:
                img=PILImage.open(BytesIO(response.content))
                img=img.convert("RGB")
                img.save(local_path, "PNG", quality=90)
                print(f"Downloaded img {local_filename}")
                return f"images/figures/{local_filename}"
            except UnidentifiedImageError:
                print(f"Failed to download {img_url}")
                return None
        else:
            print(f"Failed to download {img_url}")
            return None
    except requests.RequestException as e:
        print(f"Failed to download {img_url}")
        return None


def get_name_from_mfc(code):
    # lookup mfc for with the JAN code
    url = f"https://myfigurecollection.net/browse.v4.php?barcode={code}"
    time.sleep(1)

    resp = requests.get(url, headers=headers, timeout=60)
    if not resp.ok:
        print("response not ok!")
        print(f"error while assessing {code}")
        return "", ""


    if "/item/" not in resp.url:
        print("no such code or invalid code")
        return "", ""
    soup=BeautifulSoup(resp.content,"html.parser")


    char=""
    char_label = soup.find("div", class_="data-label", string=re.compile("Character"))
    if char_label:
        char_value=char_label.find_next_sibling("div", class_="data-value")
        if char_value:
            char_tag=char_value.find("a")
            if char_tag:
                char=char_tag.text.strip()
    if char:
        print("found character name on MFC!")
    scale=""
    scale_tag=soup.find("a", class_="item-scale")
    if scale_tag:
        scale=scale_tag.text.strip()
    return char, scale

def get_name_from_cache(fig_name: str, series_title:str =""):
    fallback_name = None
    series_lower = series_title.lower() if series_title else ""

    clean_fig_name=re.sub(r"[^a-zA-Z0-9\s]", " ", fig_name)
    words=clean_fig_name.split()
    max_words=len(words)

    # sliding window logic
    # start with the largest size
    for n in range(max_words, 0, -1):
        # then, gradually strat closing the window
        for i in range(max_words-n+1):
            # merge n words together in lowercase
            phrase=" ".join(words[i:i+n]).lower()

            matched_data=KNOWN_CHARACTERS_CACHE.get(phrase)

            # inverted logic (for japanese names)
            # f.e. Kamado Tanjiro = Tanjiro Kamado
            if not matched_data and n==2:
                inverted = f"{words[i + 1]} {words[i]}".lower()
                matched_data = KNOWN_CHARACTERS_CACHE.get(inverted)

            if matched_data:
                # get all series we know for this character name
                matched_char, known_series=matched_data

                if series_lower and series_lower != "original character / unknown":
                    if series_lower not in known_series and "original character / unknown" not in known_series:
                        # the series didnt match, so we keep on checking
                        continue

                # fallback logic. check yatta_scraper.py extract logic for explanation
                if series_lower and (matched_char.lower() in series_lower or series_lower in matched_char.lower()):
                    if not fallback_name:
                        fallback_name = matched_char
                    continue

                return matched_char, False

    return fallback_name, True



def save_failures_to_csv(failed_offer: dict, filename="rejects.csv"):
    with open(filename, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(failed_offer.values())