from flask import jsonify, request, g, current_app
from .. import db
from ..models import Drink, DrunkAction
from . import api
from .decorators import mobile_token_required


@api.route('/drinks/', methods=['GET'])
@mobile_token_required  # Теперь список напитков защищен токеном
def get_drinks():
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('DRINKS_PER_PAGE', 10)

    pagination = Drink.query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    drinks = pagination.items
    base_url = request.host_url.rstrip('/')

    json_drinks = []
    for drink in drinks:
        drink_data = drink.to_json()
        drink_data['image_url'] = f"{base_url}/static/drinks/{drink_data.get('image')}" if drink_data.get(
            'image') else None
        json_drinks.append(drink_data)

    return jsonify({
        'drinks': json_drinks,
        'current_page': page,
        'per_page': per_page,
        'total_pages': pagination.pages,
        'has_prev': pagination.has_prev,
        'has_next': pagination.has_next,
        'count': pagination.total
    }), 200


@api.route('/drinks/<int:id>', methods=['GET'])
@mobile_token_required  # Карточка напитка под JWT
def get_drink(id):
    drink = Drink.query.get_or_404(id)
    base_url = request.host_url.rstrip('/')
    drink_data = drink.to_json()

    image_name = drink.image_path or drink_data.get('image') or drink_data.get('image_path')
    drink_data['image_url'] = f"{base_url}/static/drinks/{image_name}" if image_name else None

    # Очищаем лишние поля
    drink_data.pop('image_path', None)
    drink_data.pop('image', None)

    # Добавляем для iOS флаг проверки: заказывал ли пользователь этот напиток ранее
    # и оценивал ли уже (чтобы iOS сразу блокировала кнопки звезд, если нельзя оценивать)
    has_drunk = DrunkAction.query.filter_by(user_id=g.current_mobile_user.id, drink_id=id).first() is not None

    # Предполагаем, что мы добавили отметку об оценке в DrunkAction (например, поле rated=True)
    # Если поля rated нет, мы можем временно проверять просто факт наличия заказа
    drink_data['can_rate'] = has_drunk

    return jsonify(drink_data), 200


@api.route('/drinks/<int:id>/rate', methods=['POST'])
@mobile_token_required  # Оценивать могут только верифицированные пользователи по JWT
def rate_drink(id):
    drink = Drink.query.get_or_404(id)
    user = g.current_mobile_user

    # 1. ЗАЩИТА ОТ НАКРУТКИ: Проверяем, пил ли пользователь этот напиток вообще
    # Ищем последнюю запись употребления, которую юзер еще НЕ оценивал
    action = DrunkAction.query.filter_by(user_id=user.id, drink_id=id).order_by(DrunkAction.timestamp.desc()).first()

    if not action:
        return jsonify({
            'error': 'Forbidden',
            'message': 'Вы не можете оценить напиток, пока не отметите факт его употребления (нажав "Выпить").'
        }), 403

    # Если в модели DrunkAction есть флаг rated (был ли этот бокал уже оценен)
    if hasattr(action, 'is_rated') and action.is_rated:
        return jsonify({
            'error': 'Conflict',
            'message': 'Вы уже оценили этот бокал. Чтобы оценить снова, добавьте новую запись употребления.'
        }), 409

    # 2. Получаем оценку из Swift
    json_data = request.get_json()
    if not json_data or 'rating' not in json_data:
        return jsonify({'error': 'Bad Request', 'message': 'Отсутствует поле rating'}), 400

    try:
        new_rating = int(json_data['rating'])
        if new_rating < 1 or new_rating > 5:
            return jsonify({'error': 'Validation Error', 'message': 'Оценка должна быть от 1 до 5'}), 422
    except ValueError:
        return jsonify({'error': 'Validation Error', 'message': 'Оценка должна быть целым числом'}), 422

    try:
        # 3. Алгоритм экспоненциального сглаживания (из твоей логики бэкенда)
        if not drink.score or float(drink.score) == 0.0:
            drink.score = float(new_rating)
        else:
            current_score = float(drink.score)
            weight = 0.2
            updated_score = (current_score * (1 - weight)) + (new_rating * weight)
            drink.score = round(updated_score, 2)

        # 4. Помечаем эту конкретную запись употребления как "оцененную"
        if hasattr(action, 'is_rated'):
            action.is_rated = True

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Internal Server Error', 'message': str(e)}), 500

    # 5. Возвращаем новый score в iOS для мгновенного обновления звездочек
    return jsonify({
        'status': 'success',
        'message': 'Оценка учтена',
        'new_score': float(drink.score)
    }), 200