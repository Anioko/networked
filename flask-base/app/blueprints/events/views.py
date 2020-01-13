from flask import Blueprint, render_template, abort, flash, redirect, url_for, request, jsonify
from flask_login import current_user, login_required

from app.models import *
from .forms import *
events = Blueprint('events', __name__)


@events.route('/list/events/')
def events_list():
    appts = Event.query.filter(Event.organisation != None).filter(Event.end_date >= datetime.now()).order_by(Event.pub_date.asc()).all()
    return render_template('events/allevents.html', appts=appts)


@events.route('/<int:event_id>/<event_title>/<event_city>/<event_state>/<event_country>')
def event_details(event_id, event_title, event_city, event_state, event_country):
    appts = Event.query.filter(Event.id == event_id).first_or_404()
    org_users = User.query.all()
    orgs = Organisation.query.filter(Organisation.user_id == User.id).all()
    return render_template('events/event_details.html', appt=appts, orgs=orgs, org_users=org_users)

@events.route('/<org_id>/create/event', methods=['Get', 'POST'])
@login_required
def create_event(org_id):
    org = Organisation.query.filter_by(user_id=current_user.id).filter_by(id=org_id).first_or_404()
    form = EventForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            image_filename = None
            if request.files['logo']:
                image_filename = images.save(request.files['logo'])
            appt = Event(event_title=form.event_title.data,
                       creator_id=current_user.id,
                       image_filename=image_filename,
                       organisation_id=org_id,
                       event_city=form.event_city.data,
                       event_state=form.event_state.data,
                       event_country=form.event_country.data,
                       description=form.description.data,
                       start_date=form.start_date.data.strftime('%d %B, %Y'),  # ''' ##('%Y-%m-%d') Alternative '''
                       end_date=form.end_date.data.strftime('%d %B, %Y')  # ''' ##('%Y-%m-%d') Alternative '''
                       )
            db.session.add(appt)
            db.session.commit()
            flash('Event added!', 'success')
            return redirect(url_for('events.event_details', event_id=appt.id, event_title=appt.event_title,
                                    event_city=appt.event_city, event_state=appt.event_state,
                                    event_country=appt.event_country))
        else:

            flash('ERROR! Event was not added.', 'error')
    return render_template('events/create_event.html', form=form, org=org)

@events.route('/<int:event_id>/<event_title>/attend')
@login_required
def event_attend(event_id, event_title):
    appt = db.session.query(Event).get(event_id)
    if appt is None:
        abort(404)
    elif current_user.id is None:
        abort(403)
    else:
        if appt.creator == current_user:
            flash("You can't click attend to {0} because you created it".format(appt.event_title), 'warning')
            return redirect(url_for('events.events_list'))
        extra = Extra.query.filter_by(user_id=current_user.id).first()
        attendees = Attendee.query.filter(Attendee.event_id == appt.id).all()
        applicants = [appt.user_id for appt in attendees]
        if current_user.id in attendees:
            flash("You are <strong>already attending</strong> for {0}.".format(appt.event_title), 'warning')
            return redirect(url_for('events.events_list'))
        else:
            appts = Attendee(event_id=appt.id, user_id=current_user.id)
            db.session.add(appts)
            db.session.commit()
            flash("You have successfully registered to {0}.".format(appt.event_title), 'success')
            return redirect(url_for('events.events_list'))

