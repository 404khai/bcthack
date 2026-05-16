Test 1 - Warm Yelp User (full history, restaurant recommendation)
{
  "user_persona": {
    "user_id": "yelp__BcWyKQL16ndpBdggh2kNA",
    "platform": "yelp",
    "preferences": {},
    "history": [],
    "persona_text": ""
  },
  "query": "I want somewhere good to eat tonight",
  "request_context": {
    "category": "restaurants",
    "target_domain": "food",
    "item_attributes": {},
    "constraints": []
  },
  "top_k": 5,
  "session_id": "session_test_001",
  "nigerian_mode": false,
  "enable_cross_domain": false
}

RESPONSE:
{
  "user_id": "yelp__BcWyKQL16ndpBdggh2kNA",
  "recommendations": [
    {
      "item": {
        "item_id": "explicit-1",
        "title": "Starter match for restaurants",
        "category": "restaurants",
        "source": "explicit_preference",
        "similarity_score": 0.862,
        "metadata": {
          "preference": "restaurants",
          "weight": 0.78
        }
      },
      "score": 9.62,
      "explanation": "Starter match for restaurants fits the request because it aligns with restaurants and the user's known preferences.",
      "confidence": 0.862
    },
    {
      "item": {
        "item_id": "popular-local",
        "title": "Popular Local Discovery",
        "category": "experience",
        "source": "popularity",
        "similarity_score": 0.585,
        "metadata": {
          "fallback": true
        }
      },
      "score": 5.85,
      "explanation": "Popular Local Discovery fits the request because it aligns with restaurants and the user's known preferences.",
      "confidence": 0.585
    },
    {
      "item": {
        "item_id": "city-favorite",
        "title": "City Favorite Pick",
        "category": "experience",
        "source": "popularity",
        "similarity_score": 0.549,
        "metadata": {
          "fallback": true
        }
      },
      "score": 5.49,
      "explanation": "City Favorite Pick fits the request because it aligns with restaurants and the user's known preferences.",
      "confidence": 0.549
    }
  ],
  "thinking": [
    "Think: interpret the query as 'I want somewhere good to eat tonight' with target category 'restaurants'.",
    "Think: user history contains 0 prior interactions, so the request is treated as cold start.",
    "Plan: explicit persona preferences are not provided and conversation refinements are none yet.",
    "Plan: constraints considered before retrieval are ['none'] and attributes not provided.",
    "Plan: use explicit preferences, Nigerian defaults, and popularity fallback because history is sparse."
  ],
  "strategy": "cold_start_hybrid",
  "session_id": "session_test_001",
  "nigerian_mode": false
}


Test 2 — Cold User (no history, Nigerian mode)
{
  "user_persona": {
    "user_id": "cold_user_lagos_001",
    "platform": "unknown",
    "preferences": {},
    "history": [],
    "persona_text": "I enjoy trying local restaurants, prefer spicy food, and care about value for money"
  },
  "query": "Recommend me somewhere to eat in Lagos",
  "request_context": {
    "category": "restaurants",
    "target_domain": "food",
    "item_attributes": {},
    "constraints": ["spicy", "affordable"]
  },
  "top_k": 5,
  "session_id": "session_test_002",
  "nigerian_mode": true,
  "enable_cross_domain": false
}

RESPONSE:
{
  "user_id": "cold_user_lagos_001",
  "recommendations": [
    {
      "item": {
        "item_id": "explicit-1",
        "title": "Starter match for restaurants",
        "category": "restaurants",
        "source": "explicit_preference",
        "similarity_score": 0.862,
        "metadata": {
          "preference": "restaurants",
          "weight": 0.78
        }
      },
      "score": 9.62,
      "explanation": "Ah, my dear! See, this recommendation for 'restaurants'? It's a proper fit, you hear? Exactly what you asked for, no two ways about it. But more than that",
      "confidence": 0.862
    },
    {
      "item": {
        "item_id": "explicit-2",
        "title": "Starter match for spicy flavors",
        "category": "restaurants",
        "source": "explicit_preference",
        "similarity_score": 0.838,
        "metadata": {
          "preference": "spicy flavors",
          "weight": 0.72
        }
      },
      "score": 9.38,
      "explanation": "Ah, my dear! When it comes to kicking off a good meal, especially in a proper restaurant setting, we've got just the thing for you.\n\nYou see, this particular",
      "confidence": 0.838
    },
    {
      "item": {
        "item_id": "ng-default-0",
        "title": "Lagos popular spots",
        "category": "restaurants",
        "source": "nigerian_default",
        "similarity_score": 0.8,
        "metadata": {
          "fallback": true
        }
      },
      "score": 9,
      "explanation": "Ah, my dear friend, let me tell you about 'Lagos popular spots'! This one? It's a fantastic fit, no doubt at all.\n\nYou see, when we talk about '",
      "confidence": 0.8
    },
    {
      "item": {
        "item_id": "ng-default-1",
        "title": "Trending Naija picks",
        "category": "restaurants",
        "source": "nigerian_default",
        "similarity_score": 0.8,
        "metadata": {
          "fallback": true
        }
      },
      "score": 9,
      "explanation": "Ah, my dear! This 'Trending Naija Picks'? *Exactly* what we had in mind for you!\n\nYou know how much we love our food, eh? This one is all about the",
      "confidence": 0.8
    },
    {
      "item": {
        "item_id": "popular-local",
        "title": "Popular Local Discovery",
        "category": "experience",
        "source": "popularity",
        "similarity_score": 0.585,
        "metadata": {
          "fallback": true
        }
      },
      "score": 5.85,
      "explanation": "Ah, my dear! When we looked at your request, this 'Popular Local Discovery' just jumped out at us, like a delicious aroma from a neighbour's kitchen!\n\nSee ehn,",
      "confidence": 0.585
    }
  ],
  "thinking": [
    "Think: interpret the query as 'Recommend me somewhere to eat in Lagos' with target category 'restaurants'.",
    "Think: user history contains 0 prior interactions, so the request is treated as cold start.",
    "Plan: explicit persona preferences are not provided and conversation refinements are none yet.",
    "Plan: constraints considered before retrieval are ['spicy', 'affordable'] and attributes not provided.",
    "Plan: use explicit preferences, Nigerian defaults, and popularity fallback because history is sparse."
  ],
  "strategy": "cold_start_hybrid",
  "session_id": "session_test_002",
  "nigerian_mode": true
}

