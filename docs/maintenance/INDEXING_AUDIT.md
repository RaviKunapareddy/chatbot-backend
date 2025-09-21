# Pinecone Indexing & Query Audit

This document summarizes how products and support docs are indexed and queried in Pinecone, along with flags that affect behavior.

Last reviewed: 2025-08-24

---

## Embeddings
- Model: Hugging Face Inference API (default `BAAI/bge-small-en-v1.5`) per index type
  - Products: env `HF_PRODUCT_MODEL` (default `BAAI/bge-small-en-v1.5`)
  - Support: env `HF_SUPPORT_MODEL` (default `BAAI/bge-small-en-v1.5`)
- Dimension: `384`
- Endpoint: `https://api-inference.huggingface.co/models/{model}` with `HF_API_KEY`
- Fallback: deterministic local vector if API fails (ensures stable though non-semantic behavior)
- Usage tracking: optional Redis counter `monthly_embeddings:{YYYY-MM}` incremented on success

## Indexes
- Client: `vector_service/pinecone_client.py`
- Index names (serverless, v6 API):
  - Products: `PINECONE_PRODUCTS_INDEX` (default `chatbot-products`)
  - Support: `PINECONE_SUPPORT_INDEX` (default `chatbot-support-knowledge`)

---

## Product Indexing: `PineconeClient.index_products()`
- Searchable text: `title + description + category` (truncated to 1000 chars)
- Embedding: HF inference or fallback
- Metadata stored per vector:
  - id: string `id`
  - title: truncated 1000 chars
  - description: truncated 1000 chars
  - category, category_lc
  - brand, brand_lc
  - price (float)
  - rating (float)
  - searchable_text (truncated 1000)
  - type: `product`
  - thumbnail, image (first of `images`), truncated 1000 chars
  - stock (int)
  - discountPercentage (float):
    - If missing/zero but `originalPrice > price > 0`, compute `((originalPrice - price)/originalPrice) * 100`, 2 decimals
    - Else keep provided value or 0.0
  - originalPrice (float)
  - availabilityStatus: `in_stock` if `stock > 0` else `out_of_stock`
  - sku: `sku` or fallback to `id`
  - tags (string): comma-joined of up to 20 tags
  - tag_<normalized>: boolean True for up to 20 tags
    - Normalization: lowercase, trim, non-alnum → `_`, collapse `_`, strip edges
- Upsert batching: chunks of 100

## Support Doc Indexing: `PineconeClient.index_support_docs()`
- Metadata per vector:
  - type: `support`
  - doc_type, category, source
  - content: truncated 1000 chars
  - optional: product_count

---

## Product Query: `PineconeClient.search_products()`
- Always filters `type: product`
- Optional filters composed into `filter_dict`:
  - Price range: `price: { $gte, $lte }`
  - Brand:
    - If `SEARCH_CASE_INSENSITIVE=true`, filter on `brand_lc = brand.lower()`
    - Else `brand = brand`
  - Category: analogous `category_lc`/`category`
  - Rating min: `rating: { $gte: rating_min }`
  - In-stock: if `in_stock is True`, `stock: { $gt: 0 }` (ignore False)
  - Discount min: `discountPercentage: { $gte: discount_min }`
  - Tags (AND): when `SEARCH_TAGS_SERVER_FILTER_ENABLED=true`, add each `tag_<normalized>: True`
    - Else, results are post-filtered in Python to ensure all requested tags are present
- Query returns `matches` with metadata; we:
  - Convert `tags` back to list
  - Attach `similarity_score = match.score`
  - Keep Python post-filter if server-side tag flags are off or not enforced (e.g., fake index)

## Support Query: `PineconeClient.search_support()`
- Adds `type: support` to filter
- Returns content, doc_type, category, source, score, id (and optional product_count)

---

## Case-Insensitive & Tag Behavior
- Case-insensitive filters controlled by env `SEARCH_CASE_INSENSITIVE` (brand/category via *_lc)
- Tags normalization shared across index and fallback: `re.sub(r'[^a-z0-9]+', '_')`, collapse, strip edges
- Server-side tag flags controlled by env `SEARCH_TAGS_SERVER_FILTER_ENABLED`

---

## Reranking Layer (Post-Query)
- Implemented in `search/product_data_loader.ProductDataLoader._apply_reranking()`
- Formula per plan 4.1:
  - `score = 0.6 * similarity + 0.2 * (rating/5) + 0.1 * (min(discountPercentage, 50)/50) + 0.1 * price_affinity`
  - `price_affinity = 1.0` if price within provided `price_min/price_max` bounds; else `0.0`
- Behavior:
  - Adds `rerank_score` to each result
  - Reorders only if `SEARCH_RERANK_ENABLED=true` (default false). Otherwise original order preserved
  - Applied on both Pinecone and keyword-fallback paths

---

## Operational Notes
- Reindex script: `vector_service/manual_reindex_products.py`
  - Dry run: `python vector_service/manual_reindex_products.py --dry-run`
  - Limit: `python vector_service/manual_reindex_products.py --limit 100 --yes`
  - Clear only products then reindex: `python vector_service/manual_reindex_products.py --clear --yes`
- Health: `/health` shows Pinecone connection and vector counts

## Environment Flags Summary
- `SEARCH_CASE_INSENSITIVE`: case-insensitive brand/category filtering (default false)
- `SEARCH_TAGS_SERVER_FILTER_ENABLED`: server-side tag AND filtering via `tag_*` flags (default false)
- `SEARCH_RERANK_ENABLED`: enable reranking reorder step (default false)

## Data Limits
- String fields truncated to 1000 chars to respect Pinecone limits
- Up to 20 tags used for `tags` and `tag_*` flags
