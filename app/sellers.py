"""Authenticated seller pages, JSON interfaces and CSRF-protected mutations."""

from datetime import date, datetime, timezone
from decimal import Decimal
from functools import wraps
import re

from flask import (Blueprint, current_app, flash, jsonify, redirect,
                   render_template, request, url_for)
from flask_login import current_user
from flask_wtf import FlaskForm
from werkzeug.datastructures import MultiDict
from wtforms import IntegerField, SubmitField
from wtforms.validators import InputRequired, NumberRange
from wtforms.widgets import HiddenInput

from .models.seller import MAX_QUANTITY, Seller, SellerError


bp = Blueprint('sellers', __name__)


class ListingForm(FlaskForm):
    product_id = IntegerField('Product', widget=HiddenInput(),
                              validators=[InputRequired(), NumberRange(min=0, max=MAX_QUANTITY)])
    quantity = IntegerField('Quantity', validators=[InputRequired(), NumberRange(min=0, max=MAX_QUANTITY)])
    submit = SubmitField('Add listing')


class QuantityForm(FlaskForm):
    quantity = IntegerField('Quantity', validators=[InputRequired(), NumberRange(min=0, max=MAX_QUANTITY)])
    expected_quantity = IntegerField('Previous quantity', widget=HiddenInput(),
                                    validators=[InputRequired(), NumberRange(min=0, max=MAX_QUANTITY)])


class RemoveForm(FlaskForm):
    expected_quantity = IntegerField('Previous quantity', widget=HiddenInput(),
                                    validators=[InputRequired(), NumberRange(min=0, max=MAX_QUANTITY)])


def _is_api():
    return request.path.startswith('/api/')


