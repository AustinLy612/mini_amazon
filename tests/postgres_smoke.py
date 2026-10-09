"""Run only on a fresh verification DB loaded with the small skeleton fixtures.

From the repository root:
DB_NAME=mini_amazon_m2_verify_20261008 poetry run python -c \
    'import runpy; runpy.run_path("tests/postgres_smoke.py", run_name="__main__")'
"""
import os
import re
from decimal import Decimal
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

load_dotenv('.flaskenv', override=False)
if not os.environ.get('DB_NAME', '').startswith('mini_amazon_m2_verify_'):
    raise RuntimeError('Use a separate mini_amazon_m2_verify_* database.')

from app import create_app


def token(response):
    return re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', response.data).group(1).decode()


def login(client):
    response = client.post('/login', data={
        'email': 'icecream@tastes.good', 'password': 'test123',
        'csrf_token': token(client.get('/login'))})
    assert response.status_code == 302, response.status_code


app = create_app()
app.config['TESTING'] = True
client = app.test_client()
assert client.get('/cart').status_code == 302
login(client)
cart = client.get('/api/cart').get_json()
assert len(cart['items']) == 2
assert Decimal(cart['total']) == sum(Decimal(i['subtotal']) for i in cart['items'])
assert client.get('/cart').status_code == 200
before = client.get('/api/wishlist').get_json()
response = client.post('/wishlist/add/1', data={'csrf_token': token(client.get('/'))}, follow_redirects=True)
assert response.status_code == 200 and b'Your wishlist' in response.data
assert len(client.get('/api/wishlist').get_json()) == len(before) + 1
assert client.post('/wishlist/add/1').status_code == 400
assert client.post('/wishlist/add/999999', data={'csrf_token': token(client.get('/'))}).status_code == 404
client.get('/logout')
assert client.get('/wishlist').status_code == 302
app.db.engine.dispose()
# A fresh application and database connection see committed records.
app2 = create_app()
app2.config['TESTING'] = True
client2 = app2.test_client()
login(client2)
assert len(client2.get('/api/wishlist').get_json()) == len(before) + 1
assert client2.get('/api/cart').get_json() == cart
seller = cart['items'][0]['seller_id']
with client2.session_transaction() as session:
    session['_user_id'] = str(seller)
    session['_fresh'] = True
assert client2.get('/api/cart').get_json()['items'] == []
assert client2.get('/api/wishlist').get_json() == []
# Exercise PostgreSQL constraints, always rolling back these invalid writes.
statements = [
    'UPDATE CartItems SET quantity=0 WHERE buyer_id=0',
    'UPDATE Inventory SET quantity=-1',
    'UPDATE Users SET balance=-1 WHERE id=0',
    "INSERT INTO Orders(buyer_id,buyer_name_snapshot,shipping_address_snapshot) VALUES(0,'Buyer',' ')",
    'INSERT INTO CartItems(buyer_id,seller_id,product_id,quantity) VALUES(0,999999,1,1)',
    'UPDATE Products SET price=0 WHERE id=1',
]
for sql in statements:
    try:
        with app2.db.engine.begin() as conn:
            conn.execute(text(sql))
            raise AssertionError('Constraint accepted invalid data: ' + sql)
    except IntegrityError:
        pass
# Verify listing deletion keeps the cart row; rollback the fixture change.
with app2.db.engine.connect() as conn:
    tx = conn.begin()
    conn.execute(text('DELETE FROM Inventory WHERE seller_id=:seller AND product_id=1'), {'seller': seller})
    assert conn.execute(text('SELECT count(*) FROM CartItems WHERE buyer_id=0 AND product_id=1')).scalar() == 1
    tx.rollback()
# Check final column names and identity/uniqueness using a rolled-back order.
with app2.db.engine.connect() as conn:
    tx = conn.begin()
    order_id = conn.execute(text("INSERT INTO Orders(buyer_id,buyer_name_snapshot,shipping_address_snapshot) VALUES(0,'Demo Buyer','Demo Address') RETURNING id")).scalar()
    line_id = conn.execute(text("INSERT INTO OrderItems(order_id,seller_id,product_id,product_name_snapshot,quantity,unit_price) VALUES(:order,:seller,1,'Snapshot',2,1.00) RETURNING id"), {'order': order_id, 'seller': seller}).scalar()
    assert isinstance(line_id, int)
    try:
        with conn.begin_nested():
            conn.execute(text("INSERT INTO OrderItems(order_id,seller_id,product_id,product_name_snapshot,quantity,unit_price) VALUES(:order,:seller,1,'Snapshot',1,1.00)"), {'order': order_id, 'seller': seller})
    except IntegrityError:
        pass
    else:
        raise AssertionError('Duplicate order line accepted')
    tx.rollback()
app2.db.engine.dispose()
print('PASS: PostgreSQL schema, real login, cart totals, wishlist POST/HTML, CSRF, missing product, user isolation, fresh-app persistence, six invalid-write checks, listing deletion, snapshot columns and order-line identity/uniqueness.')
