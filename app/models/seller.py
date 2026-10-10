"""Seller queries and writes against the team's shared inventory/order schema."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from time import sleep

from flask import current_app
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError


MAX_QUANTITY = 2_147_483_647
MONEY = Decimal('0.01')


class SellerError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def money(value):
    return Decimal(str(value or 0)).quantize(MONEY)


def _search(value):
    # Treat %, _ and backslash as text rather than SQL wildcard syntax.
    value = value.strip()[:100]
    escaped = value.lower().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return {'query': value, 'pattern': '%' + escaped + '%'}


def _page(total, page, per_page):
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(max(1, page), pages)
    return {'page': page, 'per_page': per_page, 'total': total, 'pages': pages,
            'has_previous': page > 1, 'has_next': page < pages}


def _write(operation):
    """Retry the entire transaction on PostgreSQL serialization/deadlock failures."""
    for attempt in range(3):
        try:
            with current_app.db.engine.begin() as connection:
                return operation(connection)
        except DBAPIError as error:
            code = getattr(error.orig, 'pgcode', None)
            if code not in {'40001', '40P01'}:
                raise
            if attempt == 2:
                raise SellerError('Another request changed this data. Refresh and try again.', 409) from error
            sleep(0.02 * (attempt + 1))


class Seller:
    INVENTORY_SORTS = {
        'name': 'LOWER(p.name), p.id',
        'stock_low': 'i.quantity ASC, p.id',
        'stock_high': 'i.quantity DESC, p.id',
        'price_low': 'p.price ASC, p.id',
        'price_high': 'p.price DESC, p.id',
    }

    @staticmethod
    def inventory(seller_id, query='', sort='name', page=1, per_page=20):
        if sort not in Seller.INVENTORY_SORTS:
            raise SellerError('Choose a valid inventory sort order.')
        params = dict(_search(query), seller_id=seller_id)
        scope = """
FROM Inventory i JOIN Products p ON p.id = i.product_id
WHERE i.seller_id = :seller_id
AND (:query = '' OR LOWER(p.name) LIKE :pattern ESCAPE '\\'
     OR CAST(p.id AS TEXT) = :query)
"""
        with current_app.db.engine.begin() as connection:
            total = connection.execute(text('SELECT COUNT(*) ' + scope), params).scalar_one()
            pagination = _page(total, page, per_page)
            params.update(limit=per_page, offset=(pagination['page'] - 1) * per_page)
            rows = connection.execute(text('SELECT p.id AS product_id, p.name, p.price, i.quantity '
                                           + scope + ' ORDER BY ' + Seller.INVENTORY_SORTS[sort]
                                           + ' LIMIT :limit OFFSET :offset'), params).mappings().all()
        items = [dict(row, price=money(row['price'])) for row in rows]
        return dict(pagination, items=items)

    @staticmethod
    def catalog(seller_id, query='', page=1, per_page=20):
        params = dict(_search(query), seller_id=seller_id)
        scope = """
FROM Products p
WHERE NOT EXISTS (SELECT 1 FROM Inventory i
                  WHERE i.seller_id = :seller_id AND i.product_id = p.id)
AND (:query = '' OR LOWER(p.name) LIKE :pattern ESCAPE '\\'
     OR CAST(p.id AS TEXT) = :query)
"""
        with current_app.db.engine.begin() as connection:
            total = connection.execute(text('SELECT COUNT(*) ' + scope), params).scalar_one()
            pagination = _page(total, page, per_page)
            params.update(limit=per_page, offset=(pagination['page'] - 1) * per_page)
            rows = connection.execute(text('SELECT p.id AS product_id, p.name, p.price ' + scope
                                           + ' ORDER BY LOWER(p.name), p.id LIMIT :limit OFFSET :offset'),
                                      params).mappings().all()
        return dict(pagination, items=[dict(row, price=money(row['price'])) for row in rows])

    @staticmethod
    def add_listing(seller_id, product_id, quantity):
        Seller._quantity(quantity)

        def operation(connection):
            row = connection.execute(text("""
