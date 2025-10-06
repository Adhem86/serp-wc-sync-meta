import os
import requests
import json
from time import sleep

SERPAPI_KEY = os.environ.get("SERPAPI_KEY")
WC_BASE = os.environ.get("WC_BASE").rstrip('/')
WC_KEY = os.environ.get("WC_KEY")
WC_SECRET = os.environ.get("WC_SECRET")
MAX_ITEMS = int(os.environ.get("MAX_ITEMS", 5))
QUERY = os.environ.get("QUERY", "Best-Sellers")
MAX_PRODUCT_PAGES = int(os.environ.get("MAX_PRODUCT_PAGES", 3))
WC_PER_PAGE = int(os.environ.get("WC_PER_PAGE", 100))
WC_TIMEOUT = 15

def get_serpapi_products(query, max_items=5):
    amazon_domain = "amazon.com"  # يمكن تغييره حسب الموقع
    url = f"https://serpapi.com/search.json?engine=amazon&k={query}&amazon_domain={amazon_domain}&api_key={SERPAPI_KEY}"
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

def debug_print_response(r):
    try:
        body = r.json()
    except Exception:
        body = r.text
    print(">>> WC RESPONSE STATUS:", getattr(r, "status_code", "NO_STATUS"))
    print(">>> WC RESPONSE BODY SNIPPET:", json.dumps(body)[:2000])

def create_product(payload):
    url = f"{WC_BASE}/wp-json/wc/v3/products"
    headers = {"Content-Type": "application/json"}
    # Use consumer_key & consumer_secret as query params (fallback or default)
    params = {"consumer_key": WC_KEY, "consumer_secret": WC_SECRET}
    try:
        r = requests.post(url, params=params, headers=headers, json=payload, timeout=WC_TIMEOUT)
        debug_print_response(r)
        if r.status_code in (200,201):
            return {"ok": True, "status": r.status_code, "body": r.json()}
        return {"ok": False, "status": r.status_code, "body": r.text}
    except Exception as e:
        print("[error] create_product failed:", e)
        return {"ok": False, "status": "exception", "body": str(e)}

def update_product(product_id, payload):
    url = f"{WC_BASE}/wp-json/wc/v3/products/{product_id}"
    headers = {"Content-Type": "application/json"}
    params = {"consumer_key": WC_KEY, "consumer_secret": WC_SECRET}
    try:
        r = requests.put(url, params=params, headers=headers, json=payload, timeout=WC_TIMEOUT)
        debug_print_response(r)
        if r.status_code in (200,201):
            return {"ok": True, "status": r.status_code, "body": r.json()}
        return {"ok": False, "status": r.status_code, "body": r.text}
    except Exception as e:
        print("[error] update_product failed:", e)
        return {"ok": False, "status": "exception", "body": str(e)}

def main():
    products = get_serpapi_products(QUERY, MAX_ITEMS)
    print(f"Found {len(products)} products from SerpApi.")
    for p in products:
        print(json.dumps(p, indent=2))  # عرض كامل بيانات المنتج
        create_or_update_wc_product(p)

if __name__ == "__main__":
    main()
