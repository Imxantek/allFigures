import re
import time
import requests
from ddgs import DDGS
from ddgs.exceptions import DDGSException
from pymysql import IntegrityError
from requests import RequestException
from thefuzz import fuzz
from app.models import StatusEnum, StoreEnum, db, Character, Series, Offer, Figure, Image
from scrapers.dystrykt_scraper import extract
from backend.run import app
from Image_comparator import compare
from services.scrapers.scraper_functions import process_offer_images
from static.datasets.domain_noise import DOMAIN_NOISE
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.google.com/"
}

def get_links(search:str):
    results=[]
    for i in range(10):
        print(f"Try No. {i}")
        try:
            with DDGS() as ddgs:
                print("Extracting...")
                raw_res=list(ddgs.text(search, max_results=3))
                if raw_res:
                    print("Success!!")
                    results = [res["href"] for res in raw_res if re.search(r"myfigurecollection\.\w+/item/\d+$", res["href"]) or ("https://www.dystryktzero.pl" in res["href"] and res["href"].endswith(".html"))]
        except DDGSException:
            print(f"Failed, retrying...")
            time.sleep(3)
            continue
        if results:
            break
    if not results:
        print(f"Failure extracting {search}")
    print(results)
    return results

def get_data(links):
    results={}
    for link in links:
        print(f"trying {link}:")
        if "myfigurecollection" in link:
            try:
                resp=requests.get(link, headers=headers, timeout=60)
            except RequestException:
                print("error!")
                resp=None
            if not resp:
                continue

            fig_name, ch_name, code, series_title, image, series_link, price, status = None, None, None, None, None, None, None, None
            soup=BeautifulSoup(resp.content, "html.parser")

            fig_name_tag=soup.find("h1", {"itemprop": "headline", "class": "title"})
            if fig_name_tag:
                fig_name=fig_name_tag.get_text()
                print(f"extracted fig_name: {fig_name}")
                code_tag=soup.find("meta", {"itemprop": "productID"})
                if code_tag:
                    code=code_tag.get("content").split(":")[1]
                    print(f"extracted code: {code}")
                image_tag = soup.find("a", {"href": "#", "title": "Open official gallery"})
                if image_tag:
                    image=[image_tag.find("img").get("src")]
                    print(f"extracted image link: {image}")
                series_tag = soup.find("a", {"class": "tbx-tooltip item-entry important"})
                if series_tag:
                    series_title=series_tag.get_text().strip()
                    print(f"extracted series_title: {series_title}")
                    series_link = "https://myfigurecollection.net" + series_tag['href']
                    time.sleep(1)
                    try:
                        resp=requests.get(series_link, headers=headers, timeout=60)
                    except RequestException:
                        print("error!")
                        resp=None
                    if not resp:
                        continue
                char_label = soup.find("div", class_="data-label", string=re.compile("Character"))
                if char_label:
                    char_value = char_label.find_next_sibling("div", class_="data-value")
                    if char_value:
                        char_tag = char_value.find("a")
                        if char_tag:
                            ch_name = char_tag.text.strip()

                results[fig_name] = {
                    "ch_name": ch_name,
                    "code": code,
                    "series_title": series_title,
                    "series_link": series_link,
                    "link": link,
                    "imgs": image,
                    "price": price,
                    "status": status
                }
        elif "dystryktzero" in link:
            extracted_data = extract(link)

            if extracted_data and extracted_data.get("fig_name"):
                results[extracted_data["fig_name"]] = extracted_data
        else:
            print(f"failure extracting: {link}")
        time.sleep(1)
        
    return results

