import os
import time
from dotenv import load_dotenv
from flask import Flask
from models.models import *
from api import api_bp
from models.models import db
from scrapers.dystrykt_scraper import scrape_dystrykt, extract
from scrapers.yatta_scraper import scrape_yatta
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
        print(extract("https://www.dystryktzero.pl/figurka-puella-magi-madoka-magica-the-movie-rebellion-madoka-kaname.html"))
        # scrape_dystrykt("https://www.dystryktzero.pl/statuetki/")
        # scrape_dystrykt("https://www.dystryktzero.pl/figurki/")
        # scrape_dystrykt("https://www.dystryktzero.pl/figurki-funko-pop-vinyl/")
        # character until 3502 - Hana shirosaki are valid