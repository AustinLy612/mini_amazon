"""Opt-in read-only checks against a separately seeded PostgreSQL demo DB."""

import os
import re
import unittest
from decimal import Decimal

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


@unittest.skipUnless(os.environ.get('M3_POSTGRES_TEST') == '1', 'Opt-in PostgreSQL M3 checks.')
class Milestone3PostgresTests(unittest.TestCase):
    def setUp(self):
        from app import create_app
        name = os.environ['M3_TEST_DB']
        if not name.startswith('mini_amazon_m3_'):
            raise RuntimeError('Use a separately seeded mini_amazon_m3_* database.')
        self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY='m3-postgres-test-only')
        self.app.db.engine.dispose()
        self.app.db.engine = create_engine(URL.create(
            'postgresql+psycopg2', database=name, host=os.environ['DB_HOST'],
            port=os.environ['DB_PORT'], username=os.environ['DB_USER'], password=os.environ['DB_PASSWORD']))
        self.client = self.app.test_client()

    def tearDown(self):
        self.app.db.engine.dispose()

    def login(self, email):
        from tools.setup_sellers import DEMO_PASSWORD
        page = self.client.get('/login')
        token = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', page.data).group(1).decode()
        response = self.client.post('/login', data=dict(email=email, password=DEMO_PASSWORD, csrf_token=token))
        self.assertEqual(response.status_code, 302)
        with self.app.db.engine.connect() as c:
            return c.execute(text('SELECT id FROM Users WHERE email=:email'), {'email': email}).scalar_one()

    def test_top_k_uses_postgres_ordering_and_bind_limit(self):
        data = self.client.get('/api/products/top?k=3').get_json()
        with self.app.db.engine.connect() as c:
            ids = c.execute(text('SELECT id FROM Products ORDER BY price DESC,id LIMIT 3')).scalars().all()
        self.assertEqual([p['id'] for p in data['products']], ids)
        self.assertEqual(self.client.get('/products/top?k=2').status_code, 200)
        self.assertEqual(self.client.get('/api/products/top?k=1%20OR%201=1').status_code, 400)

    def test_purchase_snapshots_aggregates_and_buyer_detail(self):
        uid = self.login('buyer.demo@example.com')
        data = self.client.get(f'/api/users/{uid}/purchases').get_json()
        self.assertEqual(data['count'], 3)
        self.assertEqual([o['status'] for o in data['orders']], ['Partially fulfilled', 'Fulfilled', 'Unfulfilled'])
        with self.app.db.engine.connect() as c:
            total = c.execute(text('''SELECT SUM(i.quantity*i.unit_price) FROM OrderItems i
                                      JOIN Orders o ON o.id=i.order_id WHERE o.buyer_id=:uid'''), {'uid': uid}).scalar_one()
        self.assertEqual(sum(Decimal(o['total']) for o in data['orders']), total)
        self.assertEqual(self.client.get('/account/purchases').status_code, 200)
        order_id = data['orders'][0]['id']
        self.assertEqual(self.client.get(f'/orders/{order_id}').status_code, 200)
        self.assertEqual(self.client.get(f'/api/users/{uid+1}/purchases').status_code, 403)

    def test_persistent_cart_postgres_results(self):
        uid = self.login('buyer.demo@example.com')
        data = self.client.get(f'/api/users/{uid}/cart').get_json()
        self.assertEqual(len(data['items']), 2)
        self.assertEqual(data['total'], '8.97')
        self.assertEqual(self.client.get('/cart').status_code, 200)

    def test_seller_inventory_zero_stock_and_isolation(self):
        uid = self.login('seller.one@example.com')
        data = self.client.get(f'/api/sellers/{uid}/inventory').get_json()
        self.assertEqual(data['total'], 4)
        self.assertIn(0, [p['quantity'] for p in data['items']])
        self.assertEqual(self.client.get('/seller/inventory').status_code, 200)
        self.assertEqual(self.client.get(f'/api/sellers/{uid+1}/inventory').status_code, 403)
