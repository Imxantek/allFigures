import csv

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import time
import re

from requests import RequestException

ua=UserAgent()
headers = {'User-Agent': ua.random}
series_set=set()

def scrape_series_dystrykt(url):
    items_per_page = 192
    suffix = f"page-{0}/?items_per_page={items_per_page}"
    first_page=url+suffix
    resp=requests.get(first_page,headers=headers, timeout=60)
    soup=BeautifulSoup(resp.content,"html.parser")
    pagination_tag=soup.find("a", {"data-ca-scroll":".cm-pagination-container", "class": "cm-history ty-pagination__item hidden-phone ty-pagination__range cm-ajax"})
    max_page=0

    if pagination_tag:
        max_page=int(pagination_tag.get_text().split("-")[1].strip())
    print(f"max_page: {max_page}")

    for page in range(0,max_page):
        print("Extracting page: ", page)
        suffix=f"page-{page}/?items_per_page={items_per_page}"
        full_url=url+suffix
        page_series_dystrykt(full_url)

def page_series_dystrykt(url):
    resp=requests.get(url,headers=headers, timeout=60)
    if not resp.ok:
        print(f"Error connecting to {url}")
        return
    soup=BeautifulSoup(resp.content,"html.parser")
    products = soup.find_all("a", {"class":"product-title", "title": True, "href": True})
    for product in products:
        time.sleep(0.5)
        curr_link=product.get("href")
        print(f"curr_link: {curr_link}")
        try:
            extract_series_dystrykt(curr_link)
        except RequestException as e:
            print(f"Error connecting to {curr_link}")

def extract_series_dystrykt(url):
    try:
        resp=requests.get(url,headers=headers, timeout=60)
        resp.raise_for_status()
    except RequestException as e:
        print(f"Error connecting to {url}")
        return
    soup=BeautifulSoup(resp.content,"html.parser")
    series=""
    thematics_tag = soup.find(string=re.compile("Tematyka:"))
    if thematics_tag:
        series_value_tags = thematics_tag.find_next("div", class_="ty-product-feature__value")
        if series_value_tags:
            series_tags = series_value_tags.find_all("li", {"class": "ty-product-feature__multiple-item"})
            if series_tags:
                for series_tag in series_tags:
                    series = series_tag.get_text().strip()
                    print(f"series: {series}")
                    series_set.add(series)

def scrape_series():
    print("Welcome to the series scraper")
    for i in range(0, 23):
        suffix=f"?A={i}&B=80"
        url=f"https://yatta.pl/Figurki,4,s{suffix}"
        page_series(url)
    print(series_set)

def page_series(url):
    resp=requests.get(url,headers=headers, timeout=60)
    soup=BeautifulSoup(resp.content,"html.parser")
    products = soup.find_all("div", {"id": "product_container_large"})
    for product in products:
        time.sleep(0.5)
        current = product.find("a")
        link = "https:" + current.get("href")
        print("current link:",link)
        extract_series(link)

def extract_series(link):
    try:
        resp=requests.get(link,headers=headers, timeout=60)
        resp.raise_for_status()
    except RequestException as e:
        print(f"Error connecting to {link}")
        return
    soup=BeautifulSoup(resp.content,"html.parser")
    series_node = soup.find(string=re.compile("Seria:"))
    if series_node:
        series_tag = series_node.find_next_sibling("a")
        if series_tag:
            series_name = series_tag.text.strip()
            series_set.add(series_name)
            # print(series_name)

if __name__=="__main__":
    scrape_series_dystrykt("https://www.dystryktzero.pl/statuetki/")
    scrape_series_dystrykt("https://www.dystryktzero.pl/figurki/")
    scrape_series_dystrykt("https://www.dystryktzero.pl/figurki-funko-pop-vinyl/")
    scrape_series_dystrykt("https://www.dystryktzero.pl/mini-figurki-pl/")
    print(series_set)
    with open("series_set.csv", 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(list(series_set))