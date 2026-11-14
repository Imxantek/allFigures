import os
import time
from dotenv import load_dotenv
from flask import Flask
from models.models import *
from api import api_bp
from models.models import db
from scrapers.dystrykt_scraper import scrape_dystrykt, extract
from scrapers.yatta_scraper import scrape_yatta, get_name_from_desc
from scrapers.scraper_functions import  init_cache_from_db, process_scraped_data
def create_app():
    load_dotenv()
    app=Flask(__name__)

    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI')
    app.config['SQLALCHEMY_TRACK_MODIFICATION'] = False
    app.config['SQLALCHEMY_ECHO'] = True

    db.init_app(app)
    app.register_blueprint(api_bp)
    return app

app=create_app()
if __name__=="__main__":
    with app.app_context():
        for i in range(5):
            try:
                db.create_all()
                print("Created db successfully")
                break
            except Exception as e:
                print(f"Failed to create db. Retrying in 5 seconds, {4-i} tries left")
                time.sleep(5)
        init_cache_from_db()
        # print(extract("https://www.dystryktzero.pl/figurka-decorated-life-collection-tea-time-cats-orange-cat.html"))
        print(get_name_from_desc("Figurka Decorated Life Collection - Tea Time Cats Orange Cat", "Wspaniała figurka Tea Time Cats Orange Cat, stworzona przez producenta Ribose, pochodzi z serii figurek Decorated Life Collection. Charakteryzuje się wysoką jakością wykonania, bogatymi detalami, oraz bardzo ładnym malowaniem. Została zrobiona z PVC/ABS, a jej wysokość to około 10 cm. Całość jest statyczna i nie posiada żadnych punktów artykulacji. Jest to niewątpliwie prawdziwa gratka dla fanów postaci jak i kolekcjonerów figurek w stylu anime / mangi."))

        # scrape_dystrykt("https://www.dystryktzero.pl/statuetki/")
        # scrape_dystrykt("https://www.dystryktzero.pl/figurki/")
        # scrape_dystrykt("https://www.dystryktzero.pl/figurki-funko-pop-vinyl/")
        # character until 3502 - Hana shirosaki are valid