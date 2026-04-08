import numpy as np
import logging
from app.database import get_connection
from app.services.ai_service import get_embedding
from softone.client import fetch_products, fetch_stock

logger = logging.getLogger(__name__)


def sync_softone_products(upddate_from: str = "2026-01-01T00:00:00") -> int:
    """Fetches products from SoftOne and syncs with local database."""
    try:
        new_products = fetch_products(upddate_from=upddate_from)
    except Exception as e:
        logger.error(f"Error fetching from SoftOne: {e}")
        return 0

    if not new_products:
        return 0

    conn = get_connection()
    cursor = conn.cursor()

    count = 0
    for prod in new_products:
        kodikos = str(prod.get("code", ""))
        factory_code = str(prod.get("name2", ""))
        if not factory_code or factory_code == "None":
            factory_code = kodikos

        description = str(prod.get("name", ""))

        group = prod.get("group")
        category = group.get("name") if group and isinstance(group, dict) else "Unknown"

        subgroup = prod.get("subgroup")
        subcategory = subgroup.get("name") if subgroup and isinstance(subgroup, dict) else "Unknown"

        cursor.execute("SELECT id FROM products WHERE kodikos = ?", (kodikos,))
        existing = cursor.fetchone()

        stock = float(prod.get("stock", 0))
        available_stock = float(prod.get("availability", prod.get("balance", stock)))

        if existing:
            cursor.execute("""
                UPDATE products
                SET description = ?, category = ?, subcategory = ?, factory_code = ?, stock = ?, available_stock = ?
                WHERE kodikos = ?
            """, (description, category, subcategory, factory_code, stock, available_stock, kodikos))
            logger.info(f"[Update] {kodikos} - {description[:40]} - Stock: {stock}")
        else:
            cursor.execute("""
                INSERT INTO products (kodikos, factory_code, description, category, subcategory, stock, available_stock, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
            """, (kodikos, factory_code, description, category, subcategory, stock, available_stock))
            logger.info(f"[Insert] {kodikos} - {description[:40]} - Stock: {stock}")
            count += 1

    conn.commit()
    conn.close()

    # Invalidate in-memory cache after sync
    from app.services.search_service import invalidate_cache
    invalidate_cache()

    return count


def generate_missing_embeddings() -> int:
    """Finds products without embeddings and generates them using OpenAI API."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, kodikos, factory_code, description, category, subcategory FROM products WHERE embedding IS NULL"
    )
    to_embed = cursor.fetchall()

    generated_count = 0
    if to_embed:
        logger.info(f"Generating embeddings for {len(to_embed)} products...")
        for i, item in enumerate(to_embed, 1):
            logger.info(f"Embedding [{i}/{len(to_embed)}]: {item['kodikos']} - {item['description'][:40]}")
            text = f"{item['factory_code']} {item['description']} {item['category']} {item['subcategory']}"
            embedding = get_embedding(text)
            if embedding is not None:
                cursor.execute(
                    "UPDATE products SET embedding = ? WHERE id = ?",
                    (embedding.tobytes(), item["id"]),
                )
                generated_count += 1
            else:
                logger.warning(f"Failed to generate embedding for product {item['kodikos']}")

    conn.commit()
    conn.close()

    if generated_count > 0:
        from app.services.search_service import invalidate_cache
        invalidate_cache()

    return generated_count


def sync_softone_stock(whouse_code: str | None = None) -> int:
    """Fetches stock levels from SoftOne and updates local database."""
    try:
        stock_data = fetch_stock(whouse_code)
    except Exception as e:
        logger.error(f"Error fetching stock: {e}")
        return 0

    if not stock_data:
        return 0

    conn = get_connection()
    cursor = conn.cursor()

    updated_count = 0
    for item in stock_data:
        # Normalize keys
        item = {str(k).strip(): v for k, v in item.items()}
        
        # Also normalize the item_code value
        item_code = str(item.get("item_code", "")).strip()
        if not item_code:
            continue
            
        # Prioritize stock from warehouses if present
        wh_phys_sum = 0
        wh_avail_sum = 0
        has_wh_data = False
        wh_list = item.get("stock_per_warehouse", [])
        if wh_list and isinstance(wh_list, list):
            has_wh_data = True
            for wh in wh_list:
                wh = {str(k).strip(): v for k, v in wh.items()}
                wh_phys_sum += float(wh.get("physical_stock", wh.get("physical_stock ", 0)))
                wh_avail_sum += float(wh.get("available_stock", wh.get("available_stock ", 0)))

        physical_stock = item.get("physical_stock", item.get("stock", 0))
        available_stock = item.get("available_stock")
        if available_stock is None:
            available_stock = item.get("availability", item.get("balance", physical_stock))
            
        # If we have warehouse data, use the sums
        if has_wh_data:
            physical_stock = wh_phys_sum
            available_stock = wh_avail_sum

        cursor.execute("SELECT id FROM products WHERE kodikos = ?", (item_code,))
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                "UPDATE products SET stock = ?, available_stock = ? WHERE kodikos = ?",
                (physical_stock, available_stock, item_code),
            )
            updated_count += 1

    conn.commit()
    conn.close()

    # Invalidate cache since stock changed
    from app.services.search_service import invalidate_cache
    invalidate_cache()

    return updated_count
