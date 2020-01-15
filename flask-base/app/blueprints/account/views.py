from flask import Blueprint, flash, redirect, render_template, request
from flask_login import current_user, login_required, login_user, logout_user

from app.decorators import anonymous_required
from app.email import send_email
from app.blueprints.main.forms import *
from app.models import *
from app.models import Photo
from app.blueprints.posts.forms import PostForm
from .forms import *
from flask_rq import get_queue

# Twilio librarie import
from twilio.rest import Client
# Twilio variables
account_sid = 'AC0523295833f4fae2e3e23580f8258e81'
auth_token = 'd06a83b3e25eaefa0c66dad0c024d168'
messaging_service_sid = 'MG0338095a466022883a192f7bd30e35e3'
client = Client(account_sid, auth_token)

account = Blueprint('account', __name__)


@account.route('/invitees')
@login_required
def invited_users():
    """View all invited users."""
    users = db.session.query(User).filter(current_user.full_name==User.invited_by).all()
    return render_template(
        'account/invited_users.html', users=users)

@account.route('/myposts')
@login_required
def manage_posts():
    """View all your posts."""
    posts = Post.query.filter(current_user.id == Post.user_id).all()
    return render_template(
        'account/manage_posts.html', posts=posts)


@account.route('/posts/<int:id>/delete', methods=['GET', 'POST'])
@login_required
def delete_post(id):
    """Delete a user's post."""
    if current_user.id == Post.user_id:
        post = Post.query.filter(id=post.id).first()
        db.session.delete(post)
        db.session.commit()
        flash('Successfully deleted post %s.' % post.id, 'success')
    return redirect(url_for('account.manage_posts'))


@account.route('/login', methods=['GET', 'POST'])
@anonymous_required
def login():
    next = ''
    if 'next' in request.values:
        next = request.values['next']
    form = LoginForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            user_instance = User.query.filter_by(mobile_phone=form.mobile_phone.data).first()
            if user_instance is not None and user_instance.password_hash is not None and \
                    user_instance.verify_password(form.password.data):
                login_user(user_instance, form.remember_me.data)
                if request.form['next'] != '':
                    return redirect(request.form['next'])
                flash('You are now logged in. Welcome back!', 'success')
                return redirect(url_for('main.index'))
            else:
                flash('Invalid mobile_phone or password.', 'form-error')
    return render_template('account/login.html', form=form, next=next)


@account.route('/register', methods=['GET', 'POST'])
@anonymous_required
def register():
    """Register a new user, and send them a confirmation email."""
    form = RegistrationForm()
    if request.method == 'GET':
        return render_template('account/register.html', form=form)
    else:
        if form.validate_on_submit():
            user_instance = User(
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                email=form.email.data,
                gender=form.gender.data,
                profession=form.profession.data,
                area_code=form.area_code.data,
                mobile_phone=form.mobile_phone.data,
                #summary_text=form.summary_text.data,
                zip=form.zip.data,
                city=form.city.data,
                state=form.state.data,
                country=form.country.data,
                password=form.password.data)
            db.session.add(user_instance)
            db.session.commit()
            if request.files['photo']:
                image_filename = images.save(request.files['photo'])
                image_url = images.url(image_filename)
                picture_photo = Photo(
                    image_filename=image_filename,
                    image_url=image_url,
                    user_id=user_instance.id,
                )
                db.session.add(picture_photo)
            db.session.commit()
            token = user_instance.generate_confirmation_token()
            confirm_link = url_for('account.confirm', token=token, _external=True)
            area_code = str(form.area_code.data)
            area_code = area_code.replace(' ', '')
            phone_number = str(form.mobile_phone.data)
            phone_number = phone_number.replace(' ', '')
            if str(area_code)[0] != '+':
                area_code = '+' + str(area_code)
            client.messages.create(
                body=f'Your confirmation link is: {confirm_link}',
                messaging_service_sid=messaging_service_sid,
                to=str(area_code) + str(phone_number)
            )
            flash('A confirmation link has been sent to {}.'.format(str(area_code) + str(phone_number)), 'warning')
            if current_user.is_anonymous:
                return redirect(url_for('account.login'))
        else:
            flash('Error! Data was not added.', 'error')
        return render_template('account/register.html', form=form)


@account.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('public.index'))


@account.route('/manage/info', methods=['GET'])
@login_required
def manage():
    return render_template('account/manage.html', user=current_user, form=None)


