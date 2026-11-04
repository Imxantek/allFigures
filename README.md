# allFigures

> **Automated E-Commerce Collectible Figures Aggregator & Computer Vision Deduplication Engine**

`allFigures` is a multi-threaded data pipeline and data-unification ecosystem built to solve the lack of standardization and hidden barcode practices across online collectible figure stores. By aggregating, cleaning, and linking messy listings into a unified relational model, `allFigures` enables price tracking, availability monitoring, and accurate entity disambiguation.

## Key Features

* **Multi-Store Web Scraping Engine:** Asynchronous/rate-limited scraping pipelines for Polish e-commerce sites (e.g., *Yatta.pl*, *DystryktZero.pl*) utilizing dynamic HTTP headers rotation (`User-Agent`), Custom Session Handling, and Robust Exception Fallbacks.

* **Smart Data Normalization & Cache:** Custom **Series-Awareness Cache** operating on a sliding-window algorithm (O(1) lookup for canonical names) paired with Regular Expressions (`regex`) to resolve character/series alias overlaps without cross-series collisions.

* **Computer Vision Hybrid Matching Engine:**

  * **Histogram Pre-Filtering:** Fast HSV color correlation check to quickly discard false-positive figure candidate matches.

  * **SIFT (Scale-Invariant Feature Transform):** Keypoint feature extraction & KNN match verification via OpenCV for visually confirming identical uncoded figures.

* **Multi-Source Fallback System:** Automatic JAN/EAN code lookup via MyFigureCollection (MFC) scraping and DuckDuckGo API (DDGS) fallback when merchant listings lack structured metadata.

* **Data Integrity & Schema Validation:** Strict runtime validation using **Pydantic** schemas before persisting into a normalized **MySQL (SQLAlchemy ORM)** relational database featuring composite keys and cascade alias mappings.

## System Architecture & Pipeline

```
  ┌────────────────────────────────────────────────────────┐
  │               Web Scraping Sources                     │
  │     (Yatta.pl, DystryktZero.pl, MFC Lookup)            │
  └───────────────────────────┬────────────────────────────┘
                              │
                              ▼
  ┌────────────────────────────────────────────────────────┐
  │            Data Normalization & Validation             │
  │ (Regex Cleanup ➔ Series-Aware Cache ➔ Pydantic)      │
  └───────────────────────────┬────────────────────────────┘
                              │
                              ▼
  ┌────────────────────────────────────────────────────────┐
  │             Identity Resolution Pipeline               │
  │    JAN Code Match ➔ Fuzzy String Match (TheFuzz)      │
  │       ➔ Computer Vision (HSV Hist + SIFT Test)        │
  └───────────────────────────┬────────────────────────────┘
                              │
                              ▼
  ┌─────────────────────────────────────────────────────────┐
  │              MySQL Relational Storage                   │
  │(Series ↔ SeriesAlias ↔ Character ↔ Figure ↔ Offer)      │
  └───────────────────────────┬─────────────────────────────┘
                              │
                              ▼
  ┌───────────────────────────────────────────────────┐
  │     CustomTkinter Human-in-the-Loop GUI           │
  └───────────────────────────────────────────────────┘

```

## Tech Stack

* **Language:** Python 3.12+

* **Database & ORM:** MySQL, SQLAlchemy ORM

* **Scraping & Networking:** BeautifulSoup4, Requests, Fake-UserAgent, Pydantic

* **Computer Vision & Image Processing:** OpenCV (`cv2`), Pillow (PIL), NumPy

* **GUI & Concurrency:** CustomTkinter, Threading

* **Search & Analytics:** DuckDuckGo Search API (`ddgs`), `thefuzz` (Fuzzy String Matching)

## Project Status & Accomplishments

* \[x\] Relational MySQL Database Architecture (Composite keys, foreign cascades, alias mappings).

* \[x\] Scrapers for Yatta.pl and DystryktZero.pl with anti-bot handling.

* \[x\] Sliding-window cache engine with Japanese name inversion handling (*First Name/Last Name*).

* \[x\] Two-tier Computer Vision matcher (HSV Histogram filtering + SIFT feature scoring).

* \[x\] Multi-threaded image fetcher & CustomTkinter verification desktop application.

* \[ \] *\[In Progress\]* Public REST API deployment for external consumption.

* \[ \] *\[Planned\]* Full-Stack Web Interface (React + TypeScript dashboard).

## Installation & Usage

1. **Clone the repository:**

   ```
   git clone https://github.com/Imxantek/allFigures.git
   cd allFigures
   
   ```

2. **Set up virtual environment & dependencies:**

   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   
   ```

3. **Configure Environment Variables:**
   Create a `.env` file in the root directory:

   ```
   DATABASE_URL=mysql+pymysql://user:password@localhost:3306/allfigures_db
   
   ```

4. **Initialize Database & Run Scraper:**

   ```
   python run.py
   
   ```

## License

Distributed under the MIT License. See `LICENSE` for more information.