def match(data, target):
    for mfc_fig in data.keys():
        clean_mfc = clean_for_fuzz(mfc_fig)
        best_score = fuzz.token_set_ratio(target, clean_mfc)
        if best_score < 85:
            series_title = data[mfc_fig].get("series_title")
            series_link = data[mfc_fig].get("series_link")

            if series_link and not data[mfc_fig].get("alias"):
                try:
                    time.sleep(1)
                    resp = requests.get(series_link, headers=headers, timeout=10)
                    soup = BeautifulSoup(resp.content, "html.parser")
                    alias_tag = soup.find("div", {"class": "data-label"}, string="Aliases")
                    if alias_tag:
                        alias_raw = alias_tag.find_next_sibling("div")
                        data[mfc_fig]["alias"] = alias_raw.get_text().replace("(Also known as)", "").strip()
                except Exception:
                    pass
            alias = data[mfc_fig].get("alias", "")
            if series_title and alias:
                new_mfc = mfc_fig.replace(series_title, alias)
                clean_mfc_alias = clean_for_fuzz(new_mfc)
                new_score = fuzz.token_set_ratio(target, clean_mfc_alias)
                if best_score < new_score:
                    best_score = new_score

        data[mfc_fig]["score"] = best_score
    return data

def clean_for_fuzz(title):
    title = re.sub(r'\(.*?\)', '', title)
    title = re.sub(r'[^a-zA-Z0-9\s]', ' ', title).lower()
    cleaned_words = [word for word in title.split() if word not in DOMAIN_NOISE]
    return " ".join(cleaned_words)

def fetch_from_db():
    with app.app_context():
        query = db.session.query(
                                Figure.F_ID,
                                Figure.name.label("fig_name"),
                                Figure.code,
                                Offer.O_ID,
                                ).select_from(Figure) \
            .join(Offer, Offer.F_ID == Figure.F_ID) \
            .filter(Figure.code.is_(None), Figure.F_ID>=5306).all()

        if not query:
            return None
        results: dict={}
        for row in query:
            img_query=db.session.query(Image.path)\
            .join(Offer, Offer.O_ID==Image.O_ID).filter_by(O_ID=row.O_ID).all()
            imgs=[img.path for img in img_query]
            results[row.F_ID]={
                "O_ID": row.O_ID,
                "fig_name": row.fig_name,
                "code": row.code,
                "imgs": imgs,
            }
            print("imgs:")
            print(imgs)

        return results

def update_code_in_db(key, ext_data):
    with app.app_context():
        fig = db.session.query(Figure).filter_by(F_ID=key).first()
        if not fig:
            return
        code_to_set=ext_data.get("code")
        if code_to_set:
            existing_fig_with_code = db.session.query(Figure).filter_by(code=code_to_set).first()
            if existing_fig_with_code and existing_fig_with_code.F_ID!=key:
                print(f"skipped - code already in use by F_ID {existing_fig_with_code.F_ID}")
                return
            fig.code = code_to_set

        existing_offer = db.session.query(Offer).filter_by(link=ext_data["link"]).first()
        if not existing_offer:
            new_offer = Offer(
                F_ID=key,
                link=ext_data["link"],
                store=ext_data["store"],
                price=ext_data.get("price"),
                status=ext_data.get("status") or StatusEnum.UNAVAILABLE
            )
            db.session.add(new_offer)
            db.session.flush()

            if ext_data.get("imgs"):
                process_offer_images(new_offer.O_ID, ext_data["imgs"])

        try:
            db.session.commit()
            print(f"[SUCCESS] code saved {code_to_set} for F_ID={key}")
        except Exception as e:
            db.session.rollback()
            print(f"[db error for F_ID={key}]: {e}")


def assign_codes():
    db_data=fetch_from_db()
    for k, v in db_data.items():
        found=False
        search = f"site:dystryktzero.pl {v["fig_name"]}"
        links=get_links(search)
        for link in links:
            ext_data = extract(link)
            db_imgs=v["imgs"]
            if not ext_data:
                return
            ext_imgs=ext_data.get("imgs", None)
            if not ext_imgs:
                continue
            for db_img in db_imgs:
                for ext_img in ext_imgs:
                    score=compare(db_img, ext_img)
                    print(f"comparing: {db_img} and {ext_img}, score: {score}")
                    if score<0.15:
                        print("comparison score to low, go to next img")
                        break
                    if score>0.90:
                        found=True
                        break
                if found:
                    break
            if found:
                update_code_in_db(k, ext_data)
                break

if __name__ == "__main__":
    assign_codes()
    # print(get_data(["https://www.dystryktzero.pl/figurka-blue-box-nendoroid-chinatsu-kano.html"]))
