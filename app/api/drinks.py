from flask import jsonify, request, g, url_for, current_app
from .. import db
from ..models import Drink, Permission
from . import api
from .decorators import permission_required
from .errors import forbidden


@api.route('/drinks/')
def get_drinks():
    page = request.args.get('page', 1, type=int)
    # Используем стандартный лимит из конфига, убираем странный +2 для предсказуемости iOS-сеток
    per_page = current_app.config.get('DRINKS_PER_PAGE', 10)

    pagination = Drink.query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    drinks = pagination.items

    # Формируем базовый URL сервера для картинок (iOS нужен полный путь!)
    # request.host_url вернет что-то вроде http://192.168.1 (в зависимости от сети)
    base_url = request.host_url.rstrip('/')

    # Сериализуем данные, на лету добавляя абсолютный путь к фото для Xcode
    json_drinks = []
    for drink in drinks:
        drink_data = drink.to_json()
        if drink_data.get('image'):
            drink_data['image_url'] = f"{base_url}/static/drinks/{drink_data['image']}"
        else:
            drink_data['image_url'] = None
        json_drinks.append(drink_data)

    # Отдаем идеальный для Swift-структур (Decodable) ответ
    return jsonify({
        'drinks': json_drinks,
        'current_page': page,
        'per_page': per_page,
        'total_pages': pagination.pages,
        'has_prev': pagination.has_prev,
        'has_next': pagination.has_next,
        'count': pagination.total
    })


@api.route('/drinks/<int:id>')
def get_drink(id):
    drink = Drink.query.get_or_404(id)
    drink_data = drink.to_json()

    # Также собираем абсолютный URL для одиночного запроса
    base_url = request.host_url.rstrip('/')
    if drink_data.get('image'):
        drink_data['image_url'] = f"{base_url}/static/drinks/{drink_data['image']}"
    else:
        drink_data['image_url'] = None

    return jsonify(drink_data)
