# SerpApi -> WooCommerce Sync (search by meta.source_id)

This project is a standalone Python script that uses SerpApi to fetch Amazon search results (e.g. "best sellers")
and creates/updates products in a WooCommerce store. It searches WooCommerce products by `meta_data` key `source_id`
to avoid duplicates.

## Files
- `serp_wc_sync_meta.py` - main script
- `requirements.txt` - Python deps
- `Dockerfile` - minimal Dockerfile for Cloud Run / container usage
- `.dockerignore` - ignore file for Docker
- `README.md` - this file

## Usage (local)
Set environment variables:
```
export SERPAPI_KEY="your_serpapi_key"
export WC_BASE="https://yourstore.com"
export WC_KEY="ck_xxx"
export WC_SECRET="cs_xxx"
export MAX_ITEMS=10
export QUERY="best sellers"
```

Install deps and run:
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python serp_wc_sync_meta.py
```

## Deploy (Cloud Run - recommended approach)
Build and push:
```
gcloud builds submit --tag gcr.io/PROJECT_ID/serp-wc-sync-meta
```

Create a Cloud Run Job:
```
gcloud beta run jobs create serp-wc-sync-meta-job --image gcr.io/PROJECT_ID/serp-wc-sync-meta --region us-central1 --memory=512Mi --set-env-vars "SERPAPI_KEY=...,WC_BASE=https://yourstore.com,WC_KEY=ck_xxx,WC_SECRET=cs_xxx,MAX_ITEMS=10,QUERY=best sellers"
```

Execute job manually:
```
gcloud beta run jobs execute serp-wc-sync-meta-job --region us-central1
```

Use Cloud Scheduler to run the job periodically.

## Notes & Recommendations
- Searching WooCommerce by meta scans pages and may be slow for stores with many products. Consider storing a `source_id -> product_id` mapping in a small DB (Firestore / Cloud SQL).
- Test the SerpApi output for your queries to ensure fields like `images`, `link`, and `price` are present and parsed correctly.
- Respect SerpApi quotas and Amazon TOS.
