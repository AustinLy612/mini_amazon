from flask import Blueprint, jsonify, render_template
from flask_login import current_user, login_required

from .models.cart import Cart

bp = Blueprint('carts', __name__)


@bp.route('/cart')
@login_required
def cart():
    # The authenticated identity is authoritative; never accept a buyer id from a form.
    items = Cart.get_items(current_user.id)
    return render_template('cart.html', items=items, total=Cart.total(items))


@bp.route('/api/cart')
@login_required
def cart_json():
    items = Cart.get_items(current_user.id)
    return jsonify(items=[dict(item, unit_price=format(item['unit_price'], '.2f'),
                               subtotal=format(item['subtotal'], '.2f')) for item in items],
                   total=format(Cart.total(items), '.2f'))
