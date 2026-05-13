import json
from collections import defaultdict

INPUT  = "goodreads_data/goodreads_reviews_spoiler_raw.json"
OUTPUT = "data/sample/goodreads_reviews_sample.json"

TARGET_USERS   = 2000
MIN_REVIEWS    = 10
MAX_REVIEWS    = 50
MAX_SCAN_LINES = 500000   # stop scanning after this to save time

print("Pass 1 — counting reviews per user...")
user_counts = defaultdict(int)
with open(INPUT, "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        if i >= MAX_SCAN_LINES:
            break
        try:
            obj = json.loads(line)
            uid = obj.get("user_id")
            if uid:
                user_counts[uid] += 1
        except:
            continue

# Pick users with 10–50 reviews
eligible = [u for u, c in user_counts.items() if MIN_REVIEWS <= c <= MAX_REVIEWS]
selected = set(eligible[:TARGET_USERS])
print(f"Eligible users: {len(eligible)} | Selected: {len(selected)}")

print("Pass 2 — writing sample file...")
written = 0
user_review_counts = defaultdict(int)

with open(INPUT, "r", encoding="utf-8") as fin, \
     open(OUTPUT, "w", encoding="utf-8") as fout:
    for i, line in enumerate(fin):
        if i >= MAX_SCAN_LINES:
            break
        try:
            obj = json.loads(line)
            uid = obj.get("user_id")
            if uid in selected and user_review_counts[uid] < MAX_REVIEWS:
                fout.write(line)
                user_review_counts[uid] += 1
                written += 1
        except:
            continue

print(f"Done. {written} reviews written to {OUTPUT}")