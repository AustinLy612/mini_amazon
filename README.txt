Mini-Amazon — Milestone 3
Standard project option
Repository: https://github.com/AustinLy612/mini_amazon
Integrated branch: milestone3

TEAM AND WORK SINCE MILESTONE 2
Leyang Han — Users Guru: SQL-backed buyer purchase history using the shared
Orders/OrderItems structure, final totals, item counts, fulfillment states,
and buyer-only order details.
Tiancheng Yu — Products Guru: parameterized top-k most expensive products
query, validated k input, deterministic price ordering, and results page.
Ziyi Shen — Carts Guru: persistent cart query and frontend, integrated from
the existing Carts branch; explicit user-ID query with ownership checks.
Zhiyuan Qi — Sellers Guru: inventory query and frontend, integrated from
the existing Sellers branch; explicit seller-ID query with ownership checks.

REQUIRED IMPLEMENTATIONS
Users: app/models/order.py — Order.for_buyer and Order.detail (SQL).
  Routes: app/milestone3.py — purchases and order_detail.
  HTML: /account/purchases; /orders/<order_id>.
  JSON: /api/users/<uid>/purchases; /api/users/<uid>/orders/<order_id>.
  Templates: app/templates/milestone3/purchases.html and order.html.
Products: app/models/product.py — Product.top_k (SQL).
  Route: app/milestone3.py — top_products.
  HTML: /products/top?k=3; JSON: /api/products/top?k=3.
  Template: app/templates/milestone3/products.html.
Carts: app/models/cart.py — Cart.get_items (SQL).
  Routes: app/carts.py and app/milestone3.py — cart_by_user.
  HTML: /cart; JSON: /api/users/<uid>/cart (also /api/cart).
  Template: app/templates/cart.html.
Sellers: app/models/seller.py — Seller.inventory (SQL).
  Routes: app/sellers.py and app/milestone3.py — inventory_by_seller.
  HTML: /seller/inventory; JSON: /api/sellers/<uid>/inventory?page=1.
  Template: app/templates/sellers/inventory.html.

START AND DEMONSTRATE
Use Python 3.11 or 3.12 and PostgreSQL.
1. Create/activate a virtual environment and run pip install -r requirements.txt,
   or use the repository's poetry install workflow.
2. Set DB_HOST, DB_PORT, DB_USER and DB_PASSWORD for your development PostgreSQL.
3. Run python tools/setup_sellers.py --database mini_amazon_m3_demo --demo.
   This creates a NEW database only and refuses to overwrite an existing one.
   It loads the skeleton, Carts/Sellers shared schema and synthetic demo data,
   and creates .flaskenv only when none exists. If .flaskenv already exists,
   preserve it and explicitly select DB_NAME=mini_amazon_m3_demo to run the demo.
4. Apply the optional read-query indexes using:
   psql -h <host> -p <port> -U <user> -d mini_amazon_m3_demo -v ON_ERROR_STOP=1
     -f db/milestone3_indexes.sql
   (The command above is one command, shown on two lines for readability.)
5. Run python -m flask --app amazon run --host 127.0.0.1 --port 8080.
6. Open http://127.0.0.1:8080/milestone3.

Synthetic demo accounts (not real people or production credentials):
  buyer.demo@example.com — purchase history and saved cart.
  seller.one@example.com — four listings, including zero stock.
  seller.two@example.com — a second seller for isolation and different results.
  All three use SellerDemo2026! in the isolated demo database only.
Account IDs are displayed in the Explore page after login; a fresh demo DB
assigns seller IDs 1 and 2 and buyer ID 3. Private ID endpoints require that
the supplied ID matches the authenticated account; other IDs return 403.

VIDEO
Milestone3_Final_179s.mp4 accompanies the submission files.
Duration: 2 minutes 59 seconds, with narration by the four module members.
Order: Products, Users, Carts, Sellers.
Video link: https://drive.google.com/file/d/1qvJginDU6sKi5lARdyFLJvPmYLZmfzf3/view?usp=sharing

VERIFICATION
See docs/milestone3/VALIDATION.md for executed checks and reproduction commands.
Install pytest in the active environment to run python -m pytest -q.

SCOPE AND SCHEMA COMPATIBILITY
This submission implements the four required M3 read queries and frontend
interactions, with buyer order details as an improvement over the skeleton.
The shared Orders, OrderItems, CartItems and Inventory contracts match the
M2 query design. The working database retains the skeleton's Users.password
(already a hash), legacy Purchases and Products.available for compatibility
with existing tutorial/seller code. New history reads Orders/OrderItems;
inventory/cart availability comes from Inventory, not Products.available.
Categories, product creator/profile editing, final password_hash renaming,
checkout, inventory version tokens and checkout keys remain final-stage work.
Synthetic demo orders are preloaded fixtures, not evidence of implemented checkout.
The four-person team has no fifth Social M3 endpoint requirement.

PACKAGING
Run python tools/package_milestone3.py to produce
submission/milestone3/CODE.zip and submission/milestone3/README.txt.
The package excludes virtual environments, credentials, database files,
downloaded runtimes, Git metadata, caches, historical design drafts and outputs.
