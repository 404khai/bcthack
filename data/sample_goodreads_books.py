import json

INPUT  = "goodreads_data/goodreads_books.json"
OUTPUT = "data/sample/goodreads_books_sample.json"
MAX_BOOKS = 30000   # 30k books is more than enough

print("Sampling goodreads books...")
written = 0

with open(INPUT, "r", encoding="utf-8") as fin, \
     open(OUTPUT, "w", encoding="utf-8") as fout:
    for i, line in enumerate(fin):
        if written >= MAX_BOOKS:
            break
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            # Keep only fields we actually need
            slim = {
                "book_id":      obj.get("book_id"),
                "title":        obj.get("title"),
                "authors":      obj.get("authors", []),
                "genres":       obj.get("popular_shelves", [])[:5],
                "description":  obj.get("description", "")[:500],
                "average_rating": obj.get("average_rating"),
                "language_code":  obj.get("language_code"),
            }
            if slim["book_id"] and slim["title"]:
                fout.write(json.dumps(slim) + "\n")
                written += 1
        except:
            continue

print(f"Done. {written} books written to {OUTPUT}")