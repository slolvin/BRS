from functools import wraps
from flask import request, jsonify, g
from .errors import forbidden
from ..models import User

def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not g.current_user.can(permission):
                return forbidden('Insufficient permissions')
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def mobile_token_required(f):
    """
    Декоратор проверяет наличие валидного JWT токена в заголовках запроса.
    Записывает активного пользователя в глобальный контекст g.current_mobile_user.
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # Проверяем наличие заголовка Authorization
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            # Строка должна быть в формате: Bearer <token_string>
            if auth_header.startswith('Bearer '):
                token = auth_header.split(" ")[1]

        if not token:
            return jsonify({'error': 'Unauthorized', 'message': 'Токен авторизации отсутствует'}), 401

        # Проверяем токен через наш статический метод модели User
        user = User.verify_auth_token(token)
        if not user:
            return jsonify({'error': 'Unauthorized', 'message': 'Токен недействителен или истек'}), 401

        # Сохраняем пользователя в контекст запроса g, чтобы ручка могла его прочитать
        g.current_mobile_user = user
        return f(*args, **kwargs)

    return decorated