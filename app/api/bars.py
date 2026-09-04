from flask import jsonify, request, g, url_for, current_app
from .. import db
from sqlalchemy.exc import IntegrityError
from flask_login import current_user, login_required
from ..models import Bar
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


@api.route('/bars/', methods=['POST'])
# @login_required  # Гарантирует, что сессия активна и пользователь залогинен
##@permission_required(Permission.WRITE) # Проверяет права текущего пользователя
def create_bar():
    # 1. Получаем JSON из запроса
    json_data = request.get_json()
    if not json_data:
        return jsonify({'error': 'Bad Request', 'message': 'Отсутствуют JSON данные'}), 400

    # 2. Обязательные поля для валидации
    name = json_data.get('name')
    address = json_data.get('address')
    city = json_data.get('city')

    # Базовая проверка на заполненность критичных полей
    if not name or not address:
        return jsonify({'error': 'Validation Error', 'message': 'Поля name и address обязательны'}), 422

    # 3. Привязываем администратора бара из текущей сессии (current_user)
    # Если суперадмин может создавать бары для других менеджеров,
    # приоритет отдаем admin_id из JSON, иначе берем текущего юзера.
    admin_id = json_data.get('admin_id') or current_user.id

    # 4. Создаем экземпляр модели
    new_bar = Bar(
        name=name.strip(),
        address=address.strip(),
        city=city.strip() if city else "Самара",
        admin_id=admin_id,
        rate=json_data.get('rate', 0.0)
    )

    # 5. Сохраняем в базу данных с обработкой уникальности имени
    try:
        db.session.add(new_bar)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Conflict', 'message': f'Бар с именем "{name}" уже существует'}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Internal Server Error', 'message': str(e)}), 500

    # 6. Возвращаем успешный ответ (201 Created)
    return jsonify({
        'status': 'success',
        'message': 'Бар успешно создан',
        'bar': {
            'id': new_bar.id,
            'name': new_bar.name,
            'address': new_bar.get_full_address(),
            'manager': new_bar.get_user_name()
        }
    }), 201


@api.route('/bars/<int:id>', methods=['GET'])
# @login_required  # Требуем сессию авторизованного пользователя
def get_bar(id):
    # 1. Ищем бар по ID (автоматический 404, если не найден)
    bar = Bar.query.get_or_404(id)

    # 2. Формируем базовый URL для картинок напитков, как в твоей ручке /drinks/
    base_url = request.host_url.rstrip('/')

    # 3. Собираем список напитков, переиспользуя метод то_json() модели Drink
    drinks_list = []
    for drink in bar.drinks:
        drink_data = drink.to_json()

        # Добавляем абсолютный путь к фото для отображения в UIImageView / AsyncImage
        if drink_data.get('image'):
            drink_data['image_url'] = f"{base_url}/static/drinks/{drink_data['image']}"
        else:
            drink_data['image_url'] = None

        drinks_list.append(drink_data)

    # 4. Отдаем полный JSON для Swift-экрана
    return jsonify({
        'id': bar.id,
        'name': bar.name,
        'address': bar.get_full_address(),
        'city': bar.city,
        'rate': float(bar.rate) if bar.rate else 0.0,
        'manager_name': bar.get_user_name(),
        'admin_id': bar.admin_id,
        'drinks': drinks_list  # Список напитков теперь содержит полные данные с image_url
    }), 200


# @api.route('/bars/')
# def get_bars():
#     page = request.args.get('page', 1, type=int)
#     pagination = Bar.query.paginate(
#         page=page, per_page=current_app.config['DRINKS_PER_PAGE']+2,
#         error_out=False)
#     bars = pagination.items
#     prev = None
#     if pagination.has_prev:
#         prev = url_for('api.get_bars', page=page-1)
#     next = None
#     if pagination.has_next:
#         next = url_for('api.get_bars', page=page+1)
#     return jsonify({
#         'bars': [bar.to_json() for bar in bars],
#         'prev': prev,
#         'next': next,
#         'count': pagination.total
#     })


# @api.route('/bars/<int:id>')
# def get_bar(id):
#     post = Bar.query.get_or_404(id)
#     return jsonify(post.to_json())


# @api.route('/bars/', methods=['POST'])
# def new_bar():
#     bar = Bar.from_json(request.json)
#     # Add admin from creator
#     db.session.add(bar)
#     db.session.commit()
#     return jsonify(bar.to_json()), 201, \
#         {'Location': url_for('api.get_bar', id=bar.id)}
