"""Read-path integration tests; SQLite does not validate PostgreSQL migration/locking."""
import os
import unittest
from decimal import Decimal

for key, value in {'DB_PASSWORD': '', 'DB_USER': 'test', 'DB_HOST': 'localhost', 'DB_PORT': '5432', 'DB_NAME': 'test'}.items():
    os.environ.setdefault(key, value)
from sqlalchemy import create_engine, text
from app import create_app
from app.models.cart import Cart


class CartTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY='test-only')
        self.app.db.engine.dispose()
        self.app.db.engine = create_engine('sqlite://')
        statements = [
            'CREATE TABLE Users (id INTEGER PRIMARY KEY, email TEXT, firstname TEXT, lastname TEXT)',
            'CREATE TABLE Products (id INTEGER PRIMARY KEY, name TEXT, price NUMERIC, available BOOLEAN)',
            'CREATE TABLE Inventory (seller_id INTEGER, product_id INTEGER, quantity INTEGER)',
            'CREATE TABLE CartItems (buyer_id INTEGER, seller_id INTEGER, product_id INTEGER, quantity INTEGER)',
            "INSERT INTO Users VALUES (1,'a@t.test','Buyer','One'), (2,'b@t.test','Buyer','Two'), (3,'s@t.test','Seller','One'), (4,'x@t.test','Seller','Two')",
            "INSERT INTO Products VALUES (10,'Tea <special>',2.99,1),(11,'Coffee',0.1,1)",
            'INSERT INTO Inventory VALUES (3,10,5),(4,10,0),(3,11,2)',
            'INSERT INTO CartItems VALUES (1,3,10,2),(1,4,10,1),(2,3,11,3)',
        ]
        with self.app.db.engine.begin() as conn:
            for statement in statements:
                conn.execute(text(statement))
        self.client = self.app.test_client()

    def tearDown(self):
        self.app.db.engine.dispose()

    def login(self, uid):
        with self.client.session_transaction() as session:
            session['_user_id'] = str(uid)
            session['_fresh'] = True

    def test_guest_cannot_query_cart(self):
        for path in ('/cart', '/api/cart'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertIn('/login?', response.location)

    def test_owner_isolation_and_decimal_total(self):
        self.login(1)
        data = self.client.get('/api/cart?buyer_id=2').get_json()
        self.assertEqual(data['total'], '8.97')
        self.assertEqual([x['seller_id'] for x in data['items']], [3, 4])
        self.assertEqual(data['items'][0]['subtotal'], '5.98')
        self.assertFalse(data['items'][1]['available'])
        self.login(2)
        data = self.client.get('/api/cart').get_json()
        self.assertEqual(data['total'], '0.30')
        self.assertEqual(len(data['items']), 1)

    def test_html_escapes_names_and_explains_unavailable(self):
        self.login(1)
        response = self.client.get('/cart')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Tea &lt;special&gt;', response.data)
        self.assertIn(b'Unavailable', response.data)
        self.assertIn(b'$8.97', response.data)
        self.login(2)
        self.assertIn(b'Only 2 left', self.client.get('/cart').data)

    def test_empty_cart(self):
        self.login(3)
        self.assertIn(b'Your cart is empty', self.client.get('/cart').data)
        self.assertEqual(self.client.get('/api/cart').get_json(), {'items': [], 'total': '0.00'})

    def test_logout_and_new_session_preserve_cart(self):
        self.login(1)
        before = self.client.get('/api/cart').get_json()
        self.client.get('/logout')
        self.assertEqual(self.client.get('/cart').status_code, 302)
        self.client = self.app.test_client()
        self.login(1)
        self.assertEqual(before, self.client.get('/api/cart').get_json())

    def test_removed_listing_remains_visible(self):
        with self.app.db.engine.begin() as conn:
            conn.execute(text('DELETE FROM Inventory WHERE seller_id=3 AND product_id=10'))
        self.login(1)
        data = self.client.get('/api/cart').get_json()
        self.assertEqual(len(data['items']), 2)
        removed = data['items'][0]
        self.assertEqual(removed['stock'], 0)
        self.assertFalse(removed['available'])
        self.assertEqual(data['total'], '8.97')
        self.assertIn(b'Tea &lt;special&gt;', self.client.get('/cart').data)

    def test_query_parameter_binding(self):
        with self.app.app_context():
            self.assertEqual(Cart.get_items('1 OR 1=1'), [])
            self.assertEqual(Cart.total([]), Decimal('0.00'))


if __name__ == '__main__':
    unittest.main()
