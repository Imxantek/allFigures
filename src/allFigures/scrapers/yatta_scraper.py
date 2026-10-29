import os
import re
import time
import spacy
import requests

from scrapers.scraper_functions import (init_cache_from_db, add_to_cache, get_name_from_mfc,
                               get_name_from_cache,process_scraped_data)

CURRENT_FILE = os.path.abspath(__file__)
SCRAPERS_DIR = os.path.dirname(CURRENT_FILE)
ALLFIGURES_DIR = os.path.dirname(SCRAPERS_DIR)
SRC_DIR = os.path.dirname(ALLFIGURES_DIR)

from typing import Any
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from requests import RequestException
from models.models import StatusEnum, StoreEnum
from decimal import Decimal, InvalidOperation
from static.datasets.regex_patterns import patterns
from static.datasets.skip_list import MASTER_SKIP_PATTERN
from static.datasets.blacklist import URL_BLACKLIST, KW_BLACKLIST


ua=UserAgent()
headers = {'User-Agent': ua.random}


def scrape_yatta(url="https://yatta.pl/Figurki,4,s"):
    init_cache_from_db()
    full_link=url+"?A=0&B=80"
    resp=requests.get(full_link, headers=headers, timeout=30)

    if not resp.ok:
        print("response not ok!")
        return

    print("Extracting pg 0")
    print("response ok!")
    
    soup=BeautifulSoup(resp.content,"html.parser")
    extract_page(full_link)

    max_a_tag=soup.find("a", string="»")
    match = re.search(r"[?&]A=([^&]+)", max_a_tag.get("href"))
    
    if match:
        max_a=int(match.group(1))
    else:
        max_a=0


    for pg in range(1, max_a+1):
        time.sleep(1)
        print(f"Extracting page {pg}")
        full_link=f"{url}?A={pg}&B=80"
        extract_page(full_link)


def extract_page(link):
    resp=requests.get(link, headers=headers, timeout=30)
    soup=BeautifulSoup(resp.content,"html.parser")

    products=soup.find_all("div", {"id": "product_container_large"})

    for product in products:
        time.sleep(1)
        current=product.find("a")
        link="https:"+current.get("href")
        
        if link in URL_BLACKLIST:
            print("rejected - url blacklisted!")
            continue
            
        res=extract(link)
        process_scraped_data(res)

