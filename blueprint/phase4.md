PHASE 4 PROMPT — Data Pipeline & ChromaDB Ingestion
<role>
You are a Data Engineer who builds reliable, memory-efficient ETL pipelines 
for large JSON datasets. You are pragmatic: you know how to sample intelligently 
for hackathon purposes without sacrificing representative coverage.
</role>

<project_context>
We need to ingest three datasets into ChromaDB collections:
  - "users" collection: user profiles with style fingerprints
  - "items" collection: items/businesses/books/products with attributes
  - "reviews" collection: individual reviews linked to users and items

Datasets and their formats:
  1. Yelp Open Dataset (yelp_academic_dataset_review.json, 
     yelp_academic_dataset_business.json, yelp_academic_dataset_user.json)
     Each line is a JSON object.
     
  2. Amazon Reviews — use the "Electronics" or "Books" subset from 
     https://nijianmo.github.io/amazon/index.html
     Format: one JSON per line, fields: reviewerID, asin, reviewText, 
     overall (rating), summary, unixReviewTime
     
  3. Goodreads — use goodreads_reviews_spoiler_raw.json.gz subset
     Fields: user_id, book_id, rating, review_text, date_added

Sampling strategy for hackathon:
  - Take users with 10–50 reviews (active but not bots)
  - Sample 2,000 users per dataset (6,000 total)
  - For each user, keep all their reviews (capped at 50 most recent)
  - This gives ~100k–200k reviews total — manageable
  - Create an 80/20 train/test split per user (held-out for evaluation)
</project_context>

<task>
Implement these files completely:

1. data/yelp_processor.py
2. data/amazon_processor.py  
3. data/goodreads_processor.py
4. data/ingest.py — master script that:
   a) Runs all three processors
   b) Builds ChromaDB collections: users, items, reviews
   c) Generates embeddings using shared/embeddings.py
   d) Saves a train/test split manifest as data/splits.json
   e) Prints ingestion statistics at completion

Each processor must output:
  - list[UserProfile] (using shared/user_profile.py)
  - list[ItemRecord] (define in shared/schemas.py)
  - list[ReviewRecord] (define in shared/schemas.py)

ChromaDB document structure:
  - users collection: id=user_id, embedding=style_fingerprint_text_embedding,
    metadata={platform, avg_rating, review_count, top_categories}
  - items collection: id=item_id, embedding=item_description_embedding,
    metadata={platform, category, avg_rating, name}
  - reviews collection: id=review_id, embedding=review_text_embedding,
    metadata={user_id, item_id, rating, platform, is_test_split}

<constraints>
- Use streaming JSON parsing (ijson or line-by-line) — do NOT load full files 
  into memory
- Show a tqdm progress bar
- If a dataset file doesn't exist, log a warning and skip (graceful degradation)
- Include a --sample-only flag that processes only the first 100 users 
  (for fast local testing)
- All paths configurable via environment variables with sensible defaults
- Add a data/create_samples.py script that creates 100-row sample JSONs 
  matching each format (for CI/testing without real datasets)
</constraints>

<output_format>
Full files. Include a sample JSON structure comment at the top of each 
processor showing the expected input format.
</output_format>