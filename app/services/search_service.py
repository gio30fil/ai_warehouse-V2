import numpy as np
import logging
import re
import threading
from sklearn.metrics.pairwise import cosine_similarity
from app.database import get_connection
from app.services.ai_service import understand_and_check_query, get_embedding, ai_product_advisor

logger = logging.getLogger(__name__)

# Known brands
BRANDS = [
    "inim", "dahua", "hikvision", "ajax", "paradox", "uniview", "tiandy", "ezviz",
    "detnov", "tyco", "american dynamics", "fireclass", "risco", "dsc", "boss",
    "samsung", "sensormatic", "honeywell", "c-tec", "toshiba", "western digital",
    "wisenet", "panoramic", "illustra", "arecont vision", "simtronics",
    "eff eff", "soyal", "cometa", "mobiak",
]

# ─── In-Memory Embedding Cache ─────────────────────────────────────────
# Holds all product embeddings in a single numpy matrix for vectorized search.
# Refreshed periodically or after sync.

_cache_lock = threading.Lock()
_embedding_cache = {
    "loaded": False,
    "matrix": None,       # np.ndarray shape (N, dim)
    "product_ids": [],    # parallel list of product IDs
    "product_data": [],   # parallel list of product dicts
}


def _load_embedding_cache():
    """Load all product embeddings into memory as a numpy matrix."""
    global _embedding_cache

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, kodikos, factory_code, description, category, subcategory, stock, available_stock, embedding
        FROM products
        WHERE embedding IS NOT NULL
    """)

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        with _cache_lock:
            _embedding_cache = {
                "loaded": True,
                "matrix": None,
                "product_ids": [],
                "product_data": [],
            }
        return

    embeddings = []
    product_ids = []
    product_data = []

    for row in rows:
        emb = np.frombuffer(row["embedding"], dtype=np.float64)
        embeddings.append(emb)
        product_ids.append(row["id"])
        product_data.append({
            "kodikos": row["kodikos"],
            "factory_code": row["factory_code"],
            "description": row["description"],
            "category": row["category"],
            "subcategory": row["subcategory"],
            "stock": row["stock"],
            "available_stock": row["available_stock"],
        })

    matrix = np.vstack(embeddings)

    with _cache_lock:
        _embedding_cache = {
            "loaded": True,
            "matrix": matrix,
            "product_ids": product_ids,
            "product_data": product_data,
        }

    logger.info(f"Embedding cache loaded: {len(product_ids)} products, matrix shape {matrix.shape}")


def invalidate_cache():
    """Call after product sync to force cache reload."""
    global _embedding_cache
    with _cache_lock:
        _embedding_cache["loaded"] = False
    logger.info("Embedding cache invalidated.")


def _ensure_cache():
    """Ensure embeddings are loaded into memory."""
    if not _embedding_cache["loaded"]:
        _load_embedding_cache()


def normalize_query(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _lookup_by_kodikos(query: str, category: str = "all") -> list:
    """
    Direct database lookup by SoftOne product code (kodikos).
    Returns matching products if the query looks like a product code.
    Uses exact match first, then prefix match with LIKE.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Try exact match first (case-insensitive)
    if category != "all":
        cursor.execute("""
            SELECT kodikos, factory_code, description, category, subcategory, stock, available_stock
            FROM products
            WHERE LOWER(kodikos) = LOWER(?) AND category = ?
        """, (query, category))
    else:
        cursor.execute("""
            SELECT kodikos, factory_code, description, category, subcategory, stock, available_stock
            FROM products
            WHERE LOWER(kodikos) = LOWER(?)
        """, (query,))

    rows = cursor.fetchall()

    # If no exact match, try prefix match (user might type partial code)
    if not rows:
        like_pattern = f"{query}%"
        if category != "all":
            cursor.execute("""
                SELECT kodikos, factory_code, description, category, subcategory, stock, available_stock
                FROM products
                WHERE LOWER(kodikos) LIKE LOWER(?) AND category = ?
                LIMIT 10
            """, (like_pattern, category))
        else:
            cursor.execute("""
                SELECT kodikos, factory_code, description, category, subcategory, stock, available_stock
                FROM products
                WHERE LOWER(kodikos) LIKE LOWER(?)
                LIMIT 10
            """, (like_pattern,))
        rows = cursor.fetchall()

    conn.close()

    if not rows:
        return []

    results = []
    for row in rows:
        results.append({
            "score": 1.0,
            "kodikos": row["kodikos"],
            "factory_code": row["factory_code"],
            "description": row["description"],
            "category": row["category"],
            "subcategory": row["subcategory"],
            "stock": row["stock"],
            "available_stock": row["available_stock"],
        })

    return results


def _text_search(query: str, category: str = "all") -> list:
    """
    Direct text search (SQL LIKE) on product descriptions.
    Splits query into words and matches products containing ALL words.
    Catches products the AI embedding search might miss.
    """
    words = [w.strip() for w in query.split() if len(w.strip()) >= 2]
    if not words:
        return []

    conn = get_connection()
    cursor = conn.cursor()

    # Build WHERE clause: description LIKE '%word1%' AND description LIKE '%word2%' ...
    conditions = []
    params = []
    for word in words:
        conditions.append("LOWER(description) LIKE LOWER(?)")
        params.append(f"%{word}%")

    if category != "all":
        conditions.append("category = ?")
        params.append(category)

    where_clause = " AND ".join(conditions)
    sql = f"""
        SELECT kodikos, factory_code, description, category, subcategory, stock, available_stock
        FROM products
        WHERE {where_clause}
        LIMIT 20
    """

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        stock = row["stock"]
        results.append({
            "score": 0.999,
            "kodikos": row["kodikos"],
            "factory_code": row["factory_code"],
            "description": row["description"],
            "category": row["category"],
            "subcategory": row["subcategory"],
            "stock": stock,
            "available_stock": row["available_stock"],
        })

    logger.info(f"Text search for '{query}' → {len(results)} result(s)")
    return results


