from flask import render_template

from app.blueprints.sitemaps.views import sitemaps


@sitemaps.app_errorhandler(403)
def forbidden(_):
    return render_template('errors/403.html'), 403

@sitemaps.errorhandler(Exception)
def page_not_found(error):
    return render_template('errors/404.html')

@sitemaps.errorhandler(Exception)
def handle_bad_request(error):
    return render_template('errors/500.html'), 400

@sitemaps.app_errorhandler(Exception)
def internal_server_error(error):
    return render_template('errors/500.html'), 500
