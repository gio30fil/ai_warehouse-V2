import sqlite3
conn = sqlite3.connect('warehouse.db')
c = conn.cursor()
c.execute('SELECT kodikos, description, stock, available_stock FROM products WHERE kodikos = ?', ('019544',))
rows = c.fetchall()
for r in rows:
    print(repr(r))

# Also search for "Μηχανισμός" in descriptions
print("\n--- Searching for text matches ---")
c.execute("SELECT kodikos, description, stock FROM products WHERE description LIKE ? LIMIT 10", ('%Μηχανισμ%',))
rows2 = c.fetchall()
for r in rows2:
    print(repr(r))

# Check how many products have non-null embedding
c.execute("SELECT COUNT(*) FROM products WHERE embedding IS NOT NULL")
print(f"\nProducts with embeddings: {c.fetchone()[0]}")

c.execute("SELECT COUNT(*) FROM products")
print(f"Total products: {c.fetchone()[0]}")

# Check if product 019544 has an embedding
c.execute("SELECT kodikos, description, embedding IS NOT NULL as has_emb FROM products WHERE kodikos = ?", ('019544',))
r = c.fetchone()
if r:
    print(f"\nProduct 019544: desc='{r[1]}', has_embedding={r[2]}")

conn.close()
