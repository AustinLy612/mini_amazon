"""Create a NEW PostgreSQL development database without replacing existing data."""

import argparse
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import secrets

from dotenv import load_dotenv, set_key
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from werkzeug.security import generate_password_hash


ROOT = Path(__file__).resolve().parents[1]
DEMO_PASSWORD = 'SellerDemo2026!'


def read_sql(path):
    """Expand the skeleton's relative includes; let the caller own one transaction."""
    path = path.resolve()
    if not path.is_relative_to(ROOT / 'db'):
        raise ValueError('SQL includes must remain in this repository db directory.')
    lines = []
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.strip().startswith('\\ir '):
            lines.append(read_sql(path.parent / line.strip()[4:].strip()))
        elif re.fullmatch(r'\s*(BEGIN|COMMIT);\s*', line, flags=re.IGNORECASE):
            continue
        else:
            lines.append(line)
    return '\n'.join(lines)


def load_small_fixtures(connection):
    raw = connection.connection.driver_connection
    columns = {
        'Users': 'id,email,password,firstname,lastname',
        'Products': 'id,name,price,available',
        'Purchases': 'id,uid,pid,time_purchased',
        'Wishes': 'id,uid,pid,time_added',
    }
    with raw.cursor() as cursor:
        for table in ['Users', 'Products', 'Purchases', 'Wishes']:
            with (ROOT / 'db' / 'data' / (table + '.csv')).open(encoding='utf-8', newline='') as source:
                cursor.copy_expert(f"COPY {table} ({columns[table]}) FROM STDIN WITH (FORMAT CSV, NULL '')", source)
            cursor.execute(f"SELECT setval('public.{table.lower()}_id_seq', "
                           f'(SELECT COALESCE(MAX(id)+1,1) FROM {table}), false)')


def execute_sql(connection, path):
    # A one-argument DBAPI call preserves literal % in PostgreSQL procedure bodies.
    with connection.connection.driver_connection.cursor() as cursor:
        cursor.execute(read_sql(path))


