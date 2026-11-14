import re
import time
import json
import spacy
import random
import requests
from spacy.tokens import DocBin
from bs4 import BeautifulSoup
from sqlalchemy import and_
from sqlalchemy.orm import joinedload
from spacy.util import filter_spans


from models.models import Offer, db, StoreEnum, Figure, Character, Series
from run import app
nlp=spacy.blank("xx")
doc_bin = DocBin()
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.google.com/"
}
def get_title_and_desc():
    with app.app_context():
        offers=db.session.query(Offer).filter(Offer.store==StoreEnum.DYSTRYKTZERO).order_by(Offer.O_ID.asc()).all()

        for offer in offers:
            resp = requests.get(offer.link, headers=headers)
            soup = BeautifulSoup(resp.content, 'html.parser')
            title, desc = None, None
            if resp.ok and soup is not None:
                if offer.store==StoreEnum.YATTA:
                    title, desc = get_from_yatta(soup)
                elif offer.store==StoreEnum.DYSTRYKTZERO:
                    title, desc = get_from_dystrykt(soup)
            if title and desc:
                offer.title=title
                offer.description=desc
                try:
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
            time.sleep(0.2)

def get_from_yatta(soup):
    raw_title = soup.find("h2", class_="tytul")
    title=raw_title.get_text() if raw_title else None
    fig_name = re.sub(r'\s+', ' ', title).strip() if title else None

    desc = soup.find("div", itemprop="description")
    desc_text = desc.get_text(separator='\n', strip=True).replace('\xa0', ' ') if desc else None
    return fig_name, desc_text
def get_from_dystrykt(soup):
    fig_name_tag = soup.find("h1", class_="ty-product-block-title")
    fig_name = fig_name_tag.get_text().strip() if fig_name_tag else None
    desc_tag = soup.find("div", id="content_description")
    desc_text = desc_tag.get_text(separator=' ', strip=True).replace('\xa0', ' ') if desc_tag else None
    return fig_name, desc_text

def fetch_random():
    with app.app_context():
        all_records=db.session.query(Offer)\
            .options(joinedload(Offer.figure)
                     .joinedload(Figure.character)
                     .joinedload(Character.aliases),
                     joinedload(Offer.figure)
                     .joinedload(Figure.character)
                     .joinedload(Character.series)
                     .joinedload(Series.aliases))\
            .filter(and_(Offer.title.is_not(None), Offer.description.is_not(None))).all()
        print(all_records)
        random.shuffle(all_records)
        split_index=int(len(all_records)*0.8)
        training_batch=all_records[:split_index]
        validation_batch=all_records[split_index:]
        get_json(training_batch, "training.json")
        get_json(validation_batch, "validation.json")
        get_spacy("training.json", "train.spacy")
        get_spacy("validation.json", "dev.spacy")



def get_json(batch, filename):
    Training_data=[]
    total_count=0
    full_data_count=0
    for offer in batch:
        text=offer.title.strip()+" "+offer.description.strip()
        text=re.sub(r'[\n\r\']', ' ', text)
        char_name=offer.figure.character.name
        char_alias=offer.figure.character.aliases
        title=offer.figure.character.series.title
        title_alias=offer.figure.character.series.aliases
        character_positions=[(match.start(), match.end()) for match in re.finditer(char_name, text)]
        ch_alias_positions=[]
        for alias in char_alias:
            ch_alias_positions.extend([(match.start(), match.end()) for match in re.finditer(alias.alias, text)])
        title_positions=[(match.start(), match.end()) for match in re.finditer(title, text)]
        title_alias_positions=[]
        for alias in title_alias:
            title_alias_positions=[(match.start(), match.end()) for match in re.finditer(alias.alias, text)]
        # print(text)
        if character_positions:
            character_positions=[(fst, snd, "CHARACTER") for fst, snd in character_positions]
        if ch_alias_positions:
            ch_alias_positions=[(fst, snd, "CHARACTER") for fst, snd in ch_alias_positions]
        if title_positions:
            title_positions=[(fst, snd, "TITLE") for fst, snd in title_positions]
        if title_alias_positions:
            title_alias_positions=[(fst, snd, "TITLE") for fst, snd in title_alias_positions]
        # print("char: ", character_positions)
        # print("ch_alias: ", ch_alias_positions)
        # print("title: ", title_positions)
        # print("title_alias: ", title_alias_positions)
        merge=[]
        merge.extend(character_positions)
        merge.extend(ch_alias_positions)
        merge.extend(title_positions)
        merge.extend(title_alias_positions)
        if not merge:
            continue
        ents={"entities": merge}
        tup=(text, ents)
        Training_data.append(tup)
    print(Training_data)
    with open(f'{filename}', 'w', encoding='utf8') as f:
        json.dump(Training_data, f, indent=4)
    #     if (character_positions or ch_alias_positions) and (title_positions or title_alias_positions):
    #         full_data_count+=1
    #     total_count+=1
    # print("Total: ", total_count)
    # print("Full Data: ", full_data_count)

def get_spacy(src_filename, target_filename):
    with open(f'{src_filename}', 'r', encoding='utf-8') as f:
        train_data = json.load(f)

    for text, annotations in train_data:
        doc = nlp.make_doc(text)
        ents = []
        print(annotations)
        for start, end, label in annotations['entities']:
            span = doc.char_span(start, end, label=label)
            if span is not None:
                ents.append(span)
        doc.ents = filter_spans(ents)
        doc_bin.add(doc)
    doc_bin.to_disk(f"{target_filename}")

if __name__=="__main__":
    # resp=requests.get("https://www.dystryktzero.pl/figurka-sword-art-online-alternative-gun-gale-online-ii-luminasta-fukaziroh-2.html", headers=headers)
    # soup = BeautifulSoup(resp.content, 'html.parser')
    # print(get_from_dystrykt(soup))
    # get_title_and_desc()
    fetch_random()