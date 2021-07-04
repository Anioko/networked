from functools import wraps

from flask import abort, redirect
from flask_login import current_user

from app.models import Permission, url_for

def permission_required(permission):
    """Restrict a view to users with the given permission."""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.can(permission):
                abort(403)
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def logged_in():
    """Restrict a view to users with the given permission."""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_user.is_authenticated:
                return redirect(url_for('main.index'))
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def admin_required(f):
    return permission_required(Permission.ADMINISTER)(f)


def anonymous_required(f):
    return logged_in()(f)
