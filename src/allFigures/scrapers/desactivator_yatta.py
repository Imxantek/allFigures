import os
import sys
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import time
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

ua=UserAgent()
headers = {'User-Agent': ua.random}
offers=[]

from app.schemas.schemas import ScrapedOffer
from app.models import StatusEnum, StoreEnum, db, Character, Series, Offer, Figure

def deactivate_offers():
    offers=db.session.query(Offer.link).where(Offer.store==StoreEnum.YATTA, Offer.status!=StatusEnum.ARCHIVAL).all()
    # print(offers)
    count=0
    print(f"Loaded {len(offers)} offers")
    for offer in offers:
        if is_expired(str(offer.link)):
            print(f"offer {offer.link} is no longer valid - setting expired status")
            record=db.session.query(Offer).filter_by(link=offer.link).first()
            if record:
                record.status=StatusEnum.ARCHIVAL
                count+=1
        else:
            print("current offer was not expired")
        time.sleep(0.5)
    db.session.commit()
    print(f"Deactivated {count} offers")
def is_expired(link):
    resp=requests.get(link,headers=headers,timeout=30)
    if not resp.ok:
        return True
    soup=BeautifulSoup(resp.content,"html.parser")
    if soup.find(string="Niestety, ten artykuł nie jest już dostępny na naszej stronie."):
        return True
    return False

if __name__=="__main__":
    # print(is_expired("https://yatta.pl/Jason_and_the_Argonauts_Soft_Vinyl_Statue_Hydra_30_cm,262487,p"))
    # print(is_expired("https://yatta.pl/Preorder_WeatherPlanet_PVC_Figure_1_7_Amagai_Ruka_25_cm,319476,p"))
    deactivate_offers()