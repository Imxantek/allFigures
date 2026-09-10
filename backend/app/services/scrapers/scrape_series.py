import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import time
import re

from requests import RequestException

ua=UserAgent()
headers = {'User-Agent': ua.random}
series_set=set()

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
        time.sleep(1)
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
    scrape_series()