#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SerpApi -> WooCommerce sync (search by meta.source_id)
Usage:
  export SERPAPI_KEY=xxxx
  export WC_BASE=https://yourstore.com
  export WC_KEY=ck_xxx
  export WC_SECRET=cs_xxx
  export SERVICE_API_KEY=some-secret
  python3 serp_wc_sync_meta.py
"""

import os
import sys
import time
import hashlib
import json
import logging
from typing import List, Dict, Any, Optional

import requests

# ---------- config from env ----------
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "").strip()
WC_BASE = os.environ.get("WC_BASE", "").strip().rstrip("/")
WC_KEY = os.environ.get("WC_KEY", "").strip()
WC_SECRET = os.environ.get("WC_SECRET", "").strip()
SERVICE_API_KEY = os.environ.get("SERVICE_API_KEY", "").strip()
MAX_ITEMS = int(os.environ.get("MAX_ITEMS", "10"))
QUERY = os.environ.get("QUERY", "best sellers")
# number of pages to scan when searching by meta in WooCommerce (each page contains PER_PAGE items)
MAX_PRODUCT_PAGES = int(os.environ.get("MAX_PRODUCT_PAGES", "10"))
PER_PAGE = int(os.environ.get("WC_PER_PAGE", "100"))

# SerpApi endpoint
SERPAPI_URL = "https://serpapi.com/search.json"

# logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

if not SERPAPI_KEY:
    logging.error("SERPAPI_KEY not set in environment")
    sys.exit(1)
if not (WC_BASE and WC_KEY and WC_SECRET):
    logging.error("WooCommerce credentials (WC_BASE, WC_KEY, WC_SECRET) are required")
    sys.exit(1)


# ---------- helpers ----------
def wc_auth_headers() -> Dict[str, str]:
    token = (WC_KEY + ":" + WC_SECRET).encode()
    import base64
    b = base64.b64encode(token).decode()
    return {"Authorization": f"Basic {b}", "Content-Type": "application/json"}


def make_sku(source: str, source_id: str, title: str) -> str:
    ident = source_id or title or ""
    h = hashlib.sha1((ident or title).encode()).hexdigest()[:10]
    return f"SRC-{source.upper()}-{h}"


def serpapi_search(query: str, num: int = 10) -> List[Dict[str, Any]]:
    params = {
        "engine": "amazon",
        "q": query,
        "api_key": SERPAPI_KEY,
        "num": num
    }
    logging.info("Calling SerpApi for query='%s' num=%d", query, num)
    r = requests.get(SERPAPI_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    results = []
    organic = data.get("organic_results") or []
    for o in organic[:num]:
        title = o.get("title") or o.get("product_title") or ""
        link = o.get("link") or o.get("product_link") or o.get("product_url") or ""
        images = []
        if o.get("thumbnail"):
            images.append(o.get("thumbnail"))
        if o.get("images"):
            for im in o.get("images"):
                if isinstance(im, dict):
                    images.append(im.get("link") or im.get("src") or "")
                elif isinstance(im, str):
                    images.append(im)
        price = None
        if o.get("price"):
            price = o.get("price")
        source_id = ""
        if "/dp/" in link:
            try:
                source_id = link.split("/dp/")[1].split("/")[0]
            except Exception:
                source_id = ""
        results.append({
            "title": title,
            "product_url": link,
            "images": images,
            "image": images[0] if images else None,
            "price": price,
            "source": "amazon",
            "isAffiliate": True,
            "source_id": source_id
        })
    return results


# ---------- Woo helpers (search by meta.source_id) ----------
def find_product_by_source_id(source_id: str) -> Optional[Dict[str, Any]]:
    """
    Searches WooCommerce products by scanning pages and checking meta_data for key 'source_id'.
    Returns the product dict if found, else None.
    WARNING: This performs paginated requests and may be slow for stores with many products.
    """
    if not source_id:
        return None

    logging.info("Searching product by meta.source_id='%s' (per_page=%d, max_pages=%d)",
                 source_id, PER_PAGE, MAX_PRODUCT_PAGES)

    base_url = f"{WC_BASE}/wp-json/wc/v3/products"
    page = 1
    while page <= MAX_PRODUCT_PAGES:
        params = {"per_page": PER_PAGE, "page": page}
        r = requests.get(base_url, headers=wc_auth_headers(), params=params, timeout=30)
        if r.status_code != 200:
            logging.warning("Woo products list failed page %d: status=%d text=%s", page, r.status_code, r.text[:200])
            break
        prod_list = r.json()
        if not prod_list:
            break
        for p in prod_list:
            # meta_data might be present as list of dicts
            meta = p.get("meta_data") or []
            for m in meta:
                key = m.get("key")
                val = m.get("value")
                if key == "source_id" and val:
                    # compare as string
                    if str(val) == str(source_id):
                        logging.info("Found product id=%s for source_id=%s on page %d", p.get("id"), source_id, page)
                        return p
        # next page
        page += 1

    logging.info("Product with source_id=%s not found after scanning %d pages", source_id, MAX_PRODUCT_PAGES)
    return None


def create_product(payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{WC_BASE}/wp-json/wc/v3/products"
    r = requests.post(url, headers=wc_auth_headers(), json=payload, timeout=60)
    try:
        return {"status": r.status_code, "body": r.json() if r.headers.get("content-type","").startswith("application/json") else r.text}
    except Exception:
        return {"status": r.status_code, "body": r.text}


def update_product(product_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{WC_BASE}/wp-json/wc/v3/products/{product_id}"
    r = requests.put(url, headers=wc_auth_headers(), json=payload, timeout=60)
    try:
        return {"status": r.status_code, "body": r.json() if r.headers.get("content-type","").startswith("application/json") else r.text}
    except Exception:
        return {"status": r.status_code, "body": r.text}


# ---------- main sync ----------
def build_wc_payload(item: Dict[str, Any]) -> (str, Dict[str, Any]):
    title = item.get("title") or "No title"
    images = [{"src": u} for u in (item.get("images") or []) if u]
    source = item.get("source") or "source"
    source_id = item.get("source_id") or item.get("product_url") or ""
    sku = make_sku(source, source_id, title)
    payload = {
        "name": title,
        "type": "external" if item.get("isAffiliate") else "simple",
        "regular_price": str(item.get("price") or "0"),
        "description": f"Imported from {item.get('source')}",
        "external_url": item.get("product_url"),
        "button_text": f"Buy on {item.get('source').capitalize()}",
        "sku": sku,
        "images": images,
        "meta_data": [
            {"key": "source", "value": source},
            {"key": "source_id", "value": source_id}
        ]
    }
    return sku, payload


def main():
    logging.info("Starting SerpApi -> Woo sync (query='%s', max=%d)", QUERY, MAX_ITEMS)
    items = serpapi_search(QUERY, num=MAX_ITEMS)
    if not items:
        logging.info("No items from SerpApi")
        return

    summary = []
    for it in items:
        sku, payload = build_wc_payload(it)
        source_id = it.get("source_id") or it.get("product_url") or ""
        # 1) try find by source_id
        exist = None
        if source_id:
            exist = find_product_by_source_id(source_id)
        # 2) fallback: try find by sku (in case existing products were created by older flow)
        if not exist:
            exist_by_sku = None
            try:
                # reuse old method: search by sku param
                url = f"{WC_BASE}/wp-json/wc/v3/products"
                params = {"sku": sku}
                r = requests.get(url, headers=wc_auth_headers(), params=params, timeout=30)
                if r.status_code == 200:
                    j = r.json()
                    if isinstance(j, list) and len(j) > 0:
                        exist_by_sku = j[0]
                else:
                    logging.warning("WC find by sku returned status %d: %s", r.status_code, r.text[:200])
            except Exception as e:
                logging.warning("Error while searching by sku fallback: %s", e)

            exist = exist_by_sku

        if exist:
            pid = exist.get("id")
            logging.info("Product exists (source_id=%s, sku=%s, id=%s) -> updating", source_id, sku, pid)
            resp = update_product(pid, payload)
            summary.append({"sku": sku, "source_id": source_id, "action": "updated", "resp": resp})
        else:
            logging.info("Creating product (sku=%s, source_id=%s)", sku, source_id)
            resp = create_product(payload)
            summary.append({"sku": sku, "source_id": source_id, "action": "created", "resp": resp})

        # small delay to be gentle on WC / hosting
        time.sleep(1.0)

    logging.info("Done. Summary:")
    logging.info(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
