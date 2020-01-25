from flask import Blueprint, render_template, abort, flash, redirect, url_for, request, jsonify
from flask_login import current_user, login_required

from app.models import *
directory = Blueprint('directory', __name__)

"""
This is where I intend to render all directory related data from the database into the views
"""


@directory.errorhandler(Exception)
def page_not_found(error):
    print(error)
    return render_template('errors/404.html')

@directory.route('/companies/', methods=['GET'])
def list_companies():
    appt = Organisation.query.all()
    return render_template('directory/list_company.html', appt=appt)

@directory.route('/services/')
def list_services():
    appts = Service.query.all()
    return render_template('directory/list_service.html', appt=appt)

@directory.route('/promos/', methods=['GET'])
def list_promos():
    appt = Promo.query.query.all()
    return render_template('directory/list_promo.html', appt=appt)
