from flask import Blueprint, render_template, abort, flash, redirect, url_for, request, jsonify
from flask_login import current_user, login_required

from app.models import *
from .forms import *
services = Blueprint('services', __name__)


@services.route('/list/services/')
def services_list():
    appts = Service.query.all()
    return render_template('services/allservices.html', appts=appts)


@services.route('/<int:service_id>/<service_category>/<service_title>/<service_city>/<service_state>/<service_country>')
def service_details(service_id,service_category, service_title, service_city, service_state, service_country):
    appts = Service.query.filter(Service.id == service_id).first_or_404()
    org_users = User.query.all()
    orgs = Organisation.query.filter(Organisation.user_id == User.id).all()
    return render_template('services/service_details.html', appt=appts, orgs=orgs, org_users=org_users)

@services.route('/<org_id>/create/service', methods=['Get', 'POST'])
@login_required
def create_service(org_id):
    org = Organisation.query.filter_by(user_id=current_user.id).filter_by(id=org_id).first_or_404()
    form = ServiceForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            appt = Service(service_category=form.service_category.data,
                       service_title=form.service_title.data,
                       creator_id=current_user.id,
                       organisation_id=org_id,
                       service_city=form.service_city.data,
                       service_state=form.service_state.data,
                       service_country=form.service_country.data,
                       mobile_phone=form.mobile_phone.data,
                       street_address=form.street_address.data,
                       description=form.description.data,
                       )
            db.session.add(appt)
            db.session.commit()
            flash('Service added!', 'success')
            return redirect(url_for('services.service_details', service_id=appt.id, service_category=appt.service_category, service_title=appt.service_title,
                                    service_city=appt.service_city, service_state=appt.service_state,
                                    service_country=appt.service_country))
        else:

            flash('ERROR! Service was not added.', 'error')
    return render_template('services/create_service.html', form=form, org=org)


