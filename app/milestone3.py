"""Four SQL-backed milestone queries, with HTML and JSON representations."""

from datetime import date, datetime
from decimal import Decimal
from functools import wraps
import re

from flask import Blueprint, abort, current_app, jsonify, render_template, request
from flask_login import current_user

from .models.cart import Cart
from .models.order import Order
from .models.product import Product
from .models.seller import Seller

bp = Blueprint('milestone3', __name__)


def json_value(value):
    if isinstance(value, Decimal):
        return format(value, '.2f')
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    return value


def authenticated(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.path.startswith('/api/'):
                return jsonify(error='Authentication required.'), 401
            return current_app.login_manager.unauthorized()
        return function(*args, **kwargs)
    return wrapped


def require_owner(uid):
    if str(uid) != str(current_user.id):
        abort(403)


@bp.route('/milestone3')
def overview():
    return render_template('milestone3/overview.html')


@bp.route('/products/top')
@bp.route('/api/products/top', endpoint='top_products_json')
def top_products():
    raw = request.args.get('k', '5')
    if not re.fullmatch(r'[0-9]{1,4}', raw) or not 1 <= int(raw) <= 1000:
        message = 'k must be a whole number between 1 and 1000.'
        if request.path.startswith('/api/'):
            return jsonify(error=message), 400
        return render_template('milestone3/products.html', products=[], k=raw, error=message), 400
    k = int(raw)
    products = Product.top_k(k)
    if request.path.startswith('/api/'):
        return jsonify(json_value(dict(k=k, count=len(products), products=products)))
    return render_template('milestone3/products.html', products=products, k=k, error=None)


@bp.route('/account/purchases')
@bp.route('/api/users/<int:uid>/purchases')
@authenticated
def purchases(uid=None):
    uid = current_user.id if uid is None else uid
    require_owner(uid)
    orders = Order.for_buyer(uid)
    if request.path.startswith('/api/'):
        return jsonify(json_value(dict(user_id=int(uid), orders=orders, count=len(orders))))
    return render_template('milestone3/purchases.html', orders=orders)


@bp.route('/orders/<int:order_id>')
@bp.route('/api/users/<int:uid>/orders/<int:order_id>')
@authenticated
def order_detail(order_id, uid=None):
    uid = current_user.id if uid is None else uid
    require_owner(uid)
    order = Order.detail(uid, order_id)
    if order is None:
        abort(404)
    if request.path.startswith('/api/'):
        return jsonify(json_value(order))
    return render_template('milestone3/order.html', order=order)


@bp.route('/api/users/<int:uid>/cart')
@authenticated
def cart_by_user(uid):
    require_owner(uid)
    items = Cart.get_items(uid)
    return jsonify(json_value(dict(user_id=uid, items=items, total=Cart.total(items))))


@bp.route('/api/sellers/<int:uid>/inventory')
@authenticated
def inventory_by_seller(uid):
    require_owner(uid)
    # The existing seller query supplies stable pagination and all listings,
    # including zero stock. Requests cannot substitute another seller identity.
    raw = request.args.get('page', '1')
    if not re.fullmatch(r'[0-9]{1,6}', raw) or int(raw) < 1:
        return jsonify(error='page must be a positive whole number.'), 400
    return jsonify(json_value(dict(seller_id=uid, **Seller.inventory(uid, page=int(raw)))))


@bp.errorhandler(403)
@bp.errorhandler(404)
def private_error(error):
    message = 'This account is not accessible.' if error.code == 403 else 'Order not found.'
    if request.path.startswith('/api/'):
        return jsonify(error=message), error.code
    return render_template('milestone3/error.html', message=message), error.code
