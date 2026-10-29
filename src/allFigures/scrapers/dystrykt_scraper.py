import os
import time



from bs4 import BeautifulSoup
import requests
import re
from requests import RequestException

from models.models import Figure, StatusEnum, StoreEnum, db
from scrapers.scraper_functions import process_scraped_data, get_name_from_cache, init_cache_from_db, get_name_from_mfc
from static.datasets.blacklist import URL_BLACKLIST

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.google.com/"
}

def scrape_dystrykt(url="https://www.dystryktzero.pl/statuetki/"):
    uri="page-1/?items_per_page=192"
    full_link=url+uri
    resp=requests.get(full_link,headers=headers,timeout=30)
    extract_page(full_link)
    soup = BeautifulSoup(resp.content, "html.parser")
    last_page_idx=soup.find("a", {"data-ca-scroll": ".cm-pagination-container", "class":"cm-history ty-pagination__item hidden-phone ty-pagination__range cm-ajax"}).get_text().split("-")[1].strip()
    # for i in range(2, int(last_page_idx)+1):
    for i in range(2,3):
        uri=f"page-{i}/?items_per_page=192"
        full_link=url+uri
        extract_page(full_link)


def extract_page(link):
    resp=requests.get(link,headers=headers,timeout=30)
    soup = BeautifulSoup(resp.content, "html.parser")
    products=[product.get("href") for product in soup.find_all("a", class_="product-title")]
    for product in products:
        time.sleep(1)
        if product in URL_BLACKLIST:
            print("rejected - url blacklisted!")
            continue
        res=extract(product)
        if not res:
            continue
        process_scraped_data(res)

        # print("extracted product: ")
        # print(res)



def extract(url):
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
    except RequestException as err:
        print(f"Error while connecting to {url}")
        return

    if not resp.ok:
        print("response not ok!")
        return

    res = {
        'fig_name': None,
        'price': None,
        'link': url,
        'code': None,
        'series_title': None,
        'manufacturer': None,
        'status': StatusEnum.AVAILABLE,
        'scale': None,
        'store': StoreEnum.DYSTRYKTZERO,
        'ch_name': None,
        'imgs': []
    }

    soup = BeautifulSoup(resp.content, "html.parser")


    # get fig name
    fig_name_tag = soup.find("h1", class_="ty-product-block-title")
    if not fig_name_tag:
        # print(f"No fig name: {url}")
        return res
    fig_name = fig_name_tag.get_text().strip()
    # print(f"extracted fig_name: {fig_name}")
    res["fig_name"] = fig_name

    # get code
    code_tag = soup.find("span", class_="ty-control-group__item")
    if code_tag:
        code = code_tag.get_text().strip()
        # print(f"extracted code: {code}")
        res["code"]=code


    # get images
    image_tags = soup.find_all("a", {"class": "cm-image-previewer", "href": True})
    if image_tags:
        image = [img["href"] for img in image_tags]
        # print(f"extracted images: {image}")
        res["imgs"]=image

    # get series
    thematics_tag = soup.find(string=re.compile("Tematyka:"))
    if thematics_tag:
        series_value_tags = thematics_tag.find_next("div", class_="ty-product-feature__value")
        if series_value_tags:
            series_tags = series_value_tags.find_all("li", {"class": "ty-product-feature__multiple-item"})
            if series_tags:
                # on dystryktzero, often times a figure has more than one series assigned,
                # usually the mos specific and accurate one is last
                res["series_title"] = series_tags[-1].get_text().strip()
                # if len(series_tags)>1:
                #     for series_tag in series_tags:
                #         if "Anime / Manga" not in series_tag.get_text():
                #             series = series_tag.get_text().strip()
                #             res["series_title"] = series
                # else:
                #     series = series_tags[0].get_text().strip()
                #     res["series_title"] = series

    # get status
    status_tag = soup.find("div", id="ss_product_available")
    if status_tag:
        status_text = status_tag.get_text()
        status=StatusEnum.UNAVAILABLE
        if "Wyprzedany" in status_text:
            status = StatusEnum.ARCHIVAL

        if "Przedsprzedaży" in status_text:
            status = StatusEnum.PREORDER

        if "Dostępny" in status_text or "Pozostała" in status_text:
            status = StatusEnum.AVAILABLE
        res["status"] = status


        if status is not StatusEnum.ARCHIVAL:
            price_tag = soup.find("span", {"class": "ty-price"})
            if price_tag:
                price = float(price_tag.get_text().split("\xa0")[0].replace(',', '.'))
                res["price"] = price

    # get manufacturer
    manufacturer_label_tag=soup.find(string=re.compile("Producent:"))
    if manufacturer_label_tag:
        manufacturer_tag = manufacturer_label_tag.find_next("div")
        if manufacturer_tag:
            manufacturer=manufacturer_tag.get_text().strip()
            res["manufacturer"] = manufacturer

    scale_tag = soup.find(string=re.compile("Wysokość:"))
    if scale_tag:
        scale_tag = scale_tag.find_next("div")
        if scale_tag:
            scale=scale_tag.get_text().strip().replace("\n", "")
            res["scale"] = scale

    # get name
    is_fallback = False
    hero_label_tag = soup.find(string=re.compile("Bohater:"))
    if hero_label_tag:
        char_value_tag = hero_label_tag.find_next("div", class_="ty-product-feature__value")
        if char_value_tag:
            char_name_li = char_value_tag.find_all("li", class_="ty-product-feature__multiple-item")
            if len(char_name_li)>1:
                return None
            ch_name = char_name_li[0].get_text().strip()
            res["ch_name"] = ch_name
            if res['ch_name'] not in res["fig_name"]:
                is_fallback = True

    if is_fallback or not res["ch_name"]:
        # get desc
        desc_tag=soup.find("div", id="content_description")
        if desc_tag:
            strongs=desc_tag.find_all("strong")
            if strongs:
                strong=strongs[0].get_text()
                res["ch_name"],is_fallback=get_name_from_cache(strong, res.get("series_title"))


    if res["code"] and (is_fallback or not res["ch_name"]):
        name, _ = get_name_from_mfc(res["code"])
        res["ch_name"] = name
    return res




# if __name__=="__main__":
    # scrape_dystrykt()
