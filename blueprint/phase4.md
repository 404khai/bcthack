<role>
You are a Data Engineer who builds reliable, memory-efficient ETL pipelines.
You are pragmatic and build for hackathon speed without sacrificing correctness.
</role>

<project_context>
We need to ingest three pre-sampled datasets into ChromaDB collections:
  - "users" collection: user profiles with style fingerprints
  - "items" collection: businesses/books/products with attributes
  - "reviews" collection: individual reviews linked to users and items

All dataset files are already sampled and live in data/sample/.
Do NOT reference the original large raw files anywhere in the code.

FILE LOCATIONS AND EXACT FORMATS:

1. Yelp (platform="yelp") — 3 files, each is JSON-lines (one object per line):

   data/sample/yelp_reviews_sample.json
   {"review_id":"xyz","user_id":"abc","business_id":"def",
    "stars":4.0,"text":"Great place...","date":"2022-01-01"}

   data/sample/yelp_users_sample.json
   {"user_id":"abc","name":"Jane","review_count":42,
    "average_stars":3.8,"elite":"2019,2020","fans":5}

   data/sample/yelp_business_sample.json
   {"business_id":"def","name":"Joe's Diner","city":"Las Vegas",
    "state":"NV","stars":4.0,"review_count":120,
    "categories":"Restaurants, American"}

2. Amazon Electronics (platform="amazon") — JSON-lines:

   data/sample/amazon_reviews_sample.json
   {"reviewerID":"A1X","asin":"B001","reviewText":"Good product",
    "overall":5.0,"summary":"Great buy","unixReviewTime":1609459200,
    "reviewerName":"John D."}

   No separate items file — derive item records from unique asin values
   found within the reviews file itself using summary + asin as metadata.

3. Goodreads (platform="goodreads") — JSON-lines:

   data/sample/goodreads_reviews_sample.json
   {"user_id":"u1","book_id":"b1","rating":4,
    "review_text":"Loved this book...","date_added":"Thu Jan 01 2022",
    "spoiler_tag": 0}

   data/sample/goodreads_books_sample.json
   {"book_id":"b1","title":"Some Book","authors":[{"author_id":"1",
    "role":""}],"genres":[{"count":50,"name":"fiction"}],
    "description":"A story about...","average_rating":"4.2",
    "language_code":"eng"}

COLLECTIONS TO BUILD IN CHROMADB:

  users:
    id        = "{platform}_{user_id}"
    embedding = embed(style fingerprint summary text)
    metadata  = {platform, avg_rating, review_count, top_categories,
                 avg_review_length, vocabulary_size}

  items:
    id        = "{platform}_{item_id}"
    embedding = embed(item name + description + category)
    metadata  = {platform, category, avg_rating, name}

  reviews:
    id        = "{platform}_{review_id}"   # use index if no review_id
    embedding = embed(review_text)
    metadata  = {user_id, item_id, rating (float), platform,
                 is_test_split (bool as "true"/"false" string)}

SAMPLING STRATEGY (already done — do not re-sample):
  Files are pre-filtered to users with 10–50 reviews.
  Apply 80/20 train/test split per user at ingestion time.
  The 20% held-out reviews get metadata is_test_split="true".
</project_context>

<task>
Implement these files completely:

1. data/yelp_processor.py
   - Reads all 3 Yelp sample files
   - Joins reviews → users → businesses
   - Returns (users: list[UserProfile], items: list[ItemRecord],
     reviews: list[ReviewRecord])
   - top_categories derived from business categories field (split by ", ")

2. data/amazon_processor.py
   - Reads amazon_reviews_sample.json only (no separate items file)
   - Derives ItemRecord per unique asin from reviews data
     (name = most common summary for that asin, category = "Electronics")
   - Returns (users, items, reviews)

3. data/goodreads_processor.py
   - Reads both goodreads sample files
   - Joins reviews → books for item metadata
   - authors field is a list of dicts: extract first author_id only
   - genres field is a list of dicts: extract top 3 by count
   - Returns (users, items, reviews)

4. data/ingest.py — master orchestration script:
   a) Parses CLI args: --sample-only (process first 100 users per dataset),
      --skip-yelp, --skip-amazon, --skip-goodreads (for partial runs)
   b) Calls all three processors (respecting skip flags)
   c) Deduplicates across platforms by id before inserting to ChromaDB
   d) Builds all three ChromaDB collections with embeddings
      (batch inserts of 100 documents at a time to avoid memory spikes)
   e) Saves train/test split manifest to data/splits.json:
      {"yelp": {"train": [review_ids], "test": [review_ids]}, ...}
   f) Prints final stats table:
      Platform | Users | Items | Reviews | Test Reviews

5. data/create_samples.py — generates 100-row mini JSONs for each of the
   6 sample files matching the exact formats above (for CI/unit testing
   without real data). Saves to data/sample/test_fixtures/.

<constraints>
- Stream all file reads line by line — never load a full file into memory
- Use tqdm progress bars on all file reads
- shared/embeddings.py already exists — import and use it, do not rewrite it
- shared/user_profile.py, shared/schemas.py already exist — import from them
- If a sample file is missing, log a warning with the expected path and skip
- All file paths must come from environment variables with these defaults:
    YELP_REVIEWS_PATH   = "data/sample/yelp_reviews_sample.json"
    YELP_USERS_PATH     = "data/sample/yelp_users_sample.json"
    YELP_BUSINESS_PATH  = "data/sample/yelp_business_sample.json"
    AMAZON_REVIEWS_PATH = "data/sample/amazon_reviews_sample.json"
    GR_REVIEWS_PATH     = "data/sample/goodreads_reviews_sample.json"
    GR_BOOKS_PATH       = "data/sample/goodreads_books_sample.json"
    CHROMA_PERSIST_DIR  = "chroma_data"
- Batch size for ChromaDB inserts: 100 documents per batch
- 80/20 split is per-user, deterministic (use sorted review order, 
  last 20% = test). Do NOT use random shuffle (reproducibility).
- is_test_split stored as string "true"/"false" (ChromaDB metadata 
  does not support booleans)
- All UserProfile, ItemRecord, ReviewRecord construction must use 
  the existing dataclasses — do not redefine them inline
</constraints>

<output_format>
Output each file completely with its path as a comment header.
Include type hints and docstrings on every function and class.
No truncation. No placeholders.
</output_format>