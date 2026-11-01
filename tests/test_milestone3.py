"""End-to-end SQL, JSON and template coverage for the four M3 requirements."""

import unittest
from sqlalchemy import text
import test_sellers


class Milestone3Tests(unittest.TestCase):
    setUp = test_sellers.SellerTests.setUp
    tearDown = test_sellers.SellerTests.tearDown
    login = test_sellers.SellerTests.login

    def test_all_four_queries_have_html_and_json(self):
        overview = self.client.get('/milestone3')
        self.assertIn(b'action="/products/top"', overview.data)
        self.assertNotIn(b'action="/api/products/top"', overview.data)
        self.login(1)
        for path in ['/milestone3', '/products/top?k=2', '/account/purchases', '/orders/100', '/cart']:
            self.assertEqual(self.client.get(path).status_code, 200, path)
        for path in ['/api/products/top?k=2', '/api/users/1/purchases', '/api/users/1/cart']:
            self.assertEqual(self.client.get(path).status_code, 200, path)
        self.login(3)
        self.assertEqual(self.client.get('/seller/inventory').status_code, 200)
        self.assertEqual(self.client.get('/api/sellers/3/inventory').status_code, 200)

    def test_purchases_use_final_prices_and_all_sellers(self):
        self.login(1)
        data = self.client.get('/api/users/1/purchases').get_json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['orders'][0]['total'], '155.98')
        self.assertEqual(data['orders'][0]['item_count'], 5)
        self.assertEqual(data['orders'][0]['status'], 'Unfulfilled')
        with self.app.db.engine.begin() as c:
            c.execute(text('UPDATE Products SET price=9999'))
        self.assertEqual(self.client.get('/api/users/1/purchases').get_json(), data)
        detail = self.client.get('/api/users/1/orders/100').get_json()
        self.assertEqual(detail['total'], '155.98')
        self.assertEqual(detail['address'], 'Original delivery address')
        self.assertEqual(len(detail['items']), 2)

    def test_purchase_ordering_empty_and_statuses(self):
        self.login(2)
        orders = self.client.get('/api/users/2/purchases').get_json()['orders']
        expected = sorted(orders, key=lambda o: (o['placed_at'], o['id']), reverse=True)
        self.assertEqual(orders, expected)
        self.assertEqual(next(o for o in orders if o['id'] == 101)['status'], 'Partially fulfilled')
        with self.app.db.engine.begin() as c:
            c.execute(text("UPDATE OrderItems SET fulfilled_at='2026-11-01' WHERE order_id=101"))
        self.assertEqual(next(o for o in self.client.get('/api/users/2/purchases').get_json()['orders']
                              if o['id'] == 101)['status'], 'Fulfilled')
        self.login(5)
        self.assertEqual(self.client.get('/api/users/5/purchases').get_json()['orders'], [])
        self.assertIn(b'no purchases', self.client.get('/account/purchases').data)

    def test_private_ids_and_guests_cannot_leak_data(self):
        for path in ['/api/users/1/purchases', '/api/users/1/cart', '/api/sellers/3/inventory']:
            self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.client.get('/account/purchases').status_code, 302)
        self.login(1)
        for path in ['/api/users/2/purchases', '/api/users/2/orders/101', '/api/users/2/cart', '/api/sellers/3/inventory']:
            self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.get('/orders/101').status_code, 404)
        self.assertEqual(self.client.get('/orders/999').status_code, 404)
        self.assertEqual(self.client.get('/api/users/1/purchases?buyer_id=2').get_json()['count'], 1)

    def test_top_k_limits_ties_and_unavailable_products(self):
        with self.app.db.engine.begin() as c:
            c.execute(text("INSERT INTO Products VALUES(13,'Same price',4.99,1)"))
        data = self.client.get('/api/products/top?k=2').get_json()
        self.assertEqual([p['id'] for p in data['products']], [12, 13])
        self.assertEqual(data['products'][0]['price'], '4.99')
        self.assertEqual(self.client.get('/api/products/top?k=1000').get_json()['count'], 4)
        for k in ['0', '-1', '1.5', '1001', '1 OR 1=1', '', '999999999999']:
            self.assertEqual(self.client.get('/api/products/top', query_string={'k': k}).status_code, 400, k)
        self.assertEqual(self.client.get('/products/top?k=abc').status_code, 400)

    def test_empty_catalog_and_escaped_names(self):
        self.assertIn(b'Tea &lt;special&gt;', self.client.get('/products/top?k=3').data)
        with self.app.db.engine.begin() as c:
            c.execute(text('DELETE FROM Products'))
        self.assertEqual(self.client.get('/api/products/top?k=3').get_json()['products'], [])

    def test_cart_inventory_queries_use_given_owner(self):
        self.login(1)
        self.assertEqual(self.client.get('/api/users/1/cart').get_json()['total'], '8.97')
        self.login(3)
        inventory = self.client.get('/api/sellers/3/inventory').get_json()
        self.assertEqual(inventory['total'], 2)
        self.assertIn(0, [p['quantity'] for p in inventory['items']])
        self.assertEqual(self.client.get('/api/sellers/3/inventory?page=0').status_code, 400)


if __name__ == '__main__':
    unittest.main()
