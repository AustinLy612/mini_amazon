# Sellers integration contract

Sellers uses the Carts branch's shared schema. The blueprint is registered in
`app/__init__.py`; the shared navigation adds a Seller center link. Seller styles
are scoped to its pages. No new production dependency is required.

## Database ownership

| Relation | Required contract | Sellers access |
|---|---|---|
| Users | `id`, `email`, `firstname`, `lastname`; existing Flask-Login identity | Read buyer contact and public seller name |
| Products | `id`, `name`, `price` | Read the common product catalog and current listing price |
| Inventory | `seller_id`, `product_id`, nonnegative integer `quantity`; primary key `(seller_id, product_id)` | Add, update or delete the authenticated seller's listing |
| Orders | `id`, `buyer_id`, `placed_at`, `buyer_name_snapshot`, `shipping_address_snapshot` | Read orders containing the authenticated seller's items |
| OrderItems | `id`, `order_id`, `seller_id`, `product_id`, `product_name_snapshot`, positive `quantity`, positive `unit_price`, nullable `fulfilled_at` | Read owned items; set owned pending items' fulfillment timestamp |

The current contract uses one `Products.price` per product. Per-seller pricing
would require a coordinated schema and checkout change; this module does not
introduce a second price source. A listing with quantity zero remains listed and
is unavailable. Removing a listing does not remove Products, CartItems or
OrderItems. CartItems and OrderItems reference Users and Products, not Inventory.

Order totals, quantities, products and pending counts shown to a seller cover
only that seller's lines. `overall_fulfilled` exposes only a boolean for the whole
order. Order names, shipping addresses and prices come from checkout snapshots.
Buyer email comes from Users. Sellers cannot query another seller's line or an
order with no owned items.

`db/sellers_schema.sql` checks required columns and adds repeatable indexes for
product-stock lookups and pending fulfillment. It does not change the Carts
schema or convert legacy Purchases into Orders.

## JSON interfaces

Authenticated endpoints derive seller identity from `current_user.id`. A body
or query parameter called `seller_id` cannot select another seller. GET responses
use decimal strings such as `"5.98"` and UTC timestamps ending in `Z`.

| Method and path | Request / response |
|---|---|
| `GET /api/seller/overview` | `stock`, `sales`, daily revenue, top products and five recent pending orders |
| `GET /api/seller/inventory` | `q`, `sort`, `page`; paginated `items` with `product_id`, `name`, `price`, `quantity` |
| `POST /api/seller/inventory` | `product_id`, `quantity`; returns `listing` and HTTP 201 |
| `POST /api/seller/inventory/<product_id>/quantity` | `quantity`, `expected_quantity`; returns updated `listing` |
| `POST /api/seller/inventory/<product_id>/remove` | `expected_quantity`; returns `removed` |
| `GET /api/seller/orders` | `q`, `status`, `page`; paginated owned order summaries |
| `GET /api/seller/orders/<order_id>` | Owned summary and owned `items` only |
| `POST /api/seller/order-items/<item_id>/fulfill` | CSRF token; returns `item` with id, order id, timestamp and `already_fulfilled` |
| `GET /api/sellers/products/<product_id>` | Public product and sellers: `seller_id`, `seller_name`, `quantity`, `available` |

Inventory sorts: `name`, `stock_low`, `stock_high`, `price_low`, `price_high`.
Order filters: `all`, `pending`, `fulfilled`; pending includes partial fulfillment.
Pages contain 20 rows, ordered deterministically. Out-of-range positive pages
clamp to the last page. Search is a literal substring; `%`, `_` and backslash are
escaped rather than treated as SQL wildcards.

An owned order summary contains `id`, `placed_at`, `buyer_name_snapshot`,
`shipping_address_snapshot`, `buyer_email`, `line_count`, `item_count`, `total`,
`pending_count`, `status` (`pending`, `partial`, `fulfilled`) and
`overall_fulfilled`. Each owned item adds `unit_price`, `subtotal` and
`fulfilled_at` alongside its id, product id, snapshot name and quantity.

POST requests must send the session's CSRF token in `X-CSRFToken` or JSON
`csrf_token`. HTML pages include it in forms and `<meta name="csrf-token">`.
For a same-origin frontend:

```javascript
const token = document.querySelector('meta[name="csrf-token"]').content;
const response = await fetch('/api/seller/inventory/1/quantity', {
  method: 'POST',
  headers: {'Content-Type': 'application/json', 'X-CSRFToken': token},
  body: JSON.stringify({quantity: 20, expected_quantity: 17})
});
```

Guests receive HTTP 401 on authenticated JSON endpoints or a login redirect on
HTML pages. Invalid CSRF returns 400; invalid fields return 422; absent or
unowned resources return 404; duplicate listings and stale stock writes return
409. Quantities must be whole numbers from zero to 2,147,483,647. Negative values,
fractions and booleans are rejected. Only POST changes data.

## Checkout and concurrency

The Carts owner creates Orders and OrderItems after successful purchase. Keep
the stock validation, stock deduction, buyer debit, seller credit, snapshots and
cart clearing inside one `engine.begin()` transaction. Acquire shared resource
locks in a stable order and retry the whole transaction on serialization failure.
Repeated independent `app.db.execute()` calls do not form one purchase transaction.

Stock edits and removal use an atomic predicate on the last observed quantity.
If checkout changes stock before the edit commits, the write retries or returns
409 instead of silently replacing that stock. Seller writes retry complete
transactions up to three attempts for SQLSTATE 40001/40P01.

Fulfillment atomically updates `fulfilled_at` only while it is null and the line
belongs to the current user. Repeating the operation returns the original
timestamp. It never changes money or inventory; checkout owns those changes.
The buyer's order view can derive whole-order fulfillment from all item timestamps.

## Integration boundary

This branch includes the teammate's existing read-only Cart and Wishlist. It does
not implement checkout, buyer order management, product creation or the final
Users role/profile migration. Future `is_seller`, account field renames or
per-seller pricing should be agreed across modules before their migrations land.
The existing login allows a user to begin selling by adding a listing.

Demo initialization creates synthetic paid-order fixtures in a new database.
Those fixtures support module verification and are not an implementation of
checkout. `tools/setup_sellers.py` refuses existing names and never runs DROP.
