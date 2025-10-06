import os
import json
import time
import hashlib
import requests

# ---------- إعدادات من البيئة ----------
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "").strip()
WC_BASE = os.environ.get("WC_BASE", "").strip().rstrip("/")
WC_KEY = os.environ.get("WC_KEY", "").strip()
WC_SECRET = os.environ.get("WC_SECRET", "").strip()
MAX_ITEMS = int(os.environ.get("MAX_ITEMS", "5"))
QUERY = os.environ.get("QUERY", "best sellers")
MAX_PRODUCT_PAGES = int(os.environ.get("MAX_PRODUCT_PAGES", "3"))
WC_PER_PAGE = int(os.environ.get("WC_PER_PAGE", "100"))

WC_TIMEOUT = 15

# ---------- دوال HTTP آمنة ومخصصة لاستخدام query params ----------
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
    params = {"consumer_key": WC_KEY, "consumer_secret": WC_SECRET}
    try:
        r = requests.post(url, params=params, headers=headers, json=payload, timeout=WC_TIMEOUT)
        debug_print_response(r)
        if r.status_code in (200, 201):
            return {"ok": True, "status": r.status_code, "body": r.json()}
        return {"ok": False, "status": r.status_code, "body": r.text}
    except Exception as e:
        print("[error] create_product exception:", e)
        return {"ok": False, "status": "exception", "body": str(e)}

def update_product(product_id, payload):
    url = f"{WC_BASE}/wp-json/wc/v3/products/{product_id}"
    headers = {"Content-Type": "application/json"}
    params = {"consumer_key": WC_KEY, "consumer_secret": WC_SECRET}
    try:
        r = requests.put(url, params=params, headers=headers, json=payload, timeout=WC_TIMEOUT)
        debug_print_response(r)
        if r.status_code in (200, 201):
            return {"ok": True, "status": r.status_code, "body": r.json()}
        return {"ok": False, "status": r.status_code, "body": r.text}
    except Exception as e:
        print("[error] update_product exception:", e)
        return {"ok": False, "status": "exception", "body": str(e)}

# ---------- بحث المنتج في WooCommerce بواسطة meta.source_id (كما فعلنا سابقًا) ----------
def get_wc_products(page=1, per_page=100):
    url = f"{WC_BASE}/wp-json/wc/v3/products"
    params = {"per_page": per_page, "page": page, "consumer_key": WC_KEY, "consumer_secret": WC_SECRET}
    try:
        r = requests.get(url, params=params, timeout=WC_TIMEOUT)
        if r.status_code == 200:
            return r.json()
        print("[warn] get_wc_products status", r.status_code, r.text[:200])
        return []
    except Exception as e:
        print("[error] get_wc_products exception:", e)
        return []

def find_product_by_source_id(source_id):
    if not source_id:
        return None
    page = 1
    while page <= MAX_PRODUCT_PAGES:
        prods = get_wc_products(page, WC_PER_PAGE)
        if not prods:
            break
        for p in prods:
            meta = p.get("meta_data", []) or []
            for m in meta:
                if m.get("key") == "source_id" and str(m.get("value")) == str(source_id):
                    print(f"[info] Found existing product id={p.get('id')} for source_id={source_id} (page {page})")
                    return p
        page += 1
    return None

# ---------- مساعدة لتوليد sku آمن ----------
def make_sku(source: str, source_id: str, title: str) -> str:
    ident = (source_id or title or "").encode()
    h = hashlib.sha1(ident).hexdigest()[:10]
    return f"SRC-{(source or 'SRC').upper()}-{h}"

