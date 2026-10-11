import re
import os
import csv
import time
import requests

CURRENT_FILE = os.path.abspath(__file__)
APP_DIR = os.path.abspath(os.path.join(CURRENT_FILE, "..", "..", ".."))

print(f"[DEBUG PATH] APP_DIR wskazuje na: {APP_DIR}")

from io import BytesIO
from bs4 import BeautifulSoup
from pydantic import ValidationError
from fake_useragent import UserAgent
from app.schemas.schemas import ScrapedOffer
from PIL import Image as PILImage, UnidentifiedImageError
from app.static.datasets.series_aliases import SERIES_ALIASES
from app.models import db, Character, Series, Offer, Figure, Image



ua=UserAgent()
headers = {'User-Agent': ua.random}

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

def process_scraped_data(raw_data):
    if not raw_data:
        return

    if not raw_data.get("ch_name"):
        raw_data["error_reason"]="No character name"
        save_failures_to_csv(raw_data)
        return

    try:
        valid_offer = ScrapedOffer.model_validate(raw_data)
        save_to_mysql(valid_offer)
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

    # secondly, lets add the series
    # if no series in results, the character is "Original Character / Unknown"
    title=data.series_title.strip() if data.series_title else "Original Character / Unknown"
    title_lower=title.lower()
    # run the title in the aliases
    if title_lower in SERIES_ALIASES:
        title=SERIES_ALIASES[title_lower]
    # check if the series exists
    series=db.session.query(Series).filter_by(title=title).first()
    if not series:
        # if not, add one by taking the title
        series=Series(title=title)
        db.session.add(series)
        db.session.flush()


    # now character logic
    # get all characters named like the one we are adding
    existing_chars=db.session.query(Character).filter_by(name=data.ch_name).all()
    char=None
    if not existing_chars:
        # if no one is named like this, add a new character
        char=Character(name=data.ch_name, S_ID=series.S_ID)
        db.session.add(char)
        db.session.flush()
    else:
        # match the series
        for c in existing_chars:
            if c.S_ID==series.S_ID:
                char=c
                break

        if not char:
            # get the "Original Character / Unknown" id
            unknown_series = db.session.query(Series).filter_by(title="Original Character / Unknown").first()
            unknown_s_id=unknown_series.S_ID if unknown_series else None

            # if the scraped series is Unknown, and the character appears only in one series
            # then assign it to the only series it is currently in
            if series.title == "Original Character / Unknown" and len(existing_chars)==1:
                char=existing_chars[0]
            # if the character previously figured as an unknown series,
            # and currently scraped series isnt unknown
            elif unknown_s_id and series.title != "Original Character / Unknown":
                # reassign all those from Unknown to currently scraped series
                char_in_unknown=next((c for c in existing_chars if c.S_ID==unknown_s_id), None)
                if char_in_unknown:
                    char=char_in_unknown
                    char.S_ID=series.S_ID

            # if the character is new, simply add it
            if not char:
                char=Character(name=data.ch_name, S_ID=series.S_ID)
                db.session.add(char)
                db.session.flush()

    # now lets check the figs
    fig = None
    if data.code:
        # first lookup the code - it should be unique between figures
        fig=db.session.query(Figure).filter_by(code=data.code).first()
    if not fig:
        # then search for the name match
        fig=db.session.query(Figure).filter_by(name=data.fig_name).first()

    if not fig:
        # if we still haven't found anything, the fig is most likely new. lest add it
        fig=Figure(name=data.fig_name, C_ID=char.C_ID, code=data.code, manufacturer=data.manufacturer, scale=data.scale)
        db.session.add(fig)
        db.session.flush()

    # lastly, the offer must also be new
    new_offer=Offer(F_ID=fig.F_ID, link=offer_link, store=data.store, price=data.price, status=data.status)
    db.session.add(new_offer)
    db.session.flush()
    # process all of the images
    process_offer_images(new_offer.O_ID, data.imgs)

    db.session.commit()
    print(f"Saved offer")


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
        local_filename=f"{o_id}_{count}.jpg"
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
                img.save(local_path, "JPEG", quality=90)
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

def get_name_from_cache(fig_name: str, series_title=""):
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