def seed_demo(connection):
    """Synthetic paid orders only; this is a fixture, not a checkout endpoint."""
    password = generate_password_hash(DEMO_PASSWORD)
    people = [
        ('seller.one@example.com', 'Morgan', 'Seller', '17 Market Street', 0),
        ('seller.two@example.com', 'Taylor', 'Seller', '24 Market Street', 0),
        ('buyer.demo@example.com', 'Demo', 'Buyer', '316 Demo Lane\nDurham, NC 27708', 1000),
    ]
    ids = []
    for email, first, last, address, balance in people:
        ids.append(connection.execute(text('''
INSERT INTO Users(email,password,firstname,lastname,address,balance)
VALUES(:email,:password,:first,:last,:address,:balance) RETURNING id
'''), dict(email=email, password=password, first=first, last=last,
           address=address, balance=balance)).scalar_one())
    seller_one, seller_two, buyer = ids
    products = connection.execute(text('SELECT id,name,price FROM Products ORDER BY id LIMIT 3')).mappings().all()
    if len(products) < 3:
        raise RuntimeError('Demo requires at least three products.')
    by_id = {product['id']: product for product in products}
    p1, p2, p3 = [product['id'] for product in products]
    for seller, stock in [(seller_one, 20), (seller_two, 12)]:
        for product in products:
            connection.execute(text('INSERT INTO Inventory(seller_id,product_id,quantity) VALUES(:seller,:product,:quantity)'),
                               dict(seller=seller, product=product['id'], quantity=stock))
    fourth = connection.execute(text('SELECT id FROM Products ORDER BY id OFFSET 3 LIMIT 1')).scalar()
    if fourth is not None:
        connection.execute(text('INSERT INTO Inventory(seller_id,product_id,quantity) VALUES(:seller,:product,0)'),
                           dict(seller=seller_one, product=fourth))
    now = datetime.now(timezone.utc)
    examples = [
        (now - timedelta(days=2), [(seller_one, p1, 2, False), (seller_two, p2, 1, False)]),
        (now - timedelta(days=1), [(seller_one, p3, 1, True)]),
        (now - timedelta(hours=2), [(seller_one, p1, 1, True), (seller_one, p2, 2, False), (seller_two, p3, 1, False)]),
    ]
    order_ids = []
    for placed_at, lines in examples:
        order_id = connection.execute(text('''
INSERT INTO Orders(buyer_id,placed_at,buyer_name_snapshot,shipping_address_snapshot)
VALUES(:buyer,:placed,'Demo Buyer','316 Demo Lane\nDurham, NC 27708') RETURNING id
'''), {'buyer': buyer, 'placed': placed_at}).scalar_one()
        order_ids.append(order_id)
        for seller, product_id, quantity, fulfilled in lines:
            product = by_id[product_id]
            total = product['price'] * quantity
            connection.execute(text('''
INSERT INTO OrderItems(order_id,seller_id,product_id,product_name_snapshot,quantity,unit_price,fulfilled_at)
VALUES(:order,:seller,:product,:name,:quantity,:price,:fulfilled)
'''), dict(order=order_id, seller=seller, product=product_id, name=product['name'],
           quantity=quantity, price=product['price'],
           fulfilled=placed_at + timedelta(hours=1) if fulfilled else None))
            connection.execute(text('UPDATE Users SET balance=balance-:amount WHERE id=:buyer'),
                               dict(amount=total, buyer=buyer))
            connection.execute(text('UPDATE Users SET balance=balance+:amount WHERE id=:seller'),
                               dict(amount=total, seller=seller))
            connection.execute(text('''UPDATE Inventory SET quantity=quantity-:quantity
                                        WHERE seller_id=:seller AND product_id=:product'''),
                               dict(quantity=quantity, seller=seller, product=product_id))
    for seller, product, quantity in [(seller_one, p1, 1), (seller_two, p2, 2)]:
        connection.execute(text('INSERT INTO CartItems(buyer_id,seller_id,product_id,quantity) VALUES(:buyer,:seller,:product,:quantity)'),
                           dict(buyer=buyer, seller=seller, product=product, quantity=quantity))
    return {'sellers': [seller_one, seller_two], 'buyer': buyer, 'orders': order_ids}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', default='mini_amazon_sellers_dev')
    parser.add_argument('--demo', action='store_true', help='Load two demo sellers and synthetic paid orders.')
    parser.add_argument('--no-config', action='store_true', help='Do not create a local .flaskenv.')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,62}', args.database):
        parser.error('Database name must be a PostgreSQL identifier of at most 63 characters.')
    load_dotenv(ROOT / '.flaskenv', override=False)
    settings = {
        'host': os.environ.get('DB_HOST') or os.environ.get('PGHOST'),
        'port': os.environ.get('DB_PORT') or os.environ.get('PGPORT') or '5432',
        'username': os.environ.get('DB_USER') or os.environ.get('PGUSER'),
        'password': os.environ.get('DB_PASSWORD') or os.environ.get('PGPASSWORD'),
    }
    if not settings['host'] or not settings['username'] or settings['password'] is None:
        parser.error('Set DB_HOST/DB_USER/DB_PASSWORD or the corresponding course PG variables.')
    admin = create_engine(URL.create('postgresql+psycopg2', database='postgres', **settings),
                          isolation_level='AUTOCOMMIT')
    try:
        with admin.connect() as connection:
            exists = connection.execute(text('SELECT 1 FROM pg_database WHERE datname=:name'),
                                        {'name': args.database}).scalar()
            if exists:
                parser.exit(2, f'{args.database} already exists. Nothing was changed. Use another fresh name.\n')
            # The identifier is strictly validated above; PostgreSQL cannot bind identifiers.
            connection.exec_driver_sql(f'CREATE DATABASE "{args.database}"')
    finally:
        admin.dispose()
    engine = create_engine(URL.create('postgresql+psycopg2', database=args.database, **settings))
    try:
        with engine.begin() as connection:
            execute_sql(connection, ROOT / 'db' / 'create.sql')
            load_small_fixtures(connection)
            execute_sql(connection, ROOT / 'db' / 'carts_schema.sql')
            execute_sql(connection, ROOT / 'db' / 'sellers_schema.sql')
            if args.demo:
                seed_demo(connection)
    except Exception:
        print('Initialization failed and the schema transaction was rolled back. '
              'The new database was retained for inspection; no existing database was touched.')
        raise
    finally:
        engine.dispose()
    config = ROOT / '.flaskenv'
    if not args.no_config and not config.exists():
        descriptor = os.open(config, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        values = {'FLASK_APP': 'amazon.py', 'FLASK_RUN_HOST': '127.0.0.1', 'FLASK_RUN_PORT': '8080',
                  'SECRET_KEY': secrets.token_hex(32), 'DB_NAME': args.database,
                  'DB_HOST': settings['host'], 'DB_PORT': settings['port'],
                  'DB_USER': settings['username'], 'DB_PASSWORD': settings['password']}
        for key, value in values.items():
            set_key(str(config), key, str(value))
        print('Created local .flaskenv; credentials were not printed.')
    elif args.no_config:
        print('Local configuration was not changed (--no-config).')
    else:
        print('Existing configuration was preserved. Set DB_NAME to the new database before starting.')
    print(f'Ready: {args.database}. Start with poetry run flask run --host 0.0.0.0 --port 8080 in the course container.')
    if args.demo:
        print('Demo accounts: seller.one@example.com, seller.two@example.com, buyer.demo@example.com')
        print('Demo password: ' + DEMO_PASSWORD)


if __name__ == '__main__':
    main()
