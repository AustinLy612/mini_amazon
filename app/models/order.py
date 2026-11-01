"""Buyer queries against the shared M2 order and immutable line snapshots."""

from decimal import Decimal
from flask import current_app


class Order:
    @staticmethod
    def for_buyer(buyer_id):
        rows = current_app.db.execute("""
SELECT o.id, o.placed_at, COUNT(i.id) AS line_count,
       COALESCE(SUM(i.quantity), 0) AS item_count,
       COALESCE(SUM(i.quantity * i.unit_price), 0) AS total,
       SUM(CASE WHEN i.fulfilled_at IS NOT NULL THEN 1 ELSE 0 END) AS fulfilled_count
FROM Orders o JOIN OrderItems i ON i.order_id = o.id
WHERE o.buyer_id = :buyer_id
GROUP BY o.id, o.placed_at
ORDER BY o.placed_at DESC, o.id DESC
""", buyer_id=buyer_id)
        return [dict(id=r[0], placed_at=r[1], line_count=r[2], item_count=r[3],
                     total=Decimal(str(r[4])).quantize(Decimal('0.01')),
                     status=('Fulfilled' if r[5] == r[2] else
                             'Partially fulfilled' if r[5] else 'Unfulfilled')) for r in rows]

    @staticmethod
    def detail(buyer_id, order_id):
        rows = current_app.db.execute("""
SELECT id, placed_at, buyer_name_snapshot, shipping_address_snapshot
FROM Orders WHERE id = :order_id AND buyer_id = :buyer_id
""", buyer_id=buyer_id, order_id=order_id)
        if not rows:
            return None
        row = rows[0]
        items = current_app.db.execute("""
SELECT i.product_id, i.seller_id, i.product_name_snapshot, i.quantity,
       i.unit_price, i.fulfilled_at, u.firstname || ' ' || u.lastname
FROM OrderItems i JOIN Users u ON u.id = i.seller_id
WHERE i.order_id = :order_id ORDER BY i.id
""", order_id=order_id)
        lines = [dict(product_id=i[0], seller_id=i[1], name=i[2], quantity=i[3],
                      unit_price=Decimal(str(i[4])).quantize(Decimal('0.01')),
                      fulfilled_at=i[5], seller_name=i[6]) for i in items]
        return dict(id=row[0], placed_at=row[1], buyer_name=row[2], address=row[3],
                    items=lines, total=sum((i['quantity'] * i['unit_price'] for i in lines), Decimal('0.00')))