def extract(link: str):
    try:
        resp=requests.get(link, headers=headers, timeout=30)
        resp.raise_for_status()
    except RequestException as err:
        print(f"Error while connecting to {link}")
        return
    
    if not resp.ok:
        print("response not ok!")
        return
    
    soup=BeautifulSoup(resp.content,"html.parser")
    
    res :dict[str, Any]= {
        'fig_name': None,
        'price': None,
        'link': link,
        'code': None,
        'series_title': None,
        'manufacturer': None,
        'status': StatusEnum.AVAILABLE,
        'scale': None,
        'store': StoreEnum.YATTA,
        'ch_name': None,
        'imgs': []
    }

    # fig name assignment
    raw_title = soup.find("h2", class_="tytul").get_text()
    fig_name = re.sub(r'\s+', ' ', raw_title).strip()
    
    # name assignment
    if fig_name:
        res['fig_name']=fig_name

    if any(word in fig_name.lower() for word in KW_BLACKLIST):
        res['fig_name']=None
        res['link']=link
        print("blacklisted fig name - returning")
        return

    # price assignment
    price_node=soup.find(string=re.compile("Cena:"))
    if price_node:
        price_tag=price_node.find_next("span")
        if price_tag:
            try:
                price=Decimal(price_tag.get("content"))
                res['price']=price
            except InvalidOperation:
                pass
    
    # link assignment
    res['link']=link
    
    # code assignment
    code_node = soup.find(string=re.compile("ISBN:"))
    if code_node:
        code = code_node.split(':')[1].strip()
        res['code']=code
        # print(code)


    # series assignment
    series_node = soup.find(string=re.compile("Seria:"))
    if series_node:
        series_tag = series_node.find_next_sibling("a")
        if series_tag:
            series_name = series_tag.text.strip()
            res['series_title']=series_name
    
    # manufacturer assignment
    manuf_node=soup.find(string=re.compile(r"Producent:|Wydawca:"))
    if manuf_node:
        manuf_tag=manuf_node.find_next_sibling("a")
        if manuf_tag:
            manufacturer=manuf_tag.text.strip()
            res['manufacturer']=manufacturer
            # print(manufacturer)

    # status assignment
    status=StatusEnum.AVAILABLE
    if "Preorder:" in fig_name:
        status=StatusEnum.PREORDER
        fig_name=fig_name.replace("Preorder:", "").strip()
        res['fig_name']=fig_name
    else:
        unav=soup.find(string=re.compile("brak towaru"))
        if unav:
            status=StatusEnum.UNAVAILABLE
    res["status"]=status

    # store assignment
    store=StoreEnum.YATTA
    res['store']=store

    # image assignemnt
    carousel_tag = soup.find("div", class_="image_field")
    if carousel_tag:
        imgs = carousel_tag.find_all("img", {"src": True})
        srces = ["https:"+img['src'] for img in imgs if "size300" in img['src']]
        res['imgs']=list(dict.fromkeys(srces))

    
    # extraction of character name from cache 
    code=res.get("code")
    series_title=res.get("series_title", "")
    desc = soup.find("div", itemprop="description")
    desc_text = desc.get_text(separator='\n', strip=True).replace('\xa0', ' ') if desc else ""

    # search the desc for scale
    match = re.search(r"1/\d+", fig_name + ' ' + desc_text)
    if not match:
        match = re.search(r'\d+\s*cm', fig_name + ' ' + desc_text, re.IGNORECASE)
    scale = match.group(0) if match else ""

    fig_strp = fig_name
    if res.get("series_title"):
        fig_strp = fig_strp.replace(res.get("series_title"), "").strip()
    if res.get("manufacturer"):
        fig_strp = fig_strp.replace(res.get("manufacturer"), "").strip()
    fig_strp = re.sub(r'[^a-zA-Z0-9/\-() ]', "", fig_strp).strip()

    name, is_fallback=get_name_from_cache(fig_name, series_title)
    if name and not is_fallback:
        print("found name locally")

    # search MFC for name
    if code and (not name or not scale or is_fallback):
        mfc_char, mfc_scale=get_name_from_mfc(code)
        if (not name or is_fallback) and mfc_char:
            name=mfc_char
            is_fallback=False
        if not scale and mfc_scale:
            scale=mfc_scale

    # search the description for character name
    # clear the fig name, removing the title and manufacturer
    if (not name or is_fallback) and fig_strp and desc_text:
            desc_name, desc_is_fallback=get_name_from_desc(fig_strp, desc_text, series_title)
            if desc_name:
                cached_desc_name, cached_fallback = get_name_from_cache(desc_name, series_title)
                if cached_desc_name and not cached_fallback:
                    name = cached_desc_name
                    is_fallback = False
                elif not desc_is_fallback:
                    name = desc_name
                    is_fallback = False
                elif not name:
                    name = desc_name
    
    res["scale"] = scale
    
    # name assignment
    if not name:
        print("could not extract the character name for this figure")
        return res
    else:
        res["ch_name"]=name

    return res


def get_name_from_desc(fig_strp, desc, series_title=""):
    fallback_name=None
    series_lower=series_title.lower() if series_title else ""

    # first method of extracting figure names - regex based search with fallback

    combined_text = f"{fig_strp}. {desc}"
    for pattern in patterns:
        match = re.search(pattern, combined_text) # checking for matching patterns
        if match: 
            extracted_name=match.group(1).strip()
            contains_skip=False

            # checking if any of the extracted words are in the skip pattern
            contains_skip=bool(MASTER_SKIP_PATTERN.search(extracted_name))

            if contains_skip:
                continue

            # this part of the code is responsible for handling cases in where the
            # character name is also the name of the series
            # fe naruto, harry potter, godzilla
            # if the regex finds such name, it saves it for later
            # when other methods of extracting names fail, the fallback is assigned
            # Example of such figure:
            # Naruto Shippuden Grandista PVC Prize Figure - Uchiha Sasuke

            # split the regex and check the original fig_name
            if any(part in fig_strp for part in extracted_name.split()):
                # if the regex finding is in the series name or vice versa
                if series_lower and (extracted_name.lower() in series_lower or series_lower in extracted_name.lower()):
                    if not fallback_name:
                        # located a fallback
                        fallback_name=extracted_name
                    continue
                # else the name is matches the regex and isnt a fallback
                return extracted_name, False


    # another way of matching names - uppercase words matching between the fig_name and description

    # clearing using the master regex pattern
    clean_fig_strip=MASTER_SKIP_PATTERN.sub("", fig_strp)
    # removing the double spaces
    clean_fig_strip=" ".join(clean_fig_strip.split())

    fig_split=clean_fig_strip.split(" ")
    name=[]

    for word in fig_split:
        # checking if the word is uppercase
        if not word or not word[0].isupper():
            continue
        # checking if the uppercase word in the fig_name also appears in the desc
        if re.search(rf'\b{re.escape(word)}\b', desc, re.IGNORECASE):
            name.append(word)
    # merge the name
    carved_name=" ".join(name)
    if carved_name:
        # the same check as above, fallback logic.
        if series_lower and (carved_name.lower() in series_lower or series_lower in carved_name.lower()):
            if not fallback_name:
                fallback_name=carved_name
        else:
            return carved_name, False
    return fallback_name, True

