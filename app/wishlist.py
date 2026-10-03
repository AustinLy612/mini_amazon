from flask import Blueprint, jsonify
from flask_login import current_user, login_required

from .models.wishlist import WishlistItem

bp = Blueprint('wishlist', __name__)


@bp.route('/wishlist')
@login_required
def wishlist():
    items = WishlistItem.get_all_by_uid(current_user.id)

    return jsonify([
        {
            'id': item.id,
            'uid': item.uid,
            'pid': item.pid,
            'time_added': item.time_added.isoformat()
        }
        for item in items
    ])
