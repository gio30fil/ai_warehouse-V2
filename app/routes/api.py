from flask import Blueprint, jsonify, session, request
from app.database import get_connection
from app.services.sync_service import sync_softone_products, sync_softone_stock, generate_missing_embeddings

api = Blueprint("api", __name__, url_prefix="/api")


@api.route("/products")
def get_products():
    if "user" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT kodikos, description, stock, available_stock FROM products ORDER BY description")
    rows = cursor.fetchall()
    conn.close()

    products = [
        {
            "code": r["kodikos"], 
            "description": r["description"], 
            "stock": r["stock"],
            "available_stock": r["available_stock"]
        }
        for r in rows
    ]

    return jsonify(products)


@api.route("/fetch_stock", methods=["POST"])
def fetch_stock():
    if "user" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    try:
        count = sync_softone_stock()
        return jsonify({"success": True, "message": f"Stock updated for {count} products!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api.route("/sync", methods=["POST"])
def sync():
    if session.get("role") != "admin":
        return jsonify({"success": False, "error": "Access denied"}), 403

    data = request.get_json() or {}
    upddate_from = data.get("upddate_from", "2026-01-01T00:00:00")

    try:
        new_count = sync_softone_products(upddate_from=upddate_from)
        # Automatically trigger stock sync after product sync for real-time accuracy
        stock_count = sync_softone_stock()
        
        return jsonify({
            "success": True,
            "message": f"Sync completed! Added {new_count} new products and updated stock for {stock_count} items.",
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
@api.route("/generate_embeddings", methods=["POST"])
def generate_embeddings():
    if session.get("role") != "admin":
        return jsonify({"success": False, "error": "Access denied"}), 403

    try:
        new_count = generate_missing_embeddings()
        return jsonify({
            "success": True,
            "message": f"Ολοκληρώθηκε! Δημιουργήθηκαν {new_count} νέα AI embeddings.",
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api.route("/clear_products", methods=["POST"])
def clear_products():
    if session.get("role") != "admin":
        return jsonify({"success": False, "error": "Access denied"}), 403

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products")
        conn.commit()
        conn.close()

        from app.services.search_service import invalidate_cache
        invalidate_cache()

        return jsonify({
            "success": True,
            "message": "Όλα τα προϊόντα διεγράφησαν από τη βάση με επιτυχία.",
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
