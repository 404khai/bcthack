import json
from collections import defaultdict

INPUT  = "data/sample/amazon_electronics_reviews.JSON"
OUTPUT = "data/sample/amazon_reviews_sample.json"

TARGET_USERS = 2000
MIN_REVIEWS  = 10
MAX_REVIEWS  = 50
MAX_SCAN     = 1000000   # scan up to 1M lines from the 1.37GB file

print("Pass 1 — counting reviews per reviewer...")
user_counts = defaultdict(int)

with open(INPUT, "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        if i >= MAX_SCAN:
            break
        line = line.strip().rstrip(",")   # some Amazon files have trailing commas
        if not line or line in ("[", "]"):
            continue
        try:
            obj = json.loads(line)
            uid = obj.get("reviewerID")
            if uid:
                user_counts[uid] += 1
        except:
            continue

eligible = [u for u, c in user_counts.items() if MIN_REVIEWS <= c <= MAX_REVIEWS]
selected = set(eligible[:TARGET_USERS])
print(f"Eligible reviewers: {len(eligible)} | Selected: {len(selected)}")

print("Pass 2 — writing sample file...")
written = 0
user_review_counts = defaultdict(int)

with open(INPUT, "r", encoding="utf-8") as fin, \
     open(OUTPUT, "w", encoding="utf-8") as fout:
    for i, line in enumerate(fin):
        if i >= MAX_SCAN:
            break
        line = line.strip().rstrip(",")
        if not line or line in ("[", "]"):
            continue
        try:
            obj = json.loads(line)
            uid = obj.get("reviewerID")
            if uid in selected and user_review_counts[uid] < MAX_REVIEWS:
                fout.write(json.dumps(obj) + "\n")
                user_review_counts[uid] += 1
                written += 1
        except:
            continue

print(f"Done. {written} reviews written to {OUTPUT}")