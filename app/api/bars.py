from flask import jsonify, request, g, url_for, current_app
from .. import db
from ..models import Bar, Permission
from . import api
from .decorators import permission_required
from .errors import forbidden


@api.route('/bars/map')
def get_bars_for_map():
    all_bars = Bar.query.all()

    # Фильтруем бары: берем только те, у которых адрес собрался корректно
    valid_bars = [bar.to_json() for bar in all_bars if bar.get_full_address() is not None]

    return jsonify({
        'bars': valid_bars
    })


@api.route('/bars/')
def get_bars():
    page = request.args.get('page', 1, type=int)
    pagination = Bar.query.paginate(
        page=page, per_page=current_app.config['DRINKS_PER_PAGE']+2,
        error_out=False)
    bars = pagination.items
    prev = None
    if pagination.has_prev:
        prev = url_for('api.get_bars', page=page-1)
    next = None
    if pagination.has_next:
        next = url_for('api.get_bars', page=page+1)
    return jsonify({
        'bars': [bar.to_json() for bar in bars],
        'prev': prev,
        'next': next,
        'count': pagination.total
    })


@api.route('/bars/<int:id>')
def get_bar(id):
    post = Bar.query.get_or_404(id)
    return jsonify(post.to_json())


@api.route('/bars/', methods=['POST'])
def new_bar():
    bar = Bar.from_json(request.json)
    # Add admin from creator
    db.session.add(bar)
    db.session.commit()
    return jsonify(bar.to_json()), 201, \
        {'Location': url_for('api.get_bar', id=bar.id)}
