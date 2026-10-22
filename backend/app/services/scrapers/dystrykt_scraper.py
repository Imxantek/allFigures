from bs4 import BeautifulSoup 
import requests
import re
from static.datasets.series_aliases import SERIES_ALIASES
from app.models import StatusEnum, StoreEnum
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.google.com/"
}

def extract(url):
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
     
    resp=requests.get(url)
    soup = BeautifulSoup(resp.content, "html.parser")
    
    
    # get fig name
    fig_name_tag = soup.find("h1", class_="ty-product-block-title")
    if not fig_name_tag:
        print(f"No fig name: {url}")
        fig_name=None
        return res
    fig_name = fig_name_tag.get_text()
    print(f"extracted fig_name: {fig_name}")
    res["fig_name"] = fig_name
    
    # get code
    code_tag = soup.find("span", class_="ty-control-group__item")
    if code_tag:
        code = code_tag.get_text()
        print(f"extracted code: {code}")
        res["code"]=code
    
    
    # get images
    image_tags = soup.find_all("a", {"class": "cm-image-previewer", "href": True})
    if image_tags:
        image = [img["href"] for img in image_tags]
        print(f"extracted images: {image}")
        res["imgs"]=image
    
    # get series
    thematics_tag = soup.find(string=re.compile("Tematyka:"))
    if thematics_tag:
        series_value_tags = thematics_tag.find_next("div", class_="ty-product-feature__value")
        if series_value_tags:
            series_tags = series_value_tags.find_all("li", {"class": "ty-product-feature__multiple-item"})
            if series_tags:
                for series_tag in series_tags:
                    if "Anime / Manga" not in series_tag.get_text():
                        series = series_tag.get_text().strip()
                        series = SERIES_ALIASES.get(series, series)
                        res["series_title"] = series
    
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

    # get name
    hero_label_tag = soup.find(string=re.compile("Bohater:"))
    if hero_label_tag:
        char_value_tag = hero_label_tag.find_next("div", class_="ty-product-feature__value")
        if char_value_tag:
            char_name_li = char_value_tag.find_all("li", class_="ty-product-feature__multiple-item")
            ch_name = char_name_li[0].get_text().strip()
            res["ch_name"] = ch_name


    return res