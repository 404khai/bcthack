<context>
eval/run_task_b_eval.py sends user_ids to the /recommend endpoint
but every user returns "0 stored interactions, treated as cold start"
even users with 23 reviews in ChromaDB.

The eval loads users from ChromaDB where IDs are like:
  "yelp_RreNy--tOmXMl1en0wiBOg"
  "yelp_IKbjLnfBQtEyVzEu8CuOLg"

But the service's warm user detection queries ChromaDB for 
review_count using the user_id from the request payload.

The service stores users with IDs like:
  "yelp__BcWyKQL16ndpBdggh2kNA" (confirmed working in manual tests)

The eval payload currently sends:
  "user_id": "yelp_RreNy--tOmXMl1en0wiBOg"

But it should send exactly the ChromaDB document ID as-is.

Also: the eval query is generic "recommend something based on my history"
which triggers "unknown" category. The eval should use the user's
actual top_categories from ChromaDB metadata as the query.

Fix eval/run_task_b_eval.py:

1. When building payload, use the exact ChromaDB document ID 
   as user_id — do not strip or modify it:
   "user_id": user["user_id"]  # already correct from ChromaDB get()

2. Use user's real top_categories for the query and category:
   top_cats = (user["metadata"] or {}).get("top_categories", "")
   first_cat = top_cats.split(",")[0].strip() if top_cats else "restaurants"
   
   payload query: f"Recommend {first_cat} based on my history"
   payload request_context.category: first_cat

3. Add a pre-flight check: before running eval, test one user 
   manually and log what the service returns:
   logger.info("Pre-flight: testing user %s", test_users[0]["user_id"])
   r = requests.post(url, json=build_payload(test_users[0]), timeout=60)
   logger.info("Pre-flight thinking: %s", 
               r.json().get("thinking", [])[:2])
   
   This will show in logs whether the service sees the user as warm or cold.

Output the complete fixed file.
</context>