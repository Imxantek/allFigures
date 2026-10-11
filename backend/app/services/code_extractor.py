import re
import time
import requests
from ddgs import DDGS
from ddgs.exceptions import DDGSException
from requests import RequestException
from sqlalchemy.exc import IntegrityError
from thefuzz import fuzz
from app.models import StatusEnum, StoreEnum, db, Character, Series, Offer, Figure
from static.datasets.domain_noise import DOMAIN_NOISE
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.google.com/"
}

def get_links(name:str):
    results=[]
    for i in range(10):
        print(f"Try No. {i}")
        try:
            with DDGS() as ddgs:
                print("Extracting...")
                raw_res=list(ddgs.text(name, max_results=5))
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
        print(f"Failure extracting {name}")
    print(results)
    return results

def get_data(links):
    results={}
    for link in links:
        print(f"trying {link}:")
        try:
            resp=requests.get(link, headers=headers, timeout=60)
        except RequestException:
            print("error!")
            resp=None
        if not resp:
            continue
        name, code, series, image, series_link, price, status = None, None, None, None, None, None, None
        soup=BeautifulSoup(resp.content, "html.parser")
        if "myfigurecollection" in link:
            name_tag=soup.find("h1", {"itemprop": "headline", "class": "title"})
            if name_tag:
                name=name_tag.get_text()
                print(f"extracted name: {name}")
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
                    series=series_tag.get_text().strip()
                    print(f"extracted series: {series}")
                    series_link = "https://myfigurecollection.net" + series_tag['href']
                    time.sleep(1)
                    try:
                        resp=requests.get(series_link, headers=headers, timeout=60)
                    except RequestException:
                        print("error!")
                        resp=None
                    if not resp:
                        continue
                results[name] = {
                    "code": code,
                    "series": series,
                    "figure_link": link,
                    "series_link": series_link,
                    "alias": None,
                    "image": image,
                }
        elif "dystryktzero" in link:
            name_tag=soup.find("h1", class_="ty-product-block-title")
            if not name_tag:
                print(f"Brak nazwy (uszkodzony link / zła struktura): {link}")
                continue
            name=name_tag.get_text()
            print(f"extracted name: {name}")
            code_tag=soup.find("span", class_="ty-control-group__item")
            if code_tag:
                code=code_tag.get_text()
                print(f"extracted code: {code}")
            image_tags=soup.find_all("a", {"class":"cm-image-previewer", "href": True})
            if image_tags:
                image=[img["href"] for img in image_tags]
                print(f"extracted images: {image}")

            thematics_tag=soup.find(string=re.compile("Tematyka:"))
            if thematics_tag:
                series_value_tags=thematics_tag.find_next("div", class_="ty-product-feature__value")
                if series_value_tags:
                    series_tags=series_value_tags.findChildren("li", {"class": "ty-product-feature__multiple-item"})
                    if series_tags:
                        for series_tag in series_tags:
                            if "Anime / Manga" not in series_tag.get_text():
                                series=series_tag.get_text().strip()

            status_tag=soup.find("div", id="ss_product_available")
            status_text=status_tag.get_text()
            if "Wyprzedany" in status_text:
                status=StatusEnum.ARCHIVAL

            if "Przedsprzedaży" in status_text:
                status=StatusEnum.PREORDER

            if "Dostępny" in status_text or "Pozostała" in status_text:
                status=StatusEnum.AVAILABLE

            if status is not StatusEnum.ARCHIVAL:
                price_tag = soup.find("span", {"class": "ty-price"})
                if price_tag:
                    price = float(price_tag.get_text().split("\xa0")[0].replace(',', '.'))


            results[name] = {
                "code": code,
                "series": series,
                "figure_link": link,
                "image": image,
                "price": price,
                "status": status
            }


        else:
            print(f"failure extracting: {link}")
        time.sleep(1)
    return results

def match(data, target):
    for mfc_fig in data.keys():
        clean_mfc = clean_for_fuzz(mfc_fig)
        best_score = fuzz.token_set_ratio(target, clean_mfc)
        if best_score < 85:
            series = data[mfc_fig].get("series")
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
            if series and alias:
                new_mfc = mfc_fig.replace(series, alias)
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