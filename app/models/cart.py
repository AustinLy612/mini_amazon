from decimal import Decimal

from flask import current_app as app


class Cart:
    """Read-only starter; all cart totals use current product prices."""

    @staticmethod
    def get_items(buyer_id):
        rows = app.db.execute("""
SELECT c.product_id, c.seller_id, p.name,
       u.firstname || ' ' || u.lastname AS seller_name,
       c.quantity, p.price AS unit_price, i.quantity AS stock,
       (i.active AND COALESCE(p.available, FALSE)) AS available
FROM CartItems c
JOIN Products p ON p.id = c.product_id
JOIN Users u ON u.id = c.seller_id
JOIN Inventory i ON i.seller_id = c.seller_id AND i.product_id = c.product_id
WHERE c.buyer_id = :buyer_id
ORDER BY c.product_id, c.seller_id
""", buyer_id=buyer_id)
        items = []
        for row in rows:
            product_id, seller_id, name, seller_name, quantity, price, stock, available = row
            unit_price = Decimal(str(price))
            items.append(dict(product_id=product_id, seller_id=seller_id,
                              name=name, seller_name=seller_name, quantity=quantity,
                              unit_price=unit_price, subtotal=unit_price * quantity,
                              stock=stock, available=bool(available)))
        return items

    @staticmethod
    def total(items):
        return sum((item['subtotal'] for item in items), Decimal('0.00'))