INSERT INTO Inventory (seller_id, product_id, quantity)
SELECT :seller_id, id, :quantity FROM Products WHERE id = :product_id
RETURNING product_id, quantity
"""), dict(seller_id=seller_id, product_id=product_id, quantity=quantity)).mappings().first()
            if row is None:
                raise SellerError('This product no longer exists.', 404)
            return dict(row)

        try:
            return _write(operation)
        except IntegrityError as error:
            # Duplicate rows never overwrite an existing listing or its stock.
            code = getattr(error.orig, 'pgcode', None)
            if code == '23505' or (code is None and 'UNIQUE' in str(error.orig).upper()):
                raise SellerError('You already list this product. Change its quantity in Inventory.', 409) from error
            if code == '23503':
                raise SellerError('This product or account is no longer available.', 404) from error
            raise

    @staticmethod
    def update_listing(seller_id, product_id, quantity, expected_quantity):
        Seller._quantity(quantity)
        Seller._quantity(expected_quantity)

        def operation(connection):
            row = connection.execute(text("""
UPDATE Inventory SET quantity = :quantity
WHERE seller_id = :seller_id AND product_id = :product_id
  AND quantity = :expected_quantity
RETURNING product_id, quantity
"""), dict(seller_id=seller_id, product_id=product_id,
           quantity=quantity, expected_quantity=expected_quantity)).mappings().first()
            if row is None:
                Seller._missing_or_changed(connection, seller_id, product_id)
            return dict(row)

        return _write(operation)

    @staticmethod
    def remove_listing(seller_id, product_id, expected_quantity):
        Seller._quantity(expected_quantity)

        def operation(connection):
            row = connection.execute(text("""
DELETE FROM Inventory
WHERE seller_id = :seller_id AND product_id = :product_id
  AND quantity = :expected_quantity
RETURNING product_id
"""), dict(seller_id=seller_id, product_id=product_id,
           expected_quantity=expected_quantity)).mappings().first()
            if row is None:
                Seller._missing_or_changed(connection, seller_id, product_id)
            return dict(row)

        # CartItems and OrderItems deliberately do not reference live Inventory.
        return _write(operation)

    @staticmethod
    def _quantity(value):
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_QUANTITY:
            raise SellerError('Quantity must be a whole number from 0 to 2,147,483,647.', 422)

    @staticmethod
    def _missing_or_changed(connection, seller_id, product_id):
        exists = connection.execute(text("""
SELECT 1 FROM Inventory WHERE seller_id = :seller_id AND product_id = :product_id
"""), dict(seller_id=seller_id, product_id=product_id)).first()
        if exists is None:
            raise SellerError('Listing not found.', 404)
        raise SellerError('Stock changed since you opened this page. Refresh before saving or removing it.', 409)

    @staticmethod
    def _order_scope(status):
        if status not in {'all', 'pending', 'fulfilled'}:
            raise SellerError('Choose a valid order status.')
        scope = """
FROM Orders o JOIN Users u ON u.id = o.buyer_id
JOIN OrderItems own ON own.order_id = o.id AND own.seller_id = :seller_id
WHERE (:query = '' OR CAST(o.id AS TEXT) = :query
       OR LOWER(o.buyer_name_snapshot) LIKE :pattern ESCAPE '\\'
       OR LOWER(o.shipping_address_snapshot) LIKE :pattern ESCAPE '\\'
       OR LOWER(u.email) LIKE :pattern ESCAPE '\\'
       OR EXISTS (SELECT 1 FROM OrderItems matched
                  WHERE matched.order_id = o.id AND matched.seller_id = :seller_id
                  AND LOWER(matched.product_name_snapshot) LIKE :pattern ESCAPE '\\'))