Test 3 — Cross Domain (Goodreads user → food recommendation)
{
  "user_persona": {
    "user_id": "goodreads_e760fa37bf7785643c9b4116ad46d550",
    "platform": "goodreads",
    "preferences": {},
    "history": [],
    "persona_text": ""
  },
  "query": "Based on my reading taste, what food or restaurants would I enjoy?",
  "request_context": {
    "category": "restaurants",
    "target_domain": "food",
    "item_attributes": {},
    "constraints": []
  },
  "top_k": 5,
  "session_id": "session_test_003",
  "nigerian_mode": false,
  "enable_cross_domain": true
}

RESPONSE:
{
  "user_id": "goodreads_e760fa37bf7785643c9b4116ad46d550",
  "recommendations": [
    {
      "item": {
        "item_id": "explicit-1",
        "title": "Starter match for restaurants",
        "category": "restaurants",
        "source": "explicit_preference",
        "similarity_score": 0.862,
        "metadata": {
          "preference": "restaurants",
          "weight": 0.78
        }
      },
      "score": 9.62,
      "explanation": "Starter match for restaurants fits the request because it aligns with restaurants and the user's known preferences.",
      "confidence": 0.862
    },
    {
      "item": {
        "item_id": "popular-local",
        "title": "Popular Local Discovery",
        "category": "experience",
        "source": "popularity",
        "similarity_score": 0.585,
        "metadata": {
          "fallback": true
        }
      },
      "score": 5.85,
      "explanation": "Popular Local Discovery fits the request because it aligns with restaurants and the user's known preferences.",
      "confidence": 0.585
    },
    {
      "item": {
        "item_id": "city-favorite",
        "title": "City Favorite Pick",
        "category": "experience",
        "source": "popularity",
        "similarity_score": 0.549,
        "metadata": {
          "fallback": true
        }
      },
      "score": 5.49,
      "explanation": "City Favorite Pick fits the request because it aligns with restaurants and the user's known preferences.",
      "confidence": 0.549
    }
  ],
  "thinking": [
    "Think: interpret the query as 'Based on my reading taste, what food or restaurants would I enjoy?' with target category 'restaurants'.",
    "Think: user history contains 0 prior interactions, so the request is treated as cold start.",
    "Plan: explicit persona preferences are not provided and conversation refinements are none yet.",
    "Plan: constraints considered before retrieval are ['none'] and attributes not provided.",
    "Plan: use explicit preferences, Nigerian defaults, and popularity fallback because history is sparse."
  ],
  "strategy": "cold_start_hybrid",
  "session_id": "session_test_003",
  "nigerian_mode": false
}

Test 4 — Amazon User → Cross Domain to Books
{
  "user_persona": {
    "user_id": "amazon_A1K4G5YJDJQI6Q",
    "platform": "amazon",
    "preferences": {},
    "history": [],
    "persona_text": ""
  },
  "query": "Recommend me some books or movies I might enjoy",
  "request_context": {
    "category": "books",
    "target_domain": "books",
    "item_attributes": {},
    "constraints": []
  },
  "top_k": 5,
  "session_id": "session_test_004",
  "nigerian_mode": false,
  "enable_cross_domain": true
}

RESPONSE:
{
  "user_id": "amazon_A1K4G5YJDJQI6Q",
  "recommendations": [
    {
      "item": {
        "item_id": "explicit-1",
        "title": "Starter match for books",
        "category": "books",
        "source": "explicit_preference",
        "similarity_score": 0.862,
        "metadata": {
          "preference": "books",
          "weight": 0.78
        }
      },
      "score": 9.62,
      "explanation": "Starter match for books fits the request because it aligns with books and the user's known preferences.",
      "confidence": 0.862
    },
    {
      "item": {
        "item_id": "popular-local",
        "title": "Popular Local Discovery",
        "category": "experience",
        "source": "popularity",
        "similarity_score": 0.585,
        "metadata": {
          "fallback": true
        }
      },
      "score": 5.85,
      "explanation": "Popular Local Discovery fits the request because it aligns with books and the user's known preferences.",
      "confidence": 0.585
    },
    {
      "item": {
        "item_id": "city-favorite",
        "title": "City Favorite Pick",
        "category": "experience",
        "source": "popularity",
        "similarity_score": 0.549,
        "metadata": {
          "fallback": true
        }
      },
      "score": 5.49,
      "explanation": "City Favorite Pick fits the request because it aligns with books and the user's known preferences.",
      "confidence": 0.549
    }
  ],
  "thinking": [
    "Think: interpret the query as 'Recommend me some books or movies I might enjoy' with target category 'books'.",
    "Think: user history contains 0 prior interactions, so the request is treated as cold start.",
    "Plan: explicit persona preferences are not provided and conversation refinements are none yet.",
    "Plan: constraints considered before retrieval are ['none'] and attributes not provided.",
    "Plan: use explicit preferences, Nigerian defaults, and popularity fallback because history is sparse."
  ],
  "strategy": "cold_start_hybrid",
  "session_id": "session_test_004",
  "nigerian_mode": false
}


