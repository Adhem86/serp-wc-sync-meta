import os
import requests
import json
from time import sleep

SERPAPI_KEY = os.environ.get("SERPAPI_KEY")
WC_BASE = os.environ.get("WC_BASE").rstrip('/')
WC_KEY = os.environ.get("WC_KEY")
WC_SECRET = os.environ.get("WC_SECRET")
MAX_ITEMS = int(os.environ.get("MAX_ITEMS", 5))
QUERY = os.environ.get("QUERY", "best sellers")
MAX_PRODUCT_PAGES = int(os.environ.get("MAX_PRODUCT_PAGES", 3))
WC_PER_PAGE = int(os.environ.get("WC_PER_PAGE", 100))

def get_serpapi_products(query, max_items=5):
    url = f"https://serpapi.com/search.json?q={query}&engine=amazon&api_key={SERPAPI_KEY}"
    response = requests.get(url)
    data = response.json()
    products = data.get("shopping_results", [])
    return products[:max_items]

def wc_headers():
    return {
        "Content-Type": "application/json"
    }

def get_wc_products(page=1, per_page=100):
    url = f"{WC_BASE}/wp-json/wc/v3/products?page={page}&per_page={per_page}"
    r = requests.get(url, auth=(WC_KEY, WC_SECRET))
    return r.json() if r.status_code==200 else []

def find_wc_product_by_source_id(source_id):
    page = 1
    while page <= MAX_PRODUCT_PAGES:
        products = get_wc_products(page, WC_PER_PAGE)
        if not products:
            break
        for p in products:
            meta = p.get("meta_data", [])
            for m in meta:
                if m.get("key")=="source_id" and m.get("value")==source_id:
                    return p
        page += 1
    return None

def create_or_update_wc_product(product):
    source_id = product.get("id")
    existing = find_wc_product_by_source_id(source_id)
    payload = {
        "name": product.get("title"),
        "type": "external",
        "regular_price": str(product.get("price", "0")),
        "external_url": product.get("link"),
        "meta_data": [
            {"key": "source_id", "value": source_id},
            {"key": "source", "value": "amazon"}
        ]
    }
    if existing:
        url = f"{WC_BASE}/wp-json/wc/v3/products/{existing['id']}"
        r = requests.put(url, auth=(WC_KEY, WC_SECRET), headers=wc_headers(), data=json.dumps(payload))
        print(f"Updated: {payload['name']} ({r.status_code})")
    else:
        url = f"{WC_BASE}/wp-json/wc/v3/products"
        r = requests.post(url, auth=(WC_KEY, WC_SECRET), headers=wc_headers(), data=json.dumps(payload))
        print(f"Created: {payload['name']} ({r.status_code})")
    sleep(1)  # لتجنب الحظر أو مشاكل Rate Limit

def main():
    def main():
    products = get_serpapi_products(QUERY, MAX_ITEMS)
    print(f"Found {len(products)} products from SerpApi.")
    for p in products:
        print(json.dumps(p, indent=2))  # عرض كامل بيانات المنتج
        create_or_update_wc_product(p)

if __name__ == "__main__":
    main()