"""
        pending = """EXISTS (SELECT 1 FROM OrderItems pending
                              WHERE pending.order_id = o.id AND pending.seller_id = :seller_id
                              AND pending.fulfilled_at IS NULL)"""
        if status == 'pending':
            scope += ' AND ' + pending
        elif status == 'fulfilled':
            scope += ' AND NOT ' + pending
        return scope

    @staticmethod
    def _orders(connection, seller_id, query, status, page, per_page):
        scope = Seller._order_scope(status)
        params = dict(_search(query), seller_id=seller_id)
        total = connection.execute(text('SELECT COUNT(DISTINCT o.id) ' + scope), params).scalar_one()
        pagination = _page(total, page, per_page)
        params.update(limit=per_page, offset=(pagination['page'] - 1) * per_page)
        rows = connection.execute(text("""
SELECT o.id, o.placed_at, o.buyer_name_snapshot, o.shipping_address_snapshot,
       u.email AS buyer_email,
       COUNT(own.id) AS line_count, SUM(own.quantity) AS item_count,
       SUM(own.quantity * own.unit_price) AS total,
       SUM(CASE WHEN own.fulfilled_at IS NULL THEN 1 ELSE 0 END) AS pending_count,
       NOT EXISTS (SELECT 1 FROM OrderItems remaining
                   WHERE remaining.order_id = o.id AND remaining.fulfilled_at IS NULL) AS overall_fulfilled
""" + scope + """
GROUP BY o.id, o.placed_at, o.buyer_name_snapshot, o.shipping_address_snapshot, u.email
ORDER BY o.placed_at DESC, o.id DESC LIMIT :limit OFFSET :offset
"""), params).mappings().all()
        orders = [Seller._order_summary(dict(row)) for row in rows]
        return dict(pagination, items=orders)

    @staticmethod
    def orders(seller_id, query='', status='all', page=1, per_page=20):
        with current_app.db.engine.begin() as connection:
            return Seller._orders(connection, seller_id, query, status, page, per_page)

    @staticmethod
    def _order_summary(order):
        order['total'] = money(order['total'])
        order['overall_fulfilled'] = bool(order['overall_fulfilled'])
        order['status'] = ('fulfilled' if order['pending_count'] == 0 else
                           'pending' if order['pending_count'] == order['line_count'] else 'partial')
        return order

    @staticmethod
    def order(seller_id, order_id):
        with current_app.db.engine.begin() as connection:
            result = Seller._orders_for_id(connection, seller_id, order_id)
            if result is None:
                raise SellerError('Order not found.', 404)
            rows = connection.execute(text("""
SELECT id, product_id, product_name_snapshot, quantity, unit_price, fulfilled_at
FROM OrderItems WHERE order_id = :order_id AND seller_id = :seller_id ORDER BY id
"""), dict(order_id=order_id, seller_id=seller_id)).mappings().all()
        result['items'] = [dict(row, unit_price=money(row['unit_price']),
                                subtotal=money(row['unit_price']) * row['quantity']) for row in rows]
        return result

    @staticmethod
    def _orders_for_id(connection, seller_id, order_id):
        row = connection.execute(text("""
SELECT o.id, o.placed_at, o.buyer_name_snapshot, o.shipping_address_snapshot,
       u.email AS buyer_email, COUNT(own.id) AS line_count,
       SUM(own.quantity) AS item_count, SUM(own.quantity * own.unit_price) AS total,
       SUM(CASE WHEN own.fulfilled_at IS NULL THEN 1 ELSE 0 END) AS pending_count,
       NOT EXISTS (SELECT 1 FROM OrderItems remaining
                   WHERE remaining.order_id = o.id AND remaining.fulfilled_at IS NULL) AS overall_fulfilled
FROM Orders o JOIN Users u ON u.id = o.buyer_id
JOIN OrderItems own ON own.order_id = o.id AND own.seller_id = :seller_id
WHERE o.id = :order_id
GROUP BY o.id, o.placed_at, o.buyer_name_snapshot, o.shipping_address_snapshot, u.email
"""), dict(seller_id=seller_id, order_id=order_id)).mappings().first()
        return Seller._order_summary(dict(row)) if row is not None else None

    @staticmethod
    def fulfill(seller_id, item_id):
        def operation(connection):
            row = connection.execute(text("""
