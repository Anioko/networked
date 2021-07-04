import operator
from datetime import datetime

from flask import Blueprint, render_template, request, flash, abort, make_response, redirect
from flask_login import login_required, current_user
from flask_sqlalchemy import Pagination
import pdfkit
from sqlalchemy import func

from app.blueprints.main.forms import MessageForm, Job#, ProfileMessage
from app.models import Profile, ProfileSkill, ProfileEdu, ProfileJob, ProfileLang, url_for, User
from app.utils import basedir, db

employer = Blueprint('employer', __name__)


@employer.route('/')
def index():
    return render_template('employer/index.html')


@employer.route('/search')
def search():
    query = request.args.get('query')
    page = request.args.get('page')
    sort_by = request.args.get('sort_by')
    sort_dir = request.args.get('sort_dir')
    search_type = request.args.get('type')

    query = query if query is not None else ''
    page = page if page is not None else 1
    search_type = search_type if search_type is not None else ''
    sort_by = sort_by if sort_by is not None else ''
    sort_dir = sort_dir if sort_dir is not None else ''
    try:
        page = int(page)
    except:
        page = 1
    if len(query) > 0 and len(query) < 3:
        flash("Search Query must be at least 3 characters", "error")
        return render_template('employer/search_results.html', query=query, search_type=search_type, sort_by=sort_by,
                           sort_dir=sort_dir, results=type('obj', (object,), {'total' : 0}))
    if len(query) > 0:
        profiles_results = Profile.query.whooshee_search(query, order_by_relevance=0).all()
        skills_results = ProfileSkill.query.whooshee_search(query, order_by_relevance=0).all()
        edu_results = ProfileEdu.query.whooshee_search(query, order_by_relevance=0).all()
        jobs_results = ProfileJob.query.whooshee_search(query, order_by_relevance=0).all()
        langs_results = ProfileLang.query.whooshee_search(query, order_by_relevance=0).all()
        projects_results = ProfileLang.query.whooshee_search(query, order_by_relevance=0).all()
        all_results = profiles_results + skills_results + edu_results + jobs_results + langs_results + projects_results
        results = sorted(all_results, key=operator.attrgetter("score"))


    else:
        results = Profile.query.order_by(Profile.created_at.desc()).all()

    # profiles_count = Profile.query.whooshee_search(query, order_by_relevance=0).count()
    # skills_count = ProfileSkill.query.whooshee_search(query, order_by_relevance=0).count()
    # edu_count = ProfileEdu.query.whooshee_search(query, order_by_relevance=0).count()
    # jobs_count = ProfileJob.query.whooshee_search(query, order_by_relevance=0).count()
    # langs_count = ProfileLang.query.whooshee_search(query, order_by_relevance=0).count()
    # projects_count = ProfileLang.query.whooshee_search(query, order_by_relevance=0).count()

    # all_count = profiles_count + skills_count + edu_count + jobs_count + langs_count + projects_count

    results.reverse()
    results = [result if result.__class__.__name__ == 'Profile' else result.profile for result in results]
    search_type = 'Full Time' if search_type == 'full' else 'Part Time' if search_type == 'part' else ''
    if search_type != '':
        results = [result for result in results if result.commitment == search_type]
    all_count = len(results)
    results = results[(page - 1) * 40:page * 40]
    paginator = Pagination(items=results, page=page, per_page=40, query=None, total=all_count)
    results = paginator
    return render_template('employer/search_results.html', query=query, search_type=search_type, sort_by=sort_by,
                           sort_dir=sort_dir, results=results)


@employer.route('/profile/<int:profile_id>')
def profile(profile_id):
    profile_instance = Profile.query.filter_by(id=profile_id).first()
    if not profile_instance:
        abort(404)
    return render_template("employer/profile_view.html", profile=profile_instance)


@employer.route('/profile/pdf/<int:profile_id>')
@login_required
def profile_pdf(profile_id):
    profile_instance = Profile.query.filter_by(id=profile_id).first()
    if not profile_instance:
        abort(404)
    if not profile_instance.employer_can_download(current_user.id):
        abort(401)
    rendered = render_template("employer/profile_pdf.html", profile=profile_instance)
    # return rendered
    config = pdfkit.configuration(wkhtmltopdf=bytes('/usr/bin/wkhtmltopdf', 'utf-8'))
    css = basedir+'/static/css/profile_pdf.css'
    pdf = pdfkit.from_string(rendered, False, configuration=config, css=css)
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=cv.pdf'
    return response


@employer.route('/profile/<int:profile_id>/contact')
@login_required
def hire(profile_id):
    profile_instance = Profile.query.filter_by(id=profile_id).first()
    if not profile_instance:
        abort(404)
    user = User.query.filter(User.id != current_user.id).filter_by(id=profile_instance.user.id).first_or_404()
    for message in current_user.professional_message_history(user.id, profile_id):
        if message.recipient_id == current_user.id:
            message.read_at = db.func.now()
        db.session.add(message)
    db.session.commit()
    form = MessageForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            msg = ProfileMessage(user_id=current_user.id, recipient=user,
                          body=form.message.data, profile_id=profile_id)
            db.session.add(msg)
            db.session.commit()
            user.add_notification('unread_message', {'message': msg.id, 'count': user.new_messages()},
                                  related_id=current_user.id, permanent=True)
            flash('Your message has been sent.')
            return redirect(url_for('main.send_message', recipient=user.id, full_name=user.full_name))
    follow_lists = User.query.filter(User.id != current_user.id).order_by(func.random()).limit(10).all()
    jobs = Job.query.filter(Job.organisation != None).filter(Job.end_date >= datetime.now()).order_by(
        Job.pub_date.asc()).all()
    return render_template("employer/profile_contact.html", profile=profile_instance, title='Send Message',
                           form=form, recipient=user, current_user=current_user, follow_lists=follow_lists, jobs=jobs)
