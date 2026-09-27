import time
from app import create_app
from app.models import db
from app.services.scrapers.yatta_scraper import scrape_yatta, init_cache_from_db
from app.services.desactivator_yatta import deactivate_offers
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
        scrape_yatta(url="https://yatta.pl/Sprowadzane/Figurki,914,s")
        # deactivate_offers()