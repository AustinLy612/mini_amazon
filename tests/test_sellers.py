"""Seller routes, authorization and real SQL. PostgreSQL checks live separately."""

from datetime import datetime, timezone
import os
import re
import unittest
from unittest.mock import patch

for key, value in {'DB_PASSWORD': '', 'DB_USER': 'test', 'DB_HOST': 'localhost',
                   'DB_PORT': '5432', 'DB_NAME': 'test'}.items():
    os.environ.setdefault(key, value)

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from werkzeug.security import generate_password_hash

from app import create_app
from app.models.seller import Seller, SellerError, _write


class SellerTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY='seller-test-only')
        self.app.db.engine.dispose()
        self.app.db.engine = create_engine('sqlite://')
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(' ')
        statements = [
            '''CREATE TABLE Users (id INTEGER PRIMARY KEY, email TEXT UNIQUE,
               password TEXT, firstname TEXT, lastname TEXT, address TEXT, balance NUMERIC)''',
            'CREATE TABLE Products (id INTEGER PRIMARY KEY, name TEXT, price NUMERIC, available BOOLEAN)',
            '''CREATE TABLE Inventory (seller_id INTEGER, product_id INTEGER,
               quantity INTEGER CHECK(quantity >= 0), PRIMARY KEY(seller_id, product_id))''',
            '''CREATE TABLE CartItems (buyer_id INTEGER, seller_id INTEGER,
               product_id INTEGER, quantity INTEGER)''',
            '''CREATE TABLE Orders (id INTEGER PRIMARY KEY, buyer_id INTEGER, placed_at TIMESTAMP,
               buyer_name_snapshot TEXT, shipping_address_snapshot TEXT)''',
            '''CREATE TABLE OrderItems (id INTEGER PRIMARY KEY, order_id INTEGER,
               seller_id INTEGER, product_id INTEGER, product_name_snapshot TEXT,
               quantity INTEGER, unit_price NUMERIC, fulfilled_at TIMESTAMP)''',
            """INSERT INTO Users VALUES
               (1,'buyer@example.com','unused','Buyer','One','New address',1000),
               (2,'buyer2@example.com','unused','Buyer','Two','Other address',1000),
               (3,'seller@example.com','unused','Seller','One','Seller address',100),
               (4,'seller2@example.com','unused','Seller','Two','Seller address',100),
               (5,'new@example.com','unused','New','Seller','Seller address',0)""",
            """INSERT INTO Products VALUES (10,'Tea <special>',2.99,1),
               (11,'Coffee & cream',0.10,1),(12,'50% off_notes',4.99,0)""",
            'INSERT INTO Inventory VALUES (3,10,5),(4,10,6),(3,11,0)',
            'INSERT INTO CartItems VALUES (1,3,10,2),(1,4,10,1)',
            """INSERT INTO Orders VALUES
               (100,1,'2026-01-01 12:00:00','Original Buyer <name>','Original delivery address'),
               (101,2,'2026-02-01 12:00:00','Second Buyer','Second address'),
               (102,2,'2026-03-01 12:00:00','Other private buyer','Other private address')""",
            """INSERT INTO OrderItems VALUES
               (1000,100,3,10,'Original tea <snapshot>',2,2.99,NULL),
               (1001,100,4,11,'OTHER SELLER PRIVATE ITEM',3,50,NULL),
               (1002,101,3,10,'Historic tea',1,3.50,NULL),
               (1003,101,3,11,'Historic coffee',2,0.10,'2026-02-02 10:00:00'),
               (1004,102,4,10,'Only other seller',1,999,NULL)""",
        ]
        with self.app.db.engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
            connection.execute(text('UPDATE Orders SET placed_at=:now WHERE id=101'), {'now': now})
            connection.execute(text('UPDATE Users SET password=:password WHERE id=3'),
                               {'password': generate_password_hash('seller-test-password')})
        self.client = self.app.test_client()

    def tearDown(self):
        self.app.db.engine.dispose()

    def login(self, user_id=3):
        with self.client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True

    def token(self):
        response = self.client.get('/seller/inventory')
        self.assertEqual(response.status_code, 200)
        return re.search(rb'<meta name="csrf-token" content="([^"]+)"', response.data).group(1).decode()

    def post(self, path, data=None):
        return self.client.post(path, json=data or {}, headers={'X-CSRFToken': self.token()})

    def scalar(self, sql, params=None):
        with self.app.db.engine.connect() as connection:
            return connection.execute(text(sql), params or {}).scalar()

    def test_guest_html_and_json_protection(self):
        for path in ['/seller', '/seller/inventory', '/seller/inventory/add', '/seller/orders', '/seller/orders/100']:
            self.assertEqual(self.client.get(path).status_code, 302)
        for path in ['/api/seller/overview', '/api/seller/inventory', '/api/seller/orders', '/api/seller/orders/100']:
            self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.client.post('/api/seller/inventory', json={}).status_code, 401)

    def test_inventory_identity_cannot_be_overridden(self):
        self.login()
        data = self.client.get('/api/seller/inventory?seller_id=4').get_json()
        self.assertEqual(data['total'], 2)
        self.assertEqual([row['product_id'] for row in data['items']], [11, 10])
        self.assertEqual(data['items'][1]['quantity'], 5)
        self.assertEqual(data['items'][1]['price'], '2.99')
        self.login(4)
        self.assertEqual(self.client.get('/api/seller/inventory').get_json()['total'], 1)

    def test_add_zero_stock_duplicate_and_missing_product(self):
        self.login()
        response = self.post('/api/seller/inventory', {'product_id': 12, 'quantity': 0, 'seller_id': 4})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.scalar('SELECT quantity FROM Inventory WHERE seller_id=3 AND product_id=12'), 0)
        self.assertEqual(self.post('/api/seller/inventory', {'product_id': 12, 'quantity': 99}).status_code, 409)
        self.assertEqual(self.scalar('SELECT quantity FROM Inventory WHERE seller_id=3 AND product_id=12'), 0)
        self.assertEqual(self.post('/api/seller/inventory', {'product_id': 99999, 'quantity': 1}).status_code, 404)

    def test_mutations_require_csrf(self):
        self.login()
        for path, body in [('/api/seller/inventory', {'product_id': 12, 'quantity': 5}),
                           ('/api/seller/inventory/10/quantity', {'quantity': 9, 'expected_quantity': 5}),
                           ('/api/seller/inventory/10/remove', {'expected_quantity': 5}),
                           ('/api/seller/order-items/1000/fulfill', {})]:
            self.assertEqual(self.client.post(path, json=body).status_code, 400)
        self.assertEqual(self.scalar('SELECT quantity FROM Inventory WHERE seller_id=3 AND product_id=10'), 5)
        self.assertIsNone(self.scalar('SELECT fulfilled_at FROM OrderItems WHERE id=1000'))

    def test_invalid_quantities_do_not_write(self):
        self.login()
        for value in [-1, 'one', '1.5', 1.5, True, '1e3', 2_147_483_648, None]:
            with self.subTest(value=value):
                response = self.post('/api/seller/inventory/10/quantity',
                                     {'quantity': value, 'expected_quantity': 5})
                self.assertEqual(response.status_code, 422, response.data)
        self.assertEqual(self.scalar('SELECT quantity FROM Inventory WHERE seller_id=3 AND product_id=10'), 5)

    def test_quantity_update_and_concurrent_stock_conflict(self):
        self.login()
        self.assertEqual(self.post('/api/seller/inventory/10/quantity',
                                  {'quantity': 0, 'expected_quantity': 5, 'seller_id': 4}).status_code, 200)
        stale = self.post('/api/seller/inventory/10/quantity', {'quantity': 20, 'expected_quantity': 5})
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(self.post('/api/seller/inventory/10/remove', {'expected_quantity': 5}).status_code, 409)
        self.assertEqual(self.scalar('SELECT quantity FROM Inventory WHERE seller_id=3 AND product_id=10'), 0)
        self.assertEqual(self.scalar('SELECT quantity FROM Inventory WHERE seller_id=4 AND product_id=10'), 6)

    def test_listing_ownership_and_catalog_exclusion(self):
        self.login(4)
        self.assertEqual(self.post('/api/seller/inventory/11/quantity', {'quantity': 1, 'expected_quantity': 0}).status_code, 404)
        self.assertEqual(self.post('/api/seller/inventory/11/remove', {'expected_quantity': 0}).status_code, 404)
        self.login()
        catalog = self.client.get('/seller/inventory/add').data
        self.assertIn(b'50% off_notes', catalog)
        self.assertNotIn(b'Tea &lt;special&gt;', catalog)

    def test_removal_preserves_carts_history_and_other_seller(self):
        self.login()
        self.assertEqual(self.post('/api/seller/inventory/10/remove', {'expected_quantity': 5}).status_code, 200)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM CartItems'), 2)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM OrderItems WHERE product_id=10'), 3)
        self.assertEqual(self.scalar('SELECT quantity FROM Inventory WHERE seller_id=4 AND product_id=10'), 6)
        self.assertEqual(self.client.get('/api/seller/orders/100').status_code, 200)
        self.login(1)
        cart = self.client.get('/api/cart').get_json()
        removed = next(row for row in cart['items'] if row['seller_id'] == 3)
        self.assertFalse(removed['available'])
        self.assertEqual(removed['stock'], 0)

    def test_literal_search_and_query_validation(self):
        self.login()
        self.post('/api/seller/inventory', {'product_id': 12, 'quantity': 1})
        for query, total in [('50%', 1), ('off_', 1), ("' OR 1=1 --", 0), ('10', 1)]:
            response = self.client.get('/api/seller/inventory', query_string={'q': query})
            self.assertEqual(response.get_json()['total'], total)
        for params in [{'page': '-1'}, {'page': '1 OR 1=1'}, {'page': '0'}, {'q': 'x' * 101}, {'sort': 'price;DROP TABLE Users'}]:
            self.assertEqual(self.client.get('/api/seller/inventory', query_string=params).status_code, 400)
        self.assertEqual(self.client.get('/api/seller/orders?status=unknown').status_code, 400)

    def test_pagination_sort_and_empty_seller(self):
        self.login()
        with self.app.db.engine.begin() as connection:
            for product_id in range(20, 45):
                connection.execute(text('INSERT INTO Products VALUES(:id,:name,1,1)'),
                                   {'id': product_id, 'name': f'Extra {product_id}'})
                connection.execute(text('INSERT INTO Inventory VALUES(3,:id,:quantity)'),
                                   {'id': product_id, 'quantity': product_id})
        data = self.client.get('/api/seller/inventory?sort=stock_high&page=2').get_json()
        self.assertEqual((data['total'], data['pages'], len(data['items'])), (27, 2, 7))
        self.assertEqual(self.client.get('/api/seller/inventory?page=999').get_json()['page'], 2)
        self.login(5)
        self.assertEqual(self.client.get('/api/seller/inventory').get_json()['items'], [])
        self.assertIn(b'Start your first listing', self.client.get('/seller/inventory').data)

    def test_orders_include_only_owned_lines_and_totals(self):
        self.login()
        data = self.client.get('/api/seller/orders?seller_id=4').get_json()
        self.assertEqual([row['id'] for row in data['items']], [101, 100])
        self.assertEqual([(row['total'], row['item_count']) for row in data['items']], [('3.70', 3), ('5.98', 2)])
        order = self.client.get('/api/seller/orders/100').get_json()
        self.assertEqual([row['id'] for row in order['items']], [1000])
        self.assertNotIn('OTHER SELLER PRIVATE ITEM', str(order))
        self.assertFalse(order['overall_fulfilled'])
        self.assertEqual(self.client.get('/api/seller/orders/102').status_code, 404)

    def test_order_search_keeps_full_owned_summary(self):
        self.login()
        for query, expected in [('Historic coffee', [101]), ('Original delivery', [100]), ('buyer2@example.com', [101]), ('100', [100]), ('OTHER SELLER PRIVATE ITEM', []), ("' OR 1=1 --", [])]:
            result = self.client.get('/api/seller/orders', query_string={'q': query}).get_json()
            self.assertEqual([row['id'] for row in result['items']], expected)
            if query == 'Historic coffee':
                self.assertEqual((result['items'][0]['total'], result['items'][0]['line_count']), ('3.70', 2))

    def test_order_snapshots_survive_profile_and_product_edits(self):
        self.login()
        with self.app.db.engine.begin() as connection:
            connection.execute(text("UPDATE Products SET name='New name',price=999 WHERE id=10"))
            connection.execute(text("UPDATE Users SET firstname='Renamed',address='New address' WHERE id=1"))
        order = self.client.get('/api/seller/orders/100').get_json()
        self.assertEqual(order['buyer_name_snapshot'], 'Original Buyer <name>')
        self.assertEqual(order['shipping_address_snapshot'], 'Original delivery address')
        self.assertEqual((order['items'][0]['product_name_snapshot'], order['total']), ('Original tea <snapshot>', '5.98'))

    def test_fulfillment_is_owned_and_idempotent_without_money_or_stock_writes(self):
        self.login()
        balances = self.scalar('SELECT SUM(balance) FROM Users')
        stock = self.scalar('SELECT SUM(quantity) FROM Inventory')
        first = self.post('/api/seller/order-items/1000/fulfill')
        self.assertEqual(first.status_code, 200)
        self.assertFalse(first.get_json()['item']['already_fulfilled'])
        timestamp = self.scalar('SELECT fulfilled_at FROM OrderItems WHERE id=1000')
        second = self.post('/api/seller/order-items/1000/fulfill')
        self.assertTrue(second.get_json()['item']['already_fulfilled'])
        self.assertEqual(self.scalar('SELECT fulfilled_at FROM OrderItems WHERE id=1000'), timestamp)
        self.assertEqual(self.scalar('SELECT SUM(balance) FROM Users'), balances)
        self.assertEqual(self.scalar('SELECT SUM(quantity) FROM Inventory'), stock)
        self.assertEqual(self.post('/api/seller/order-items/1001/fulfill').status_code, 404)
        self.assertEqual(self.post('/api/seller/order-items/99999/fulfill').status_code, 404)

    def test_multi_seller_overall_status_and_status_filters(self):
        self.login()
        self.post('/api/seller/order-items/1000/fulfill')
        order = self.client.get('/api/seller/orders/100').get_json()
        self.assertEqual(order['status'], 'fulfilled')
        self.assertFalse(order['overall_fulfilled'])
        self.assertEqual([row['id'] for row in self.client.get('/api/seller/orders?status=fulfilled').get_json()['items']], [100])
        self.assertEqual([row['id'] for row in self.client.get('/api/seller/orders?status=pending').get_json()['items']], [101])
        self.login(4)
        self.post('/api/seller/order-items/1001/fulfill')
        self.login()
        self.assertTrue(self.client.get('/api/seller/orders/100').get_json()['overall_fulfilled'])

    def test_public_product_sellers_use_inventory_and_hide_private_information(self):
        data = self.client.get('/api/sellers/products/10').get_json()
        self.assertEqual([row['seller_id'] for row in data['sellers']], [4, 3])
        self.assertNotIn('balance', str(data))
        self.assertNotIn('email', str(data))
        self.assertNotIn('address', str(data))
        self.assertEqual(self.client.get('/api/sellers/products/99999').status_code, 404)
        self.login()
        self.post('/api/seller/inventory', {'product_id': 12, 'quantity': 7})
        data = self.client.get('/api/sellers/products/12').get_json()
        self.assertTrue(data['sellers'][0]['available'])  # Legacy Products.available is false.

    def test_dashboard_aggregates_only_own_sales(self):
        self.login()
        data = self.client.get('/api/seller/overview').get_json()
        self.assertEqual(data['stock'], {'listings': 2, 'out_of_stock': 1, 'stock_units': 5})
        self.assertEqual(data['sales'], {'orders': 2, 'units_sold': 5, 'pending_lines': 2, 'revenue': '9.68'})
        self.assertEqual(len(data['days']), 1)
        self.assertNotIn('999.00', str(data))

    def test_html_routes_forms_escape_snapshots_and_do_not_leak_other_seller(self):
        self.login()
        for path in ['/seller', '/seller/inventory', '/seller/inventory/add', '/seller/orders', '/seller/orders/100']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertIn(b'csrf-token', response.data)
        detail = self.client.get('/seller/orders/100').data
        self.assertIn(b'Original tea &lt;snapshot&gt;', detail)
        self.assertIn(b'Original Buyer &lt;name&gt;', detail)
        self.assertNotIn(b'OTHER SELLER PRIVATE ITEM', detail)
        response = self.client.post('/seller/inventory/10/quantity',
                                    data={'quantity': '4', 'expected_quantity': '5', 'csrf_token': self.token()},
                                    follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Inventory quantity updated.', response.data)

    def test_real_login_logout_and_session_identity(self):
        response = self.client.get('/login')
        token = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', response.data).group(1).decode()
        response = self.client.post('/login', data={'email': 'seller@example.com',
                                    'password': 'seller-test-password', 'csrf_token': token})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get('/api/seller/inventory').get_json()['total'], 2)
        self.client.get('/logout')
        self.assertEqual(self.client.get('/api/seller/orders').status_code, 401)

    def test_serialization_retries_entire_transaction_and_is_bounded(self):
        calls = []
        class Conflict(Exception):
            pgcode = '40001'
        def operation(connection):
            calls.append(1)
            connection.execute(text('UPDATE Inventory SET quantity=99 WHERE seller_id=3 AND product_id=10'))
            if len(calls) < 3:
                raise DBAPIError('test', {}, Conflict())
            return 'committed'
        with self.app.app_context(), patch('app.models.seller.sleep'):
            self.assertEqual(_write(operation), 'committed')
        self.assertEqual(len(calls), 3)
        self.assertEqual(self.scalar('SELECT quantity FROM Inventory WHERE seller_id=3 AND product_id=10'), 99)
        def always_conflict(connection):
            connection.execute(text('UPDATE Inventory SET quantity=123 WHERE seller_id=3 AND product_id=10'))
            raise DBAPIError('test', {}, Conflict())
        with self.app.app_context(), patch('app.models.seller.sleep'):
            with self.assertRaises(SellerError) as caught:
                _write(always_conflict)
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(self.scalar('SELECT quantity FROM Inventory WHERE seller_id=3 AND product_id=10'), 99)


if __name__ == '__main__':
    unittest.main()
