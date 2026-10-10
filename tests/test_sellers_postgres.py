"""Opt-in native PostgreSQL tests; reset only a separately created verification DB.

Set SELLERS_POSTGRES_TEST=1 and SELLERS_TEST_DB=mini_amazon_sellers_verify_*.
The suite never accepts the normal application/course database as its target.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import subprocess
import sys
from threading import Barrier
from time import perf_counter
import unittest

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@unittest.skipUnless(os.environ.get('SELLERS_POSTGRES_TEST') == '1', 'Opt-in isolated PostgreSQL suite.')
class SellerPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_dotenv(ROOT / '.flaskenv', override=False)
        database = os.environ.get('SELLERS_TEST_DB', '')
        if not re.fullmatch(r'mini_amazon_sellers_verify_[A-Za-z0-9_]+', database):
            raise RuntimeError('Refusing to reset a database outside mini_amazon_sellers_verify_*.')
        cls.database = database
        cls.url = URL.create('postgresql+psycopg2', database=database,
                             host=os.environ['DB_HOST'], port=os.environ['DB_PORT'],
                             username=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'])
        engine = create_engine(cls.url)
        with engine.connect() as connection:
            if connection.execute(text('SELECT current_database()')).scalar_one() != database:
                raise RuntimeError('Connected database does not match the verified target.')
            print('PostgreSQL:', connection.execute(text('SHOW server_version')).scalar_one())
        engine.dispose()

    def setUp(self):
        from app import create_app
        from tools.setup_sellers import load_small_fixtures, seed_demo
        self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY='postgres-test-only')
        self.app.db.engine.dispose()
        self.app.db.engine = create_engine(self.url, isolation_level='SERIALIZABLE')
        with self.app.db.engine.begin() as connection:
            if connection.execute(text('SELECT current_database()')).scalar_one() != self.database:
                raise RuntimeError('Database guard failed.')
            connection.exec_driver_sql('''TRUNCATE OrderItems, CartItems, Inventory, Orders,
                                           Wishes, Purchases, Products, Users RESTART IDENTITY''')
            load_small_fixtures(connection)
            self.fixture = seed_demo(connection)
        self.one, self.two = self.fixture['sellers']
        self.buyer = self.fixture['buyer']
        self.client = self.app.test_client()

    def tearDown(self):
        self.app.db.engine.dispose()

    def scalar(self, sql, params=None):
        with self.app.db.engine.connect() as connection:
            return connection.execute(text(sql), params or {}).scalar()

    def login(self, email='seller.one@example.com'):
        from tools.setup_sellers import DEMO_PASSWORD
        self.client.get('/logout')
        response = self.client.get('/login')
        token = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', response.data).group(1).decode()
        response = self.client.post('/login', data={'email': email, 'password': DEMO_PASSWORD, 'csrf_token': token})
        self.assertEqual(response.status_code, 302)

    def token(self):
        response = self.client.get('/seller/inventory')
        self.assertEqual(response.status_code, 200)
        return re.search(rb'<meta name="csrf-token" content="([^"]+)"', response.data).group(1).decode()

    def post(self, path, body=None):
        return self.client.post(path, json=body or {}, headers={'X-CSRFToken': self.token()})

    def test_real_login_inventory_m3_endpoint_and_csrf(self):
        self.assertEqual(self.client.get('/seller/inventory').status_code, 302)
        self.login()
        data = self.client.get('/api/seller/inventory?seller_id=999999').get_json()
        self.assertEqual(data['total'], 4)
        self.assertEqual(self.client.get('/seller').status_code, 200)
        self.assertEqual(self.client.get('/seller/inventory/add').status_code, 200)
        self.assertEqual(self.client.post('/api/seller/inventory', json={'product_id': 5, 'quantity': 2}).status_code, 400)
        self.assertEqual(self.post('/api/seller/inventory', {'product_id': 5, 'quantity': 2}).status_code, 201)
        self.assertEqual(self.post('/api/seller/inventory', {'product_id': 5, 'quantity': 3}).status_code, 409)
        self.assertEqual(self.post('/api/seller/inventory/5/quantity', {'quantity': 0, 'expected_quantity': 2}).status_code, 200)

    def test_native_constraints_and_no_partial_changes(self):
        order_id = self.fixture['orders'][0]
        statements = [
            'UPDATE Inventory SET quantity=-1',
            'UPDATE Users SET balance=-1',
            'UPDATE Products SET price=0 WHERE id=1',
            'UPDATE CartItems SET quantity=0',
            'INSERT INTO Inventory(seller_id,product_id,quantity) VALUES(999999,1,1)',
            f"INSERT INTO Orders(buyer_id,buyer_name_snapshot,shipping_address_snapshot) VALUES({self.buyer},'Buyer',' ')",
            f"INSERT INTO OrderItems(order_id,seller_id,product_id,product_name_snapshot,quantity,unit_price) VALUES({order_id},{self.one},1,'Duplicate',1,2.99)",
        ]
        balance = self.scalar('SELECT SUM(balance) FROM Users')
        for statement in statements:
            with self.subTest(statement=statement), self.assertRaises(IntegrityError):
                with self.app.db.engine.begin() as connection:
                    connection.execute(text(statement))
        self.assertEqual(self.scalar('SELECT SUM(balance) FROM Users'), balance)

    def test_multi_seller_fulfillment_and_historical_snapshots(self):
        self.login()
        order_id = self.fixture['orders'][0]
        detail = self.client.get(f'/api/seller/orders/{order_id}').get_json()
        self.assertEqual(detail['total'], '5.98')
        self.assertEqual(len(detail['items']), 1)
        stock = self.scalar('SELECT SUM(quantity) FROM Inventory')
        balance = self.scalar('SELECT SUM(balance) FROM Users')
        item_id = detail['items'][0]['id']
        self.assertEqual(self.post(f'/api/seller/order-items/{item_id}/fulfill').status_code, 200)
        timestamp = self.scalar('SELECT fulfilled_at FROM OrderItems WHERE id=:id', {'id': item_id})
        self.assertTrue(self.post(f'/api/seller/order-items/{item_id}/fulfill').get_json()['item']['already_fulfilled'])
        self.assertEqual(self.scalar('SELECT fulfilled_at FROM OrderItems WHERE id=:id', {'id': item_id}), timestamp)
        self.assertFalse(self.client.get(f'/api/seller/orders/{order_id}').get_json()['overall_fulfilled'])
        other_line = self.scalar('SELECT id FROM OrderItems WHERE order_id=:order AND seller_id=:seller',
                                 {'order': order_id, 'seller': self.two})
        self.assertEqual(self.post(f'/api/seller/order-items/{other_line}/fulfill').status_code, 404)
        self.login('seller.two@example.com')
        self.assertEqual(self.post(f'/api/seller/order-items/{other_line}/fulfill').status_code, 200)
        self.login()
        self.assertTrue(self.client.get(f'/api/seller/orders/{order_id}').get_json()['overall_fulfilled'])
        self.assertEqual(self.scalar('SELECT SUM(quantity) FROM Inventory'), stock)
        self.assertEqual(self.scalar('SELECT SUM(balance) FROM Users'), balance)
        with self.app.db.engine.begin() as connection:
            connection.execute(text("UPDATE Products SET name='Changed product',price=99 WHERE id=1"))
            connection.execute(text("UPDATE Users SET address='Changed buyer address' WHERE id=:buyer"), {'buyer': self.buyer})
        detail = self.client.get(f'/api/seller/orders/{order_id}').get_json()
        self.assertEqual(detail['total'], '5.98')
        self.assertIn('316 Demo Lane', detail['shipping_address_snapshot'])
        self.assertEqual(detail['items'][0]['product_name_snapshot'], 'vanilla ice cream')
        self.assertTrue(detail['items'][0]['fulfilled_at'].endswith('Z'))

    def test_removing_listing_preserves_cart_and_fulfillment(self):
        self.login()
        quantity = self.scalar('SELECT quantity FROM Inventory WHERE seller_id=:seller AND product_id=1', {'seller': self.one})
        self.assertEqual(self.post('/api/seller/inventory/1/remove', {'expected_quantity': quantity}).status_code, 200)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM CartItems WHERE seller_id=:seller AND product_id=1', {'seller': self.one}), 1)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM OrderItems WHERE seller_id=:seller AND product_id=1', {'seller': self.one}), 2)
        self.login('buyer.demo@example.com')
        cart = self.client.get('/api/cart').get_json()
        self.assertFalse(next(item for item in cart['items'] if item['seller_id'] == self.one)['available'])

    def test_two_concurrent_stock_updates_keep_one_winner(self):
        from app.models.seller import Seller, SellerError
        expected = self.scalar('SELECT quantity FROM Inventory WHERE seller_id=:seller AND product_id=1', {'seller': self.one})
        barrier = Barrier(2)
        def update(quantity):
            with self.app.app_context():
                barrier.wait(timeout=10)
                try:
                    Seller.update_listing(self.one, 1, quantity, expected)
                    return 200
                except SellerError as error:
                    return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(update, [101, 202]))
        self.assertEqual(sorted(results), [200, 409])
        self.assertIn(self.scalar('SELECT quantity FROM Inventory WHERE seller_id=:seller AND product_id=1', {'seller': self.one}), [101, 202])

    def test_two_concurrent_fulfillments_record_one_timestamp(self):
        from app.models.seller import Seller
        item = self.scalar('SELECT MIN(id) FROM OrderItems WHERE seller_id=:seller AND fulfilled_at IS NULL', {'seller': self.one})
        before = self.scalar('SELECT SUM(balance) FROM Users')
        stock = self.scalar('SELECT SUM(quantity) FROM Inventory')
        barrier = Barrier(2)
        def fulfill(_):
            with self.app.app_context():
                barrier.wait(timeout=10)
                return Seller.fulfill(self.one, item)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(fulfill, [1, 2]))
        self.assertEqual(sorted(item['already_fulfilled'] for item in results), [False, True])
        self.assertEqual(results[0]['fulfilled_at'], results[1]['fulfilled_at'])
        self.assertEqual(self.scalar('SELECT SUM(balance) FROM Users'), before)
        self.assertEqual(self.scalar('SELECT SUM(quantity) FROM Inventory'), stock)

    def test_sellers_migration_is_repeatable_and_preserves_rows(self):
        from tools.setup_sellers import execute_sql
        before = self.scalar('SELECT SUM(balance) FROM Users')
        count = self.scalar('SELECT COUNT(*) FROM OrderItems')
        with self.app.db.engine.begin() as connection:
            execute_sql(connection, ROOT / 'db' / 'sellers_schema.sql')
            execute_sql(connection, ROOT / 'db' / 'sellers_schema.sql')
        self.assertEqual(self.scalar('SELECT SUM(balance) FROM Users'), before)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM OrderItems'), count)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM pg_indexes WHERE indexname IN ('inventory_product_stock_idx','orderitems_seller_pending_idx')"), 2)

    def test_dashboard_uses_utc_days_with_a_different_server_timezone(self):
        placed = datetime.now(timezone.utc).replace(hour=1, minute=30, second=0, microsecond=0)
        with self.app.db.engine.begin() as connection:
            connection.exec_driver_sql("SET TIME ZONE 'America/New_York'")
            connection.execute(text('UPDATE Orders SET placed_at=:placed'), {'placed': placed})
        self.login()
        overview = self.client.get('/api/seller/overview').get_json()
        self.assertEqual([day['day'] for day in overview['days']], [placed.date().isoformat()])
        self.assertEqual(overview['days'][0]['revenue'], overview['sales']['revenue'])

    def test_setup_refuses_existing_database_without_modifying_it(self):
        before = self.scalar('SELECT SUM(balance) FROM Users')
        result = subprocess.run([sys.executable, 'tools/setup_sellers.py', '--database', self.database, '--no-config'],
                                cwd=ROOT, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('Nothing was changed', result.stderr)
        self.assertEqual(self.scalar('SELECT SUM(balance) FROM Users'), before)

    def test_ten_thousand_orders_remain_paginated_and_private(self):
        with self.app.db.engine.begin() as connection:
            connection.execute(text('''
INSERT INTO Orders(buyer_id,placed_at,buyer_name_snapshot,shipping_address_snapshot)
SELECT :buyer, CURRENT_TIMESTAMP - g * INTERVAL '1 minute', 'Load test buyer', 'Synthetic address'
FROM generate_series(1,10000) g
'''), {'buyer': self.buyer})
            connection.execute(text('''
INSERT INTO OrderItems(order_id,seller_id,product_id,product_name_snapshot,quantity,unit_price)
SELECT id,:seller,1,'Load test product',1,2.99 FROM Orders WHERE buyer_name_snapshot='Load test buyer'
'''), {'seller': self.one})
        self.login()
        started = perf_counter()
        response = self.client.get('/api/seller/orders')
        elapsed = perf_counter() - started
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual((data['total'], len(data['items'])), (10003, 20))
        print(f'10,003 seller orders: page of 20 returned in {elapsed:.3f}s on the verification host.')
        self.login('seller.two@example.com')
        self.assertEqual(self.client.get('/api/seller/orders').get_json()['total'], 2)


if __name__ == '__main__':
    unittest.main()
