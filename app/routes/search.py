from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify, send_file
from app.database import get_connection
from app.services.search_service import search_products, get_advisor_for_products
from app.utils.pdf import create_offer_pdf

search = Blueprint("search", __name__)


@search.route("/")
def home():
    if "user" not in session:
        return redirect(url_for("auth.login"))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM products ORDER BY category")
    categories = [row["category"] for row in cursor.fetchall()]
    conn.close()

    return render_template("index.html", categories=categories)


@search.route("/api/search", methods=["POST"])
def ajax_search():
    """AJAX search endpoint — returns JSON, no page reload."""
    if "user" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json()
    query = data.get("query", "").strip()
    category = data.get("category", "all")

    if not query:
        return jsonify({"success": True, "products": [], "advisor": None})

    # Log search
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO search_logs (user, query) VALUES (?, ?)",
        (session["user"], query),
    )
    conn.commit()
    conn.close()

    try:
        result = search_products(query, category)
        return jsonify({
            "success": True,
            "products": result["products"],
            "advisor": result.get("advisor"),
            "not_related": result.get("not_related", False),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@search.route("/api/advisor", methods=["POST"])
def ajax_advisor():
    """Separate AJAX endpoint for AI advisor — loaded after search results."""
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    query = data.get("query", "")
    products = data.get("products", [])

    advisor = get_advisor_for_products(query, products)
    return jsonify({"advisor": advisor})


@search.route("/export_pdf", methods=["POST"])
def export_pdf():
    if "user" not in session:
        return redirect(url_for("auth.login"))

    products = request.json
    filename = create_offer_pdf(products)
    return send_file(filename, as_attachment=True)
