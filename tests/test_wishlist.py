"""Tutorial flow through real routes, SQL and templates, with CSRF enabled."""
import re
import unittest

from sqlalchemy import text
from werkzeug.security import generate_password_hash
import test_cart


class WishlistTests(unittest.TestCase):
    login = test_cart.CartTests.login
    tearDown = test_cart.CartTests.tearDown
    def setUp(self):
        test_cart.CartTests.setUp(self)
        with self.app.db.engine.begin() as conn:
            conn.execute(text("UPDATE Users SET email='buyer@example.com' WHERE id=1"))
            conn.execute(text('ALTER TABLE Users ADD COLUMN password TEXT'))
            conn.execute(text('UPDATE Users SET password=:password'),
                         {'password': generate_password_hash('test-password')})
            conn.execute(text('CREATE TABLE Purchases (id INTEGER PRIMARY KEY, uid INTEGER, pid INTEGER, time_purchased TIMESTAMP)'))
            conn.execute(text('''CREATE TABLE Wishes (id INTEGER PRIMARY KEY,
                uid INTEGER NOT NULL REFERENCES Users(id),
                pid INTEGER NOT NULL REFERENCES Products(id),
                time_added TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)'''))

    def token(self, response):
        return re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', response.data).group(1).decode()

    def test_login_add_read_logout_and_user_isolation(self):
        token = self.token(self.client.get('/login'))
        response = self.client.post('/login', data={
            'email': 'buyer@example.com', 'password': 'test-password', 'csrf_token': token})
        self.assertEqual(response.status_code, 302)
        home = self.client.get('/')
        self.assertIn(b'Add to Wishlist', home.data)
        response = self.client.post('/wishlist/add/10', data={
            'csrf_token': self.token(home), 'uid': '2'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Your wishlist', response.data)
        data = self.client.get('/api/wishlist').get_json()
        self.assertEqual([(i['uid'], i['pid']) for i in data], [(1, 10)])
        self.client.get('/logout')
        self.assertEqual(self.client.get('/wishlist').status_code, 302)
        self.login(2)
        self.assertEqual(self.client.get('/api/wishlist').get_json(), [])
        self.assertIn(b'Your wishlist is empty', self.client.get('/wishlist').data)
        self.login(1)
        self.assertEqual(len(self.client.get('/api/wishlist').get_json()), 1)

    def test_csrf_missing_product_and_method(self):
        self.login(1)
        self.assertEqual(self.client.post('/wishlist/add/10').status_code, 400)
        self.assertEqual(self.client.get('/wishlist/add/10').status_code, 405)
        token = self.token(self.client.get('/'))
        self.assertEqual(self.client.post('/wishlist/add/999', data={'csrf_token': token}).status_code, 404)
        self.assertEqual(self.client.get('/api/wishlist').get_json(), [])

    def test_guest_cannot_add_or_read_wishlist(self):
        for path in ('/wishlist', '/api/wishlist'):
            self.assertEqual(self.client.get(path).status_code, 302)
        self.assertEqual(self.client.post('/wishlist/add/10').status_code, 302)

    def test_tutorial_allows_repeated_add_and_orders_newest_first(self):
        self.login(1)
        token = self.token(self.client.get('/'))
        for _ in range(2):
            self.client.post('/wishlist/add/10', data={'csrf_token': token})
        data = self.client.get('/api/wishlist').get_json()
        self.assertEqual(len(data), 2)
        self.assertGreater(data[0]['id'], data[1]['id'])
