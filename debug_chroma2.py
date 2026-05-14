# save as debug_chroma.py in project root
import chromadb

client = chromadb.PersistentClient(path="./chroma_db")

# add to debug_chroma.py
users = client.get_collection("users")
all_users = users.get(limit=394)
rich_users = [
    (uid, meta) 
    for uid, meta in zip(all_users["ids"], all_users["metadatas"])
    if int(meta.get("review_count", 0)) > 5
]
rich_users.sort(key=lambda x: int(x[1].get("review_count", 0)), reverse=True)
for uid, meta in rich_users[:5]:
    print(f"{uid} | reviews: {meta.get('review_count')} | platform: {meta.get('platform')} | categories: {meta.get('top_categories')}")

# Get real item IDs
items = client.get_collection("items")
sample_items = items.get(limit=5)
print("\n=== ITEMS ===")
for i, iid in enumerate(sample_items["ids"]):
    meta = sample_items["metadatas"][i]
    print(f"ID: {iid} | name: {meta.get('name')} | category: {meta.get('category')} | platform: {meta.get('platform')}")

# Get reviews for a specific user
reviews = client.get_collection("reviews")
print(f"\n=== TOTAL REVIEWS: {reviews.count()} ===")