@account.route('/manage/profile', methods=['GET'], defaults={'active': 'posts', 'page': 1})
@account.route('/manage/profile/<active>', methods=['GET'], defaults={'page': 1})
@account.route('/manage/profile/<active>/page/<page>', methods=['GET'])
def profile(active, page):
    if active == 'posts':
        items = current_user.posts.paginate(page, per_page=10)
    elif active == 'questions':
        items = current_user.questions.paginate(page, per_page=10)
    else:
        items = []
    edit_form = PostForm()
    return render_template('main/profile.html', user=current_user, current_user=current_user,
                           id=current_user.id, active=active, items=items, edit_form=edit_form)


@account.route('/reset-password', methods=['GET', 'POST'])
def reset_password_request():
    """Respond to existing user's request to reset their password."""
    if not current_user.is_anonymous:
        return redirect(url_for('main.index'))
    form = RequestResetPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(mobile_phone=form.mobile_phone.data).first()
        if user:
            token = user.generate_password_reset_token()
            reset_link = url_for('account.reset_password', token=token, _external=True)
            area_code = str(user.area_code)
            area_code = area_code.replace(' ', '')
            phone_number = str(user.mobile_phone)
            phone_number = phone_number.replace(' ', '')
            if str(area_code)[0] != '+':
                area_code = '+' + str(area_code)
            client.messages.create(
                body=f'Your confirmation link is: {reset_link}',
                messaging_service_sid=messaging_service_sid,
                to=str(area_code) + str(phone_number)
            )
        flash('A password reset link has been sent to {}.'.format(str(area_code) + str(phone_number)), 'warning')
        return redirect(url_for('account.login'))
    return render_template('account/reset_password.html', form=form)


