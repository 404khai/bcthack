1) Test 1 — Rich Yelp User (65 reviews, best behavioral signal)
{
  "user_persona": {
    "user_id": "yelp__BcWyKQL16ndpBdggh2kNA",
    "platform": "yelp",
    "review_history": [],
    "preferences": {}
  },
  "item_details": {
    "item_id": "yelp_8c0r7olQSYGcws0bTd3ikw",
    "name": "Zesty Tsunami",
    "category": "Hawaiian",
    "attributes": {
      "price_range": "mid-range",
      "location": "Las Vegas",
      "cuisine": "Hawaiian Fusion"
    }
  },
  "nigerian_mode": false,
  "nigerian_intensity": "medium"
}

RESPONSE
{
  "user_id": "yelp__BcWyKQL16ndpBdggh2kNA",
  "item_id": "yelp_8c0r7olQSYGcws0bTd3ikw",
  "rating": 3.9,
  "review_text": "Stopped by Zesty Tsunami in Las Vegas for a quick lunch. The Hawaiian Fusion idea sounded promising. I tried a poke bowl – the ingredients were fresh, but the overall flavor profile was a bit understated",
  "confidence": 0.385,
  "style_notes": "Avg rating 3.62, rating std 0.00, avg length 78.1 words, formality 0.50, top phrases: no repeated phrases, Nigerian signals: none detected.",
  "style_fingerprint": {
    "avg_rating": 3.615,
    "rating_std": 0,
    "avg_review_length": 78.09,
    "vocabulary_size": 1632,
    "top_phrases": [],
    "sentiment_profile": {
      "positive": 0.34,
      "neutral": 0.33,
      "negative": 0.33
    },
    "formality_score": 0.5,
    "nigerian_signals": []
  },
  "nigerian_mode": false
}

2) Test 2 — Same User, Nigerian Mode ON
{
  "user_persona": {
    "user_id": "yelp__BcWyKQL16ndpBdggh2kNA",
    "platform": "yelp",
    "review_history": [],
    "preferences": {}
  },
  "item_details": {
    "item_id": "new_item_002",
    "name": "Chicken Republic Lekki",
    "category": "Fast Food",
    "attributes": {
      "price_range": "budget",
      "location": "Lagos",
      "cuisine": "Nigerian Fast Food"
    }
  },
  "nigerian_mode": true,
  "nigerian_intensity": "medium"
}

RESPONSE 1st try
{
  "user_id": "yelp__BcWyKQL16ndpBdggh2kNA",
  "item_id": "new_item_002",
  "rating": 3.5,
  "review_text": "I quickly popped into Chicken Republic at Lekki, just to grab",
  "confidence": 0.254,
  "style_notes": "Avg rating 3.62, rating std 0.00, avg length 78.1 words, formality 0.50, top phrases: no repeated phrases, Nigerian signals: none detected.",
  "style_fingerprint": {
    "avg_rating": 3.615,
    "rating_std": 0,
    "avg_review_length": 78.09,
    "vocabulary_size": 1632,
    "top_phrases": [],
    "sentiment_profile": {
      "positive": 0.34,
      "neutral": 0.33,
      "negative": 0.33
    },
    "formality_score": 0.5,
    "nigerian_signals": []
  },
  "nigerian_mode": true
}

RESPONSE 2nd try
{
  "user_id": "yelp__BcWyKQL16ndpBdggh2kNA",
  "item_id": "new_item_002",
  "rating": 3.9,
  "review_text": "Chicken Republic Lekki is actually a solid choice if you'",
  "confidence": 0.235,
  "style_notes": "Avg rating 3.62, rating std 0.00, avg length 78.1 words, formality 0.50, top phrases: no repeated phrases, Nigerian signals: none detected.",
  "style_fingerprint": {
    "avg_rating": 3.615,
    "rating_std": 0,
    "avg_review_length": 78.09,
    "vocabulary_size": 1632,
    "top_phrases": [],
    "sentiment_profile": {
      "positive": 0.34,
      "neutral": 0.33,
      "negative": 0.33
    },
    "formality_score": 0.5,
    "nigerian_signals": []
  },
  "nigerian_mode": true
}

3) Test 3 — Amazon User
{
  "user_persona": {
    "user_id": "amazon_A1K4G5YJDJQI6Q",
    "platform": "amazon",
    "review_history": [],
    "preferences": {}
  },
  "item_details": {
    "item_id": "new_item_003",
    "name": "Anker PowerBank 20000mAh",
    "category": "Electronics",
    "attributes": {
      "price_range": "mid-range",
      "brand": "Anker",
      "use_case": "charging"
    }
  },
  "nigerian_mode": false,
  "nigerian_intensity": "medium"
}

RESPONSE 
{
  "user_id": "amazon_A1K4G5YJDJQI6Q",
  "item_id": "new_item_003",
  "rating": 3.9,
  "review_text": "Having a portable charger is pretty much essential these days, so I picked up the Anker 20000mAh power bank hoping it would be a solid option for keeping my devices",
  "confidence": 0.159,
  "style_notes": "Avg rating 2.80, rating std 0.00, avg length 285.8 words, formality 0.50, top phrases: no repeated phrases, Nigerian signals: none detected.",
  "style_fingerprint": {
    "avg_rating": 2.8,
    "rating_std": 0,
    "avg_review_length": 285.8,
    "vocabulary_size": 1788,
    "top_phrases": [],
    "sentiment_profile": {
      "positive": 0.34,
      "neutral": 0.33,
      "negative": 0.33
    },
    "formality_score": 0.5,
    "nigerian_signals": []
  },
  "nigerian_mode": false
}