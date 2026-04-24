from flask import jsonify, request, g, url_for, current_app
from .. import db
from ..models import Drink, Permission
from . import api
from .decorators import permission_required
from .errors import forbidden


@api.route('/drinks/')
def get_drinks():
    page = request.args.get('page', 1, type=int)
    pagination = Drink.query.paginate(
        page=page, per_page=current_app.config['DRINKS_PER_PAGE']+2,
        error_out=False)
    drinks = pagination.items
    prev = None
    if pagination.has_prev:
        prev = url_for('api.get_drinks', page=page-1)
    next = None
    if pagination.has_next:
        next = url_for('api.get_drinks', page=page+1)
    return jsonify({
        'drinks': [drink.to_json() for drink in drinks],
        'prev': prev,
        'next': next,
        'count': pagination.total
    })


@api.route('/drinks/<int:id>')
def get_drink(id):
    post = Drink.query.get_or_404(id)
    return jsonify(post.to_json())
