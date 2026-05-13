# data/

## Setup Instructions

### Step 1 — Download raw datasets
- **Yelp**: https://business.yelp.com/external-assets/files/Yelp-JSON.zip
  Extract to `yelp_data/` in project root

- **Amazon Electronics**: 
  https://nijianmo.github.io/amazon/index.html → Electronics 5-core
  Place as `data/sample/amazon_electronics_review.JSON`

- **Goodreads**: https://cseweb.ucsd.edu/~jmcauley/datasets/goodreads.html
  Download `goodreads_reviews_spoiler_raw.json` and `goodreads_books.json`
  Place in `goodreads_data/` in project root

### Step 2 — Generate sample files
```bash
python data/sample_yelp.py
python data/sample_goodreads_reviews.py
python data/sample_goodreads_books.py
python data/sample_amazon.py
```

### Step 3 — Run ingestion
```bash
python data/ingest.py
# or for quick test:
python data/ingest.py --sample-only
```