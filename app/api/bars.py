from flask import jsonify, request, g, current_app
from .. import db
from sqlalchemy.exc import IntegrityError
from ..models import Bar
from . import api
from .decorators import mobile_token_required


@api.route('/bars/map', methods=['GET'])
def get_bars_for_map():
    # Получаем город из параметров запроса iOS (например: ?city=Любляна)
    target_city = request.args.get('city')

    if target_city:
        # Фильтруем бары строго по выбранному в настройках городу
        all_bars = Bar.query.filter_by(city=target_city).all()
    else:
        all_bars = Bar.query.all()

    valid_bars = [bar.to_json() for bar in all_bars if bar.get_full_address() is not None]

    return jsonify({
        'bars': valid_bars
    }), 200


@api.route('/bars/create', methods=['POST'])
@mobile_token_required  # Из паспорта: проверяет Bearer JWT и пишет юзера в g.current_mobile_user
def create_bar():
    # 1. Проверяем строковую ролевую модель из паспорта проекта
    current_user = g.current_mobile_user
    if current_user.role != 'administrator':
        return jsonify({
            'error': 'Forbidden',
            'message': 'Доступ запрещен. Создавать бары может только администратор.'
        }), 403

    # 2. Получаем JSON из запроса
    json_data = request.get_json()
    if not json_data:
        return jsonify({'error': 'Bad Request', 'message': 'Отсутствуют JSON данные'}), 400

    name = json_data.get('name')
    address = json_data.get('address')
    city = json_data.get('city')

    # Валидация полей
    if not name or not address:
        return jsonify({'error': 'Validation Error', 'message': 'Поля name и address обязательны'}), 422

    # 3. Привязываем администратора бара на основе верифицированного JWT контекста g
    admin_id = current_user.id

    # 4. Создаем экземпляр модели
    new_bar = Bar(
        name=name.strip(),
        address=address.strip(),
        city=city.strip() if city else "Самара",
        admin_id=admin_id,
        rate=json_data.get('rate', 0.0)
    )

    # 5. Сохраняем в СУБД
    try:
        db.session.add(new_bar)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Conflict', 'message': f'Бар с именем "{name}" уже существует'}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Internal Server Error', 'message': str(e)}), 500

    # 6. Возвращаем успешный ответ (201 Created) под спецификацию iOS
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
@mobile_token_required  # Защищаем эндпоинт карточки бара для мобилки
def get_bar(id):
    bar = Bar.query.get_or_404(id)
    base_url = request.host_url.rstrip('/')

    drinks_list = []
    for drink in bar.drinks:
        drink_data = drink.to_json()

        # Формируем абсолютный URL картинок для UIImageView / AsyncImage на iOS
        if drink_data.get('image'):
            drink_data['image_url'] = f"{base_url}/static/drinks/{drink_data['image']}"
        else:
            drink_data['image_url'] = None

        drinks_list.append(drink_data)

    return jsonify({
        'id': bar.id,
        'name': bar.name,
        'address': bar.get_full_address(),
        'city': bar.city,
        'rate': float(bar.rate) if bar.rate else 0.0,
        'manager_name': bar.get_user_name(),
        'admin_id': bar.admin_id,
        'drinks': drinks_list
    }), 200


@api.route('/bars/<int:bar_id>/drinks/add', methods=['POST'])
@mobile_token_required  # Проверяем Bearer JWT токен менеджера/админа
def add_drink_to_bar(bar_id):
    # 1. Ищем бар, в который добавляем напиток
    bar = Bar.query.get_or_404(bar_id)

    # 2. Проверяем права строковой ролевой модели БРС
    current_user = g.current_mobile_user
    if current_user.role not in ['manager', 'administrator']:
        return jsonify({'error': 'Forbidden', 'message': 'Недостаточно прав для добавления напитков'}), 403

    # 3. Валидируем JSON от iOS
    json_data = request.get_json()
    if not json_data:
        return jsonify({'error': 'Bad Request', 'message': 'Отсутствуют JSON данные'}), 400

    name = json_data.get('name')
    drink_type = json_data.get('type', 'Пиво')
    abv = float(json_data.get('abv', 0.0))

    if not name:
        return jsonify({'error': 'Validation Error', 'message': 'Название напитка обязательно'}), 422

    # 4. Создаем напиток с правильным именем колонки СУБД (image_path вместо image)
    from ..models import Drink
    new_drink = Drink(
        name=name.strip(),
        type=drink_type,
        abv=abv,
        score=0.0,  # Защита Swift от null-значений
        bar_id=bar.id,
        image_path=json_data.get('image_url') if json_data.get('image_url') else None  # 🌟 ИСПРАВЛЕНО ЗДЕСЬ
    )

    try:
        db.session.add(new_drink)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Internal Server Error', 'message': str(e)}), 500

    return jsonify({
        'status': 'success',
        'message': 'Напиток успешно добавлен в меню',
        'drink': new_drink.to_json()
    }), 201
