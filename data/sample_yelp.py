import json

def sample_json_lines(input_path, output_path, max_lines=50000):
    """Extract first N lines from a large JSON-lines file."""
    count = 0
    with open(input_path, 'r', encoding='utf-8') as fin, \
         open(output_path, 'w', encoding='utf-8') as fout:
        for line in fin:
            if count >= max_lines:
                break
            fout.write(line)
            count += 1
    print(f"Saved {count} records to {output_path}")
    
# Run these one by one
sample_json_lines(
    'yelp_data/yelp_academic_dataset_review.json',
    'data/sample/yelp_reviews_sample.json',
    max_lines=100000   # 100k reviews
)

sample_json_lines(
    'yelp_data/yelp_academic_dataset_user.json', 
    'data/sample/yelp_users_sample.json',
    max_lines=10000    # 10k users
)

sample_json_lines(
    'yelp_data/yelp_academic_dataset_business.json',
    'data/sample/yelp_business_sample.json',
    max_lines=20000    # 20k businesses
)