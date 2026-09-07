from flask import jsonify, request, g
from flask_login import login_required, current_user
from .. import db
from . import api
from collections import Counter
from datetime import datetime, timedelta
from ..models import Drink, User, DrunkAction, ActionLog
#from .decorators import login_required
from .decorators import mobile_token_required
from sqlalchemy import func

@api.route('/user/profile')
@mobile_token_required
def get_user_profile():
    # В продакшене: user = g.current_user
    user = g.current_mobile_user

    result = db.session.query(
        func.count(DrunkAction.id).label('glasses_count'),
        func.sum(Drink.volume).label('total_ml'),
        func.avg(Drink.abv).label('average_abv')
    ).join(Drink, DrunkAction.drink_id == Drink.id) \
        .filter(DrunkAction.user_id == user.id) \
        .first()

    count_glasses = result.glasses_count or 0
    total_ml = result.total_ml or 0
    # Принудительно приводим к float, чтобы в JSON улетело дробное число (Double для Swift)
    avg_abv = float(result.average_abv) if result.average_abv else 0.0
    total_liters = float(total_ml / 1000.0)

    # === РАСЧЕТ ЛЮБИМОГО НАПИТКА ===
    fav_drink_query = db.session.query(
        Drink,
        func.count(DrunkAction.id).label('drink_count')
    ).join(DrunkAction, DrunkAction.drink_id == Drink.id) \
        .filter(DrunkAction.user_id == user.id) \
        .group_by(Drink.id) \
        .order_by(func.count(DrunkAction.id).desc()) \
        .first()

    # Берем имя любимого напитка
    fav_drink_name = fav_drink_query[0].name if fav_drink_query and fav_drink_query[0] else "Не определен"

    # Расчет звания месяца
    if total_liters == 0:
        monthly_badge = "Трезвенник"
    elif total_liters >= 5.0 and avg_abv <= 6.0:
        monthly_badge = "ПИВО"
    elif avg_abv >= 30.0 and total_liters >= 1.0:
        monthly_badge = "Пират"
    else:
        monthly_badge = "Эстет"

    # Форматируем дату регистрации
    reg_date = user.member_since.strftime('%Y-%m-%d') if hasattr(user,
                                                                 'member_since') and user.member_since else '2026-05-28'

    # Собираем логи действий (ActionLog)
    user_logs = user.actions.order_by(ActionLog.timestamp.desc()).limit(10).all()
    logs_data = []
    for log in user_logs:
        logs_data.append({
            'action_type': log.action_type,
            'description': log.description,
            'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M') if log.timestamp else ''
        })

    # Собираем историю выпитого (DrunkAction)
    drunk_actions = user.drunk_history.order_by(DrunkAction.timestamp.desc()).limit(15).all()
    drunk_data = []
    for action in drunk_actions:
        if action.drink:
            drunk_data.append({
                'id': action.id,
                'drink_name': action.drink.name,
                'type': action.drink.type,
                'volume': action.drink.volume or 0,
                'abv': float(action.drink.abv) if action.drink.abv else 0.0,
                'timestamp': action.timestamp.strftime('%d.%m %H:%M') if action.timestamp else ''
            })

    # =========================================================================
    # ВАЖНО: СТРОГО СОБЛЮДАЕМ СТРУКТУРУ КЛЮЧЕЙ PROFILESTATS ДЛЯ SWIFT
    # =========================================================================
    stats_payload = {
        'total_glasses': int(count_glasses),
        'total_liters': float(round(total_liters, 2)),
        'avg_abv': float(round(avg_abv, 1)),
        'favorite_drink': str(fav_drink_name),
        'registered_at': str(reg_date)
    }

    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': getattr(user, 'email', 'user@brs.com'),
        'role': user.role if user.role else 'user',
        'monthly_badge': monthly_badge,
        'stats': stats_payload,  # Отдаем идеально чистую структуру без лишних вложений
        'recent_logs': logs_data,
        'drunk_history': drunk_data
    })


@api.route('/user/favorite-bars', methods=['GET'])
def get_user_favorite_bars():
    if current_user.is_authenticated:
        user = current_user
    else:
        user = User.query.get(3) or User.query.first()

    if not user:
        return jsonify({'bars': []}), 200

    fav_bars = user.favorite_bars.all()

    bars_json = []
    for bar in fav_bars:
        bars_json.append({
            'id': bar.id,
            'name': bar.name,
            'address': bar.address or "Адрес не указан",
            'city': bar.city or "Самара",
            'rate': float(bar.rate) if bar.rate else 0.0
        })

    return jsonify({'bars': bars_json}), 200


@api.route('/user/update-location', methods=['POST'])
def update_user_location():
    if current_user.is_authenticated:
        user = current_user
    else:
        user = User.query.get(3) or User.query.first()

    if not user:
        return jsonify({'error': 'Not Found', 'message': 'Пользователь не найден'}), 404

    json_data = request.get_json()
    if not json_data or 'city' not in json_data:
        return jsonify({'error': 'Bad Request', 'message': 'Город не указан'}), 400

    user.location = json_data.get('city').strip()
    db.session.commit()

    return jsonify({
        'status': 'success',
        'message': f'Город успешно изменен на {user.location}',
        'current_city': user.location
    }), 200