def authenticated(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            if _is_api():
                return jsonify(error='Log in to access your seller account.'), 401
            return current_app.login_manager.unauthorized()
        return function(*args, **kwargs)
    return wrapped


def _arguments():
    raw_page = request.args.get('page', '1')
    if not re.fullmatch(r'[0-9]{1,6}', raw_page) or int(raw_page) < 1:
        raise SellerError('Page must be a positive whole number.')
    query = request.args.get('q', '').strip()
    if len(query) > 100:
        raise SellerError('Search must contain at most 100 characters.')
    return query, int(raw_page)


def _form(form_class):
    if request.is_json:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            raise SellerError('Send a JSON object.', 400)
        values = {key: '' if value is None else str(value) for key, value in payload.items()}
        values.setdefault('csrf_token', request.headers.get('X-CSRFToken', ''))
        form = form_class(formdata=MultiDict(values))
    else:
        form = form_class()
    if not form.validate_on_submit():
        if 'csrf_token' in form.errors:
            raise SellerError('The form expired or is missing its security token. Reload and try again.', 400)
        if _is_api():
            return None, (jsonify(error='Check the submitted fields.', errors=form.errors), 422)
        messages = '; '.join(f'{form[name].label.text}: {", ".join(errors)}'
                             for name, errors in form.errors.items())
        raise SellerError(messages, 422)
    return form, None


def _json_value(value):
    if isinstance(value, Decimal):
        return format(value, '.2f')
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


@bp.app_template_filter('seller_time')
def seller_time(value):
    if value is None:
        return 'Pending'
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime('%b %d, %Y · %H:%M UTC')


@bp.context_processor
def seller_context():
    return {'seller_csrf': FlaskForm()}


@bp.errorhandler(SellerError)
def seller_error(error):
    if _is_api():
        return jsonify(error=error.message), error.status
    return render_template('sellers/error.html', message=error.message), error.status


@bp.route('/seller')
@authenticated
def overview():
    data = Seller.dashboard(current_user.id)
    peak = max((day['revenue'] for day in data['days']), default=Decimal('0.00'))
    return render_template('sellers/overview.html', data=data, peak=peak, active='overview')


@bp.route('/api/seller/overview')
@authenticated
def overview_json():
    return jsonify(_json_value(Seller.dashboard(current_user.id)))


@bp.route('/seller/inventory')
@bp.route('/api/seller/inventory', methods=['GET'], endpoint='inventory_json')
@authenticated
def inventory():
    query, page = _arguments()
    sort = request.args.get('sort', 'name')
    data = Seller.inventory(current_user.id, query=query, sort=sort, page=page)
    if _is_api():
        return jsonify(_json_value(data))
    return render_template('sellers/inventory.html', data=data, query=query, sort=sort,
                           quantity_form=QuantityForm(), remove_form=RemoveForm(), active='inventory')


@bp.route('/seller/inventory/add', methods=['GET', 'POST'])
@bp.route('/api/seller/inventory', methods=['POST'], endpoint='add_listing_json')
@authenticated
def add_listing():
    if request.method == 'POST':
        form, failure = _form(ListingForm)
        if failure:
            return failure
        result = Seller.add_listing(current_user.id, form.product_id.data, form.quantity.data)
        if _is_api():
            return jsonify(listing=result), 201
        flash('Listing added to your inventory.', 'success')
        return redirect(url_for('sellers.inventory'), code=303)
    query, page = _arguments()
    return render_template('sellers/add_listing.html',
                           data=Seller.catalog(current_user.id, query=query, page=page),
                           query=query, form=ListingForm(), active='inventory')


@bp.route('/seller/inventory/<int:product_id>/quantity', methods=['POST'])
@bp.route('/api/seller/inventory/<int:product_id>/quantity', methods=['POST'], endpoint='update_listing_json')
@authenticated
def update_listing(product_id):
    form, failure = _form(QuantityForm)
    if failure:
        return failure
    result = Seller.update_listing(current_user.id, product_id,
                                   form.quantity.data, form.expected_quantity.data)
    if _is_api():
        return jsonify(listing=result)
    flash('Inventory quantity updated.', 'success')
    return redirect(url_for('sellers.inventory'), code=303)


@bp.route('/seller/inventory/<int:product_id>/remove', methods=['POST'])
@bp.route('/api/seller/inventory/<int:product_id>/remove', methods=['POST'], endpoint='remove_listing_json')
@authenticated
def remove_listing(product_id):
    form, failure = _form(RemoveForm)
    if failure:
        return failure
    result = Seller.remove_listing(current_user.id, product_id, form.expected_quantity.data)
    if _is_api():
        return jsonify(removed=result)
    flash('Listing removed. Your previous orders are preserved.', 'success')
    return redirect(url_for('sellers.inventory'), code=303)


@bp.route('/seller/orders')
@bp.route('/api/seller/orders', endpoint='orders_json')
@authenticated
def orders():
    query, page = _arguments()
    status = request.args.get('status', 'all')
    data = Seller.orders(current_user.id, query=query, status=status, page=page)
    if _is_api():
        return jsonify(_json_value(data))
    return render_template('sellers/orders.html', data=data, query=query, status=status, active='orders')


@bp.route('/seller/orders/<int:order_id>')
@bp.route('/api/seller/orders/<int:order_id>', endpoint='order_detail_json')
@authenticated
def order_detail(order_id):
    data = Seller.order(current_user.id, order_id)
    if _is_api():
        return jsonify(_json_value(data))
    return render_template('sellers/order_detail.html', order=data, active='orders')


@bp.route('/seller/order-items/<int:item_id>/fulfill', methods=['POST'])
@bp.route('/api/seller/order-items/<int:item_id>/fulfill', methods=['POST'], endpoint='fulfill_json')
@authenticated
def fulfill(item_id):
    _, failure = _form(FlaskForm)
    if failure:
        return failure
    result = Seller.fulfill(current_user.id, item_id)
    if _is_api():
        return jsonify(item=_json_value(result))
    flash('This item was already fulfilled.' if result['already_fulfilled']
          else 'Item marked as fulfilled.', 'info' if result['already_fulfilled'] else 'success')
    return redirect(url_for('sellers.order_detail', order_id=result['order_id']), code=303)


@bp.route('/api/sellers/products/<int:product_id>')
def product_sellers(product_id):
    # Public product-detail integration exposes listings, never balances or private orders.
    return jsonify(_json_value(Seller.product_sellers(product_id)))