UPDATE OrderItems SET fulfilled_at = CURRENT_TIMESTAMP
WHERE id = :item_id AND seller_id = :seller_id AND fulfilled_at IS NULL
RETURNING id, order_id, fulfilled_at
"""), dict(item_id=item_id, seller_id=seller_id)).mappings().first()
            if row is not None:
                return dict(row, already_fulfilled=False)
            row = connection.execute(text("""
SELECT id, order_id, fulfilled_at FROM OrderItems
WHERE id = :item_id AND seller_id = :seller_id
"""), dict(item_id=item_id, seller_id=seller_id)).mappings().first()
            if row is None:
                raise SellerError('Order item not found.', 404)
            return dict(row, already_fulfilled=True)

        # Only the owned line timestamp changes. No stock or account writes occur.
        return _write(operation)

    @staticmethod
    def product_sellers(product_id):
        with current_app.db.engine.begin() as connection:
            product = connection.execute(text('SELECT id, name, price FROM Products WHERE id = :id'),
                                         {'id': product_id}).mappings().first()
            if product is None:
                raise SellerError('Product not found.', 404)
            rows = connection.execute(text("""
SELECT i.seller_id, u.firstname || ' ' || u.lastname AS seller_name, i.quantity
FROM Inventory i JOIN Users u ON u.id = i.seller_id
WHERE i.product_id = :product_id ORDER BY i.quantity DESC, i.seller_id
"""), {'product_id': product_id}).mappings().all()
        return {'product': dict(product, price=money(product['price'])),
                'sellers': [dict(row, available=row['quantity'] > 0) for row in rows]}

    @staticmethod
    def dashboard(seller_id):
        params = {'seller_id': seller_id,
                  'since': datetime.now(timezone.utc) - timedelta(days=30)}
        # TIMESTAMPTZ date casts otherwise depend on the database server's zone.
        day_expression = ("DATE(o.placed_at AT TIME ZONE 'UTC')"
                          if current_app.db.engine.dialect.name == 'postgresql'
                          else 'DATE(o.placed_at)')
        with current_app.db.engine.begin() as connection:
            stock = connection.execute(text("""
SELECT COUNT(*) AS listings,
       COALESCE(SUM(quantity), 0) AS stock_units,
       COALESCE(SUM(CASE WHEN quantity = 0 THEN 1 ELSE 0 END), 0) AS out_of_stock
FROM Inventory WHERE seller_id = :seller_id
"""), params).mappings().one()
            sales = connection.execute(text("""
SELECT COUNT(DISTINCT order_id) AS orders, COALESCE(SUM(quantity), 0) AS units_sold,
       COALESCE(SUM(quantity * unit_price), 0) AS revenue,
       COALESCE(SUM(CASE WHEN fulfilled_at IS NULL THEN 1 ELSE 0 END), 0) AS pending_lines
FROM OrderItems WHERE seller_id = :seller_id
"""), params).mappings().one()
            days = connection.execute(text(f"""
SELECT {day_expression} AS day, SUM(oi.quantity * oi.unit_price) AS revenue
FROM OrderItems oi JOIN Orders o ON o.id = oi.order_id
WHERE oi.seller_id = :seller_id AND o.placed_at >= :since
GROUP BY {day_expression} ORDER BY day
"""), params).mappings().all()
            top = connection.execute(text("""
SELECT oi.product_id, p.name, SUM(oi.quantity) AS units_sold,
       SUM(oi.quantity * oi.unit_price) AS revenue
FROM OrderItems oi JOIN Products p ON p.id = oi.product_id
WHERE oi.seller_id = :seller_id
GROUP BY oi.product_id, p.name ORDER BY units_sold DESC, oi.product_id LIMIT 5
"""), params).mappings().all()
            recent = Seller._orders(connection, seller_id, '', 'pending', 1, 5)['items']
        return {'stock': dict(stock), 'sales': dict(sales, revenue=money(sales['revenue'])),
                'days': [dict(row, revenue=money(row['revenue'])) for row in days],
                'top_products': [dict(row, revenue=money(row['revenue'])) for row in top],
                'recent_orders': recent}