# ---------- بناء payload لمنتج WooCommerce من عنصر SerpApi ----------
def build_wc_payload_from_item(item):
    title = item.get("title") or item.get("product_title") or "No title"
    product_url = item.get("product_url") or item.get("link") or item.get("product_link")
    images = item.get("images") or []
    price = item.get("extracted_price") or item.get("price") or None
    source = item.get("source") or item.get("engine") or "external"
    source_id = item.get("source_id") or item.get("product_id") or item.get("id") or ""
    sku = make_sku(source, source_id or product_url or title, title)

    payload = {
        "name": title,
        "type": "external" if product_url else "simple",
        "regular_price": str(price) if price else "0",
        "description": item.get("snippet") or item.get("description") or f"Imported from {source}",
        "external_url": product_url,
        "button_text": f"Buy on {source}",
        "sku": sku,
        "images": [{"src": u} for u in images if u],
        "meta_data": [
            {"key": "source", "value": source},
            {"key": "source_id", "value": source_id}
        ]
    }
    return source_id, sku, payload

# ---------- create_or_update wrapper ----------
def create_or_update_wc_product(item):
    source_id, sku, payload = build_wc_payload_from_item(item)
    if not payload.get("name"):
        print("[warn] skipping item with no title")
        return {"ok": False, "reason": "no title"}
    # 1) try find by source_id
    existing = None
    if source_id:
        existing = find_product_by_source_id(source_id)
    # 2) fallback find by sku
    if not existing:
        # try search by sku using Woo endpoint
        try:
            url = f"{WC_BASE}/wp-json/wc/v3/products"
            params = {"sku": sku, "consumer_key": WC_KEY, "consumer_secret": WC_SECRET}
            r = requests.get(url, params=params, timeout=WC_TIMEOUT)
            if r.status_code == 200:
                arr = r.json()
                if isinstance(arr, list) and arr:
                    existing = arr[0]
        except Exception as e:
            print("[warn] sku search failed:", e)

    if existing:
        pid = existing.get("id")
        print(f"[info] updating product id={pid} sku={sku}")
        resp = update_product(pid, payload)
        return {"action": "updated", "resp": resp, "id": pid}
    else:
        print(f"[info] creating product sku={sku}")
        resp = create_product(payload)
        new_id = None
        try:
            if resp.get("ok"):
                new_id = resp["body"].get("id")
        except Exception:
            pass
        return {"action": "created", "resp": resp, "id": new_id}

# ---------- دالة استدعاء SerpApi (مثال amazon) ----------
def get_serpapi_products(query, max_items=5):
    q = requests.utils.quote(query)
    # loc = requests.utils.quote(location)
    url = (
        f"https://serpapi.com/search.json"
        f"?engine=amazon"
        f"&k={q}"
    #    f"&location={loc}"
        f"&amazon_domain=amazon.com"
        f"&hl=en_US"
        f"&api_key={SERPAPI_KEY}"
    )
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print("[error] SerpApi request failed:", e)
        return []
    items = data.get("shopping_results") or data.get("organic_results") or []
    # normalize a bit
    out = []
    for it in items[:max_items]:
        out.append({
            "title": it.get("title") or it.get("product_title"),
            "product_url": it.get("link") or it.get("product_link"),
            "images": [it.get("thumbnail")] + (it.get("images") or []),
            "price": it.get("extracted_price") or it.get("price"),
            "source": "Amazon",
            "source_id": it.get("product_id") or it.get("serpapi_product_api") or "",
            "snippet": it.get("snippet"),
            "raw": it
        })
    return out

# ---------- main() المعدلة ----------
def main():
    print("[start] SerpApi -> Woo sync")
    products = get_serpapi_products(QUERY, MAX_ITEMS)
    print(f"[info] Found {len(products)} products from SerpApi.")
    summary = []
    for idx, p in enumerate(products, start=1):
        print(f"[item {idx}] processing...")
        # طباعة العنصر (جزئي) لمزيد من التشخيص
        print(json.dumps({k: p.get(k) for k in ("title","product_url","price","source_id")}, ensure_ascii=False, indent=2))
        try:
            res = create_or_update_wc_product(p)
            print(f"[item {idx}] result: {res}")
            summary.append(res)
        except Exception as e:
            print(f"[error] exception processing item {idx}: {e}")
        # تأخير بسيط بين الطلبات
        time.sleep(1.0)
    print("[done] Summary:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
