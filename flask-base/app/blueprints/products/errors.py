from flask import render_template

from app.blueprints.products.views import products


@products.errorhandler(Exception)
def forbidden(error):
    print(error)
    return render_template('errors/403.html')


@products.errorhandler(Exception)
def page_not_found(error):
    print(error)
    return render_template('errors/404.html')


@products.errorhandler(Exception)
def internal_server_error(error):
    print(error)
    return render_template('errors/500.html')
