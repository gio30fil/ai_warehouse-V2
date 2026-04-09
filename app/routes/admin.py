from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from werkzeug.security import generate_password_hash
from app.database import get_connection

admin = Blueprint("admin", __name__, url_prefix="/admin")


@admin.before_request
def check_login():
    if "user" not in session:
        return redirect(url_for("auth.login"))


@admin.route("/")
def dashboard():
    if session.get("role") != "admin":
        return "Access denied", 403

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, username, role FROM users")
    users = cursor.fetchall()

    cursor.execute("""
        SELECT user, query, created_at
        FROM search_logs ORDER BY created_at DESC LIMIT 20
    """)
    logs = cursor.fetchall()

    cursor.execute("""
        SELECT query, COUNT(*) as total
        FROM search_logs GROUP BY query ORDER BY total DESC LIMIT 5
    """)
    top_searches = cursor.fetchall()

    cursor.execute("""
        SELECT user, COUNT(*) as total
        FROM search_logs GROUP BY user ORDER BY total DESC
    """)
    user_stats = cursor.fetchall()

    cursor.execute("""
        SELECT DATE(created_at), COUNT(*)
        FROM search_logs GROUP BY DATE(created_at)
        ORDER BY DATE(created_at) DESC LIMIT 7
    """)
    daily_stats = cursor.fetchall()

    conn.close()

    return render_template(
        "admin.html",
        users=users,
        logs=logs,
        top_searches=top_searches,
        user_stats=user_stats,
        daily_stats=daily_stats,
    )


@admin.route("/softone-raw")
def softone_raw():
    if session.get("role") != "admin":
        return "Access denied", 403

    from softone.client import fetch_products, fetch_stock

    products = fetch_products()
    stock = fetch_stock()
    # Normalize keys in stock data
    stock = [{str(k).strip(): v for k, v in item.items()} for item in stock]

    stock_lookup = {}
    for item in stock:
        item = {str(k).strip(): v for k, v in item.items()}
        code = str(item.get("item_code")).strip().lower()
        if code:
            stock_lookup[code] = item.get("physical_stock", item.get("stock", 0))

    combined_data = []
    for p in products:
        code = str(p.get("code")).strip().lower()
        p["live_stock"] = stock_lookup.get(code, 0)
        combined_data.append(p)

    return render_template("softone_data.html", products=combined_data, stock=stock)


@admin.route("/stock")
def stock_list():
    if session.get("role") not in ["admin", "sales"]:
        return "Access denied", 403

    from softone.client import fetch_stock

    live_stock = fetch_stock()

    stock_lookup = {}
    for s in live_stock:
        s = {str(k).strip(): v for k, v in s.items()}
        code = str(s.get("item_code", "")).strip().lower()
        if not code:
            continue

        details = []
        wh_phys_sum = 0
        wh_avail_sum = 0
        has_wh_data = False
        wh_list = s.get("stock_per_warehouse", [])
        
        if wh_list and isinstance(wh_list, list):
            has_wh_data = True
            for wh in wh_list:
                wh = {str(k).strip(): v for k, v in wh.items()}
                wh_name = wh.get("whouse_name", "Unknown")
                p_q = float(wh.get("physical_stock", wh.get("physical_stock ", 0)))
                a_q = float(wh.get("available_stock", wh.get("available_stock ", 0)))
                
                wh_phys_sum += p_q
                wh_avail_sum += a_q
                
                # Store for product breakdown
                if p_q > 0 or a_q > 0:
                    details.append({"wh": wh_name, "phys": p_q, "avail": a_q})

        total = s.get("physical_stock", s.get("stock", 0))
        available = s.get("available_stock", s.get("physical_stock", s.get("stock", 0)))
        
        if has_wh_data:
            total = wh_phys_sum
            available = wh_avail_sum

        stock_lookup[code] = {
            "total": total,
            "available": available,
            "details": details,
        }

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT kodikos, factory_code, description, category, subcategory, stock, available_stock
        FROM products ORDER BY category, description
    """)
    products_db = cursor.fetchall()
    conn.close()

    enriched_products = []
    for row in products_db:
        code = str(row["kodikos"]).strip().lower()
        live = stock_lookup.get(code, {"total": row["stock"], "available": row["available_stock"], "details": []})

        enriched_products.append({
            "kodikos": row["kodikos"],
            "factory_code": row["factory_code"],
            "description": row["description"],
            "category": row["category"],
            "subcategory": row["subcategory"],
            "db_stock": row["stock"],
            "db_available_stock": row["available_stock"],
            "live_total": live["total"],
            "live_available": live["available"],
            "details": live["details"],
        })

    return render_template("stock_list.html", products=enriched_products)


@admin.route("/pending-orders")
def pending_orders():
    if session.get("role") not in ["admin", "sales"]:
        return "Access denied", 403

    from softone.client import fetch_pending_orders

    try:
        orders = fetch_pending_orders()
    except Exception as e:
        orders = []

    return render_template("pending_orders.html", orders=orders)


@admin.route("/user/<username>")
def user_searches(username):
    if session.get("role") != "admin":
        return "Access denied", 403

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT query, created_at FROM search_logs WHERE user = ? ORDER BY created_at DESC",
        (username,),
    )
    logs = cursor.fetchall()
    conn.close()

    return render_template("user_logs.html", logs=logs, username=username)


@admin.route("/add", methods=["POST"])
def add_user():
    if session.get("role") != "admin":
        return "Access denied", 403

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not username or not password:
        return redirect(url_for("admin.dashboard"))

    hashed = generate_password_hash(password)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
        (username, hashed, "sales"),
    )
    conn.commit()
    conn.close()

    return redirect(url_for("admin.dashboard"))


@admin.route("/delete/<int:user_id>")
def delete_user(user_id):
    if session.get("role") != "admin":
        return "Access denied", 403

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("admin.dashboard"))


@admin.route("/edit/<int:user_id>", methods=["GET", "POST"])
def edit_user(user_id):
    if session.get("role") != "admin":
        return "Access denied", 403

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        hashed = generate_password_hash(password)
        cursor.execute(
            "UPDATE users SET username = ?, password = ? WHERE id = ?",
            (username, hashed, user_id),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("admin.dashboard"))

    cursor.execute("SELECT id, username FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()

    return render_template("edit_user.html", user=user)
