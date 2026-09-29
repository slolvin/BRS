from functools import wraps
from flask import g, jsonify, request
from ..models import User
from .errors import forbidden


def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not g.current_user.can(permission):
                return forbidden("Insufficient permissions")
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def mobile_token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if "Authorization" in request.headers:
            auth_header = request.headers["Authorization"]
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        if not token:
            return (
                jsonify(
                    {
                        "error": "Unauthorized",
                        "message": "Токен авторизации отсутствует",
                    }
                ),
                401,
            )

        user = User.verify_auth_token(token)
        if not user:
            return (
                jsonify(
                    {
                        "error": "Unauthorized",
                        "message": "Токен недействителен или истек",
                    }
                ),
                401,
            )
        g.current_mobile_user = user
        return f(*args, **kwargs)

    return decorated
