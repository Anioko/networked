from flask import Blueprint, render_template, abort, flash, redirect, url_for, request, jsonify
from flask_login import current_user, login_required

from app.models import *
directory = Blueprint('directory', __name__)



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
