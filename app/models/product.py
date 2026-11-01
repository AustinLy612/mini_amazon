from flask import current_app as app


class Product:
    @staticmethod
    def top_k(k):
        rows = app.db.execute('''
SELECT id, name, price FROM Products
ORDER BY price DESC, id ASC LIMIT :k
''', k=k)
        from decimal import Decimal
        return [dict(id=r[0], name=r[1], price=Decimal(str(r[2])).quantize(Decimal('0.01')))
                for r in rows]

    def __init__(self, id, name, price, available):
        self.id = id
        self.name = name
        self.price = price
        self.available = available

    @staticmethod
    def get(id):
        rows = app.db.execute('''
SELECT id, name, price, available
FROM Products
WHERE id = :id
''',
                              id=id)
        return Product(*(rows[0])) if rows else None

    @staticmethod
    def get_all(available=True):
        rows = app.db.execute('''
SELECT id, name, price, available
FROM Products
WHERE available = :available
''',
                              available=available)
        return [Product(*row) for row in rows]