def search_products(query: str, category: str = "all") -> dict:
    """
    Optimized product search:
    0. Direct kodikos lookup (fast-path for SoftOne codes)
    1. Single AI call: checks relevance + translates query
    2. Cached query embeddings
    3. Vectorized cosine similarity (batch numpy operation)
    4. AI advisor returned separately (non-blocking)
    """
    query_lower = normalize_query(query)

    # ── Step 0: Direct kodikos lookup (SoftOne product code) ──
    direct_results = _lookup_by_kodikos(query_lower.strip(), category)
    if direct_results:
        logger.info(f"Direct kodikos match for '{query}' → {len(direct_results)} result(s)")
        return {"products": direct_results, "advisor": None, "text_matches": []}

    # ── Step 0.5: Text search (SQL LIKE on description) ──
    text_results = _text_search(query_lower.strip(), category)
    logger.info(f"Text search found {len(text_results)} result(s) for '{query}'")

    # ── Step 1: AI combined check + translation (single API call) ──
    ai_result = understand_and_check_query(query_lower)

    if not ai_result["related"]:
        logger.info(f"Query '{query}' not product-related → returning text matches only")
        return {"products": [], "advisor": None, "not_related": True, "text_matches": text_results}

    translated_query = ai_result["translated"]
    logger.info(f"AI translated: '{query}' → '{translated_query}'")

    query_words = translated_query.split()

    # ── Step 2: Brand detection ──
    brand_query = None
    for brand in BRANDS:
        if brand in translated_query:
            brand_query = brand
            break

    # ── Step 3: Get query embedding (with cache) ──
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT embedding FROM query_cache WHERE query = ?",
        (translated_query,),
    )
    cached = cursor.fetchone()

    if cached:
        logger.debug("Query embedding from cache")
        query_embedding = np.frombuffer(cached["embedding"], dtype=np.float64)
    else:
        logger.debug("Generating new query embedding")
        query_embedding = get_embedding(translated_query)
        if query_embedding is None:
            conn.close()
            raise Exception("Αποτυχία σύνδεσης με OpenAI API")

        cursor.execute(
            "INSERT OR IGNORE INTO query_cache (query, embedding) VALUES (?, ?)",
            (translated_query, query_embedding.tobytes()),
        )
        conn.commit()

    conn.close()

    # ── Step 4: Vectorized cosine similarity ──
    _ensure_cache()

    with _cache_lock:
        matrix = _embedding_cache["matrix"]
        product_data = _embedding_cache["product_data"]

    if matrix is None or len(product_data) == 0:
        return {"products": [], "advisor": None}

    # Single batch operation — O(1) numpy call instead of O(n) Python loop
    similarities = cosine_similarity([query_embedding], matrix)[0]

    # ── Step 5: Scoring & filtering ──
    results = []

    for i, sim in enumerate(similarities):
        prod = product_data[i]
        desc_lower = prod["description"].lower() if prod["description"] else ""
        stock = prod["stock"]
        available_stock = prod["available_stock"]

        # Category filter
        if category != "all" and prod["category"] != category:
            continue

        # Stock filter
        # Consider a product fully out of stock if physical_stock is 0. 
        if not stock or float(stock) <= 0:
            continue

        # Business rules
        if "αναλογ" in translated_query:
            if not any(w in desc_lower for w in ["αναλογ", "tvi", "ahd", "cvi"]):
                continue

        if "ip" in query_words:
            if not any(w in desc_lower for w in ["ip", "network"]):
                continue

        keyword_match = any(word in desc_lower for word in query_words)

        if sim < 0.35 and not keyword_match:
            continue

        # Scoring
        keyword_score = sum(0.05 for word in query_words if word in desc_lower)
        brand_boost = 0.20 if (brand_query and brand_query in desc_lower) else 0
        final_score = float(sim) + keyword_score + brand_boost

        results.append({
            "score": final_score,
            "kodikos": prod["kodikos"],
            "factory_code": prod["factory_code"],
            "description": prod["description"],
            "category": prod["category"],
            "subcategory": prod["subcategory"],
            "stock": stock,
            "available_stock": available_stock,
        })

    results.sort(reverse=True, key=lambda x: x["score"])

    if not results and not text_results:
        return {"products": [], "advisor": None, "text_matches": []}

    top_results = results[:10]

    # Deduplicate: remove text_results that already appear in AI results
    ai_kodikos_set = {p["kodikos"] for p in top_results}
    unique_text_results = [p for p in text_results if p["kodikos"] not in ai_kodikos_set]

    return {
        "products": top_results,
        "advisor": None,  # Advisor loaded via separate AJAX call
        "text_matches": unique_text_results,
    }


def get_advisor_for_products(query: str, products: list) -> str | None:
    """Separate call for AI advisor — loaded asynchronously via AJAX."""
    return ai_product_advisor(query, products)