@account.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset an existing user's password."""
    if not current_user.is_anonymous:
        return redirect(url_for('main.index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(mobile_phone=form.mobile_phone.data).first()
        if user is None:
            flash('Invalid phone number.', 'form-error')
            return redirect(url_for('main.index'))
        if user.reset_password(token, form.new_password.data):
            flash('Your password has been updated.', 'form-success')
            return redirect(url_for('account.login'))
        else:
            flash('The password reset link is invalid or has expired.',
                  'form-error')
            return redirect(url_for('main.index'))
    return render_template('account/reset_password.html', form=form)


@account.route('/manage/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change an existing user's password."""
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.old_password.data):
            current_user.password = form.new_password.data
            db.session.add(current_user)
            db.session.commit()
            flash('Your password has been updated.', 'form-success')
            return redirect(url_for('main.index'))
        else:
            flash('Original password is invalid.', 'form-error')
    return render_template('account/manage.html', form=form)


@account.route('/manage/info/extra', methods=['GET', 'POST'])
@login_required
def change_extra_details():
    photo = Photo.query.filter_by(user_id=current_user.id).limit(1).all()
    extra = Extra.query.filter_by(user_id=current_user.id).first()
    form = ExtraForm(obj=extra)

    if extra:
        form.photo.validators = form.photo.validators[1:]
        form.photo.validators.insert(0, Optional())
        form.photo.flags.required = False

    if request.method == 'GET':
        if extra:
            form.photo.default = extra.image_url
            for field_name, value in form.data.items():
                try:
                    form[field_name].default = extra.__getattribute__(field_name)
                except Exception as e:
                    print(field_name, e)
            form.process()
        return render_template('account/manage.html', user=current_user, current_user=current_user, photo=photo,
                               id=current_user.id, form=form, extra=extra)
    else:
        if form.validate_on_submit():
            if request.files['photo']:
                image_filename = docs.save(request.files['photo'])
                image_url = docs.url(image_filename)
            if not extra:
                extra = Extra(
                    image_filename=image_filename,
                    image_url=image_url,
                    required_skill_one=form.required_skill_one.data,
                    required_skill_two=form.required_skill_two.data,
                    required_skill_three=form.required_skill_three.data,
                    required_skill_four=form.required_skill_four.data,
                    required_skill_five=form.required_skill_five.data,
                    required_skill_six=form.required_skill_six.data,
                    required_skill_seven=form.required_skill_seven.data,
                    required_skill_eight=form.required_skill_eight.data,
                    required_skill_nine=form.required_skill_nine.data,
                    required_skill_ten=form.required_skill_ten.data,
                    user_id=current_user.id
                )
            else:
                if request.files['photo']:
                    extra.image_filename = image_filename,
                    extra.image_url = image_url,
                extra.required_skill_one = form.required_skill_one.data,
                extra.required_skill_two = form.required_skill_two.data,
                extra.required_skill_three = form.required_skill_three.data,
                extra.required_skill_four = form.required_skill_four.data,
                extra.required_skill_five = form.required_skill_five.data,
                extra.required_skill_six = form.required_skill_six.data,
                extra.required_skill_seven = form.required_skill_seven.data,
                extra.required_skill_eight = form.required_skill_eight.data,
                extra.required_skill_nine = form.required_skill_nine.data,
                extra.required_skill_ten = form.required_skill_ten.data,
                extra.user_id = current_user.id
            form.populate_obj(extra)
            db.session.add(extra)
            db.session.commit()
            flash("Extra Info saved.", 'success')
        else:
            flash('ERROR! Data was not saved.', 'error')
    return render_template('account/manage.html', form=form)

@account.route('/manage/update-profile', methods=['GET', 'POST'])
@login_required
def change_profile_details():
    """Respond to existing user's request to change their profile details."""
    user_instance = current_user
    form = EditProfileForm(obj=user_instance)
    if request.method == 'POST':
        if form.validate_on_submit():
            if form.validate_on_submit():
                form.populate_obj(user_instance)
                db.session.add(user_instance)
                if request.files['photo']:
                    image_filename = images.save(request.files['photo'])
                    image_url = images.url(image_filename)
                    picture_photo = Photo.query.filter_by(user_id=current_user.id).first()
                    if not picture_photo:
                        picture_photo = Photo(
                            image_filename=image_filename,
                            image_url=image_url,
                            user_id=current_user.id,
                        )
                    else:
                        picture_photo.image_filename = image_filename
                        picture_photo.image_url = image_url
                    db.session.add(picture_photo)
                db.session.commit()
                flash('You have successfully updated your profile',
                      'success')
                return redirect(url_for('account.manage'))
            else:
                flash('Unsuccessful.', 'warning')
    return render_template('account/edit_profile.html', form=form)


@account.route('/add/details', methods=['Get', 'POST'])
@login_required
def create_resume():
    check_resume_exist = Resume.query.filter(Resume.user == current_user).filter_by(id=Resume.user_id).count()
    if check_resume_exist > 0:
        return redirect(url_for('account.edit_resume', resume_id=current_user.id))

    form = ResumeForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            appt = Resume(company_name_one =form.company_name_one.data,
                       company_summary_one=form.company_summary_one.data,
                       role_one=form.role_one.data,
                       role_description_one=form.role_description_one.data,
                       start_date_one=form.start_date_one.data,
                       end_date_one=form.end_date_one.data,
                       currently_one=form.currently_one.data,
                       location_city_one=form.location_city_one.data,
                       location_state_one=form.location_state_one.data,
                       location_country_one=form.location_country_one.data,
                       company_name_two =form.company_name_two.data,
                       company_summary_two=form.company_summary_two.data,
                       role_two=form.role_two.data,
                       role_description_two=form.role_description_two.data,
                       start_date_two=form.start_date_two.data,
                       end_date_two=form.end_date_two.data,
                       currently_two=form.currently_two.data,
                       location_city_two=form.location_city_two.data,
                       location_state_two=form.location_state_two.data,
                       location_country_two=form.location_country_two.data,
                       company_name_three =form.company_name_three.data,
                       company_summary_three=form.company_summary_three.data,
                       role_three=form.role_three.data,
                       role_description_three=form.role_description_three.data,
                       start_date_three=form.start_date_three.data,
                       end_date_three=form.end_date_three.data,
                       currently_three=form.currently_three.data,
                       location_city_three=form.location_city_three.data,
                       location_state_three=form.location_state_three.data,
                       location_country_three=form.location_country_three.data,
                       company_name_four =form.company_name_four.data,
                       company_summary_four=form.company_summary_four.data,
                       role_four=form.role_four.data,
                       role_description_four=form.role_description_four.data,
                       start_date_four=form.start_date_four.data,
                       end_date_four=form.end_date_four.data,
                       currently_four=form.currently_four.data,
                       location_city_four=form.location_city_four.data,
                       location_state_four=form.location_state_four.data,
                       location_country_four=form.location_country_four.data,
                       company_name_five =form.company_name_five.data,
                       company_summary_five=form.company_summary_five.data,
                       role_five=form.role_five.data,
                       role_description_five=form.role_description_five.data,
                       start_date_five=form.start_date_five.data,
                       end_date_five=form.end_date_five.data,
                       currently_five=form.currently_five.data,
                       location_city_five=form.location_city_five.data,
                       location_state_five=form.location_state_five.data,
                       location_country_five=form.location_country_five.data,
                       company_name_six =form.company_name_six.data,
                       company_summary_six=form.company_summary_six.data,
                       role_six=form.role_six.data,
                       role_description_six=form.role_description_six.data,
                       start_date_six=form.start_date_six.data,
                       end_date_six=form.end_date_six.data,
                       currently_six=form.currently_six.data,
                       location_city_six=form.location_city_six.data,
                       location_state_six=form.location_state_six.data,
                       location_country_six=form.location_country_six.data,

                       school_name_one=form.school_name_one.data,
                       degree_description_one=form.degree_description_one.data,
                       grading_one=form.grading_one.data,
                       school_start_date_one=form.school_start_date_one.data,
                       school_end_date_one=form.school_end_date_one.data,
                       school_currently_one=form.school_currently_one.data,
                       city_school_one=form.city_school_one.data,
                       state_school_one=form.state_school_one.data,
                       country_school_one=form.country_school_one.data,
                       school_name_two=form.school_name_two.data,
                       degree_description_two=form.degree_description_two.data,
                       grading_two=form.grading_two.data,
                       school_start_date_two=form.school_start_date_two.data,
                       school_end_date_two=form.school_end_date_two.data,
                       school_currently_two=form.school_currently_two.data,
                       city_school_two=form.city_school_two.data,
                       state_school_two=form.state_school_two.data,
                       country_school_two=form.country_school_two.data,
                       school_name_three=form.school_name_three.data,
                       degree_description_three=form.degree_description_three.data,
                       grading_three=form.grading_three.data,
                       school_start_date_three=form.school_start_date_three.data,
                       school_end_date_three=form.school_end_date_three.data,
                       school_currently_three=form.school_currently_three.data,
                       city_school_three=form.city_school_three.data,
                       state_school_three=form.state_school_three.data,
                       country_school_three=form.country_school_three.data,
                       school_name_four=form.school_name_four.data,
                       degree_description_four=form.degree_description_four.data,
                       grading_four=form.grading_four.data,
                       school_start_date_four=form.school_start_date_four.data,
                       school_end_date_four=form.school_end_date_four.data,
                       school_currently_four=form.school_currently_four.data,
                       city_school_four=form.city_school_four.data,
                       state_school_four=form.state_school_four.data,
                       country_school_four=form.country_school_four.data,
                       school_name_five=form.school_name_five.data,
                       degree_description_five=form.degree_description_five.data,
                       grading_five=form.grading_five.data,
                       school_start_date_five=form.school_start_date_five.data,
                       school_end_date_five=form.school_end_date_five.data,
                       school_currently_five=form.school_currently_five.data,
                       city_school_five=form.city_school_five.data,
                       state_school_five=form.state_school_five.data,
                       country_school_five=form.country_school_five.data,
                       user_id=current_user.id
                       )
            db.session.add(appt)
            db.session.commit()
            flash('Details added!', 'success')
            return redirect(url_for('main.public_profile', user_id=current_user.id, full_name=current_user.full_name, _external=True))

        else:

            flash('ERROR! Details were not added.', 'error')
    return render_template('account/create_resume.html', form=form)

@account.route('/manage/edit/<int:resume_id>/details', methods=['GET', 'POST'])
@login_required
def edit_resume(resume_id):
    appt = Resume.query.filter(Resume.user == current_user).filter_by(id=resume_id).first_or_404()
    form = ResumeForm(obj=appt)
    if request.method == 'POST':
        if form.validate_on_submit():
            form.populate_obj(appt)
            db.session.add(appt)
            db.session.commit()
            flash('Details added!', 'success')
            return redirect(url_for('main.public_profile', user_id=current_user.id, full_name=current_user.full_name, _external=True))

        else:

            flash('ERROR! Details were not added.', 'error')
    return render_template('account/create_resume.html', form=form)

@account.route('/manage/change-email', methods=['GET', 'POST'])
@login_required
def change_email_request():
    """Respond to existing user's request to change their email."""
    form = ChangeEmailForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.password.data):
            new_email = form.email.data
            token = current_user.generate_email_change_token(new_email)
            change_email_link = url_for(
                'account.change_email', token=token, _external=True)
            get_queue().enqueue(
                send_email,
                recipient=new_email,
                subject='Confirm Your New Email',
                template='account/email/change_email',
                # current_user is a LocalProxy, we want the underlying user
                # object
                user=current_user._get_current_object(),
                change_email_link=change_email_link)
            flash('A confirmation link has been sent to {}.'.format(new_email),
                  'warning')
            return redirect(url_for('main.index'))
        else:
            flash('Invalid email or password.', 'form-error')
    return render_template('account/manage.html', form=form)


@account.route('/manage/change-email/<token>', methods=['GET', 'POST'])
@login_required
def change_email(token):
    """Change existing user's email with provided token."""
    if current_user.change_email(token):
        flash('Your email address has been updated.', 'success')
    else:
        flash('The confirmation link is invalid or has expired.', 'error')
    return redirect(url_for('main.index'))


@account.route('/confirm-account')
@login_required
def confirm_request():
    """Respond to new user's request to confirm their account."""
    token = current_user.generate_confirmation_token()
    confirm_link = url_for('account.confirm', token=token, _external=True)
    area_code = str(current_user.area_code)
    area_code = area_code.replace(' ', '')
    phone_number = str(current_user.mobile_phone)
    phone_number = phone_number.replace(' ', '')
    if str(area_code)[0] != '+':
        area_code = '+' + str(area_code)
    client.messages.create(
        body=f'Your confirmation link is: {confirm_link}',
        messaging_service_sid=messaging_service_sid,
        to=str(area_code) + str(phone_number)
    )
    flash('A new confirmation link has been sent to {}.'.format(str(area_code) + str(phone_number)), 'warning')
    return redirect(url_for('main.navigation'))


@account.route('/confirm-account/<token>')
@login_required
def confirm(token):
    """Confirm new user's account with provided token."""
    if current_user.confirmed:
        return redirect(url_for('main.index'))
    if current_user.confirm_account(token):
        flash('Your account has been confirmed.', 'success')
        return redirect(url_for('main.navigation'))
        
        #Check if user was invited and reward ambassador point to referrer
        if current_user.invited_by is not None:
            referrer = db.session.query(User).filter_by(full_name=current_user.invited_by.full_name).first()
            referrer.ambassador_points += 1
            referrer.ambassador_badge = get_level(referrer.ambassador_points) + " Ambassador"

            db.session.commit()

    else:
        flash('The confirmation link is invalid or has expired.', 'error')
    return redirect(url_for('main.navigation'))


@account.route(
    '/join-from-invite/<int:user_id>/<token>', methods=['GET', 'POST'])
def join_from_invite(user_id, token):
    """
    Confirm new user's account with provided token and prompt them to set
    a password.
    """
    if current_user is not None and current_user.is_authenticated:
        flash('You are already logged in.', 'error')
        return redirect(url_for('main.index'))

    new_user = User.query.get(user_id)
    if new_user is None:
        return redirect(404)

    if new_user.password_hash is not None:
        flash('You have already joined.', 'error')
        return redirect(url_for('main.navigation'))

    if new_user.confirm_account(token):
        form = CreatePasswordForm()
        if form.validate_on_submit():
            new_user.password = form.password.data
            db.session.add(new_user)
            db.session.commit()
            flash('Your password has been set. After you log in, you can '
                  'go to the "Your Account" page to review your account '
                  'information and settings.', 'success')
            return redirect(url_for('account.login'))
        return render_template('account/join_invite.html', form=form)
    else:
        flash('The confirmation link is invalid or has expired. Another '
              'invite email with a new link has been sent to you.', 'error')
        token = new_user.generate_confirmation_token()
        invite_link = url_for(
            'account.join_from_invite',
            user_id=user_id,
            token=token,
            _external=True)
        get_queue().enqueue(
            send_email,
            recipient=new_user.email,
            subject='You Are Invited To Join',
            template='account/email/invite',
            user=new_user,
            invite_link=invite_link)
    return redirect(url_for('main.navigation'))


@account.before_app_request
def before_request():
    """Force user to confirm email before accessing login-required routes."""
    if current_user.is_authenticated \
            and not current_user.confirmed \
            and request.endpoint[:8] != 'account.' \
            and request.endpoint != 'static':
        return redirect(url_for('account.unconfirmed'))


@account.route('/unconfirmed')
def unconfirmed():
    """Catch users with unconfirmed emails or phone numbers."""
    if current_user.is_anonymous or current_user.confirmed:
        return redirect(url_for('main.index'))
    return render_template('account/unconfirmed.html')
