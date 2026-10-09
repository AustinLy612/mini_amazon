from datetime import datetime, timezone

from flask import Blueprint, abort, jsonify, redirect, render_template, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from humanize import naturaltime
from wtforms import SubmitField

from .models.wishlist import WishlistItem

bp = Blueprint('wishlist', __name__)


class WishlistForm(FlaskForm):
    submit = SubmitField('Add to Wishlist')


def humanize_time(value):
    # The tutorial schema stores UTC without a timezone, not local wall time.
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return naturaltime(datetime.now(timezone.utc) - value)


@bp.route('/wishlist')
@login_required
def wishlist():
    return render_template('wishlist.html',
                           items=WishlistItem.get_all_by_uid(current_user.id),
                           humanize_time=humanize_time)


@bp.route('/api/wishlist')
@login_required
def wishlist_json():
    return jsonify([dict(id=item.id, uid=item.uid, pid=item.pid,
                         time_added=str(item.time_added))
                    for item in WishlistItem.get_all_by_uid(current_user.id)])


@bp.route('/wishlist/add/<int:product_id>', methods=['POST'])
@login_required
def wishlist_add(product_id):
    form = WishlistForm()
    if not form.validate_on_submit():
        abort(400, description='Invalid form or expired CSRF token. Reload and try again.')
    if WishlistItem.add(current_user.id, product_id) is None:
        abort(404, description='Product not found.')
    return redirect(url_for('wishlist.wishlist'))
