# from app import socket_io
from flask import Blueprint, render_template, flash, redirect, url_for, request, jsonify
from flask_login import current_user, login_required
# from flask_rq import get_queue
# from flask_socketio import emit
from sqlalchemy import desc, func

from app.email import send_email
from .forms import *

from app.models.user import get_level
from app.upload import list_files, download_file, upload_file, upload_fileobj
#from config import ACCESS_KEY,SECRET_KEY
import boto3
from werkzeug import secure_filename
from flask_weasyprint import HTML, render_pdf
from app import cache
#import pdfkit


# Twilio librarie import
from twilio.rest import Client
# Twilio variables
account_sid = 'AC0523295833f4fae2e3e23580f8258e81'
auth_token = 'd06a83b3e25eaefa0c66dad0c024d168'
messaging_service_sid = 'MG0338095a466022883a192f7bd30e35e3'
client = Client(account_sid, auth_token)

main = Blueprint('main', __name__)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

UPLOAD_FOLDER = "uploads"
BUCKET = "networkedng1"




def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@main.route('/navigation')
@login_required
def navigation():
    """
    Once user confirms their account, they land here first to choose what actions
    they actually want to perform. Then the links here sends them to those actions
    """
    return render_template('main/user_navigation.html')



@main.route('/dashboard')
@login_required
def index():
    check_org_exist = db.session.query(Organisation).filter_by(user_id=current_user.id).first()
    return render_template('main/user_dashboard.html', check_org_exist=check_org_exist)

"""
##Navigation intended for first time logged in users to direct them
@main.route('/navigation')
@login_required
def navigation():
    return render_template('main/user_navigation.html')
"""
##Abandoned feed design, could be revisited
@main.route('/feed')
def home():
    if not current_user.is_authenticated:
        return redirect(url_for('public.index'))
    ''' this is where users will see their feeds'''
    data = cache.lrange("q")
    if not data:
        data = []
    data1 = cache.lrange("p")
    if not data1:
        data1 = []

    return render_template('main/user_feed.html', data = [data, data1])


@main.route('/profile', methods=['GET', 'POST'])
def profile():
    return redirect(url_for('account.profile'))


@main.route('/list/', defaults={'page': 1})
@main.route('/list/page/<int:page>', methods=['GET'])
@login_required
def select_section(page):
    paginated = User.query.filter(User.id != current_user.id).order_by(User.id.desc()).paginate(page, per_page=10)
    return render_template('main/selection.html', paginated=paginated)


@main.route('/profile/<int:user_id>/', methods=['GET'], defaults={'active': 'posts', 'page': 1})
@main.route('/profile/<int:user_id>/<active>', methods=['GET'], defaults={'page': 1})
@main.route('/profile/<int:user_id>/<active>/page/<page>', methods=['GET'])
def user_detail(user_id, active, page):
    """Provide HTML page with all details on a given user """
    user = User.query.get_or_404(user_id)
    if active == 'posts':
        items = user.posts.paginate(page, per_page=10)
    elif active == 'questions':
        items = user.questions.paginate(page, per_page=10)
    else:
        items = []
    user_id = Photo.user_id
    photo = Photo.query.filter_by(id=user_id).limit(1).all()
    return render_template('public/profile.html', user=user, current_user=current_user, photo=photo, id=User.id, items=items)

@main.route('/public/<int:user_id>/<full_name>')
def public_profile(user_id, full_name):
    """Provide HTML page with all details on a given user """
    #user = User.query.get_or_404(user_id)
    user = db.session.query(User).filter(User.id == user_id, User.full_name == full_name).first()
    resume = db.session.query(Resume).filter(Resume.id == user.id).first()
    extra = db.session.query(Extra).filter(Extra.id == user.id).first()
    user_id = Photo.user_id
    photo = Photo.query.filter_by(id=user_id).limit(1).all()
    return render_template('public/public_profile.html', user=user, resume=resume, extra=extra, current_user=current_user, photo=photo, id=User.id)


@main.route('/public/<full_name>.pdf')
def resume_pdf(full_name):
    user = db.session.query(User).filter(User.full_name == full_name).first()
    resume = db.session.query(Resume).filter(Resume.id == user.id).first()
    extra = db.session.query(Extra).filter(Extra.id == user.id).first()
    user_id = Photo.user_id
    photo = Photo.query.filter_by(id=user_id).limit(1).all()
    # Make a PDF straight from HTML in a string.
    html = render_template('public/public_profile.html', full_name=User.full_name, user=user, resume=resume, extra=extra, photo=photo,)
    return render_pdf(HTML(string=html))


@main.route('/user/<int:id>/<full_name>', defaults={'active': 'posts', 'page': 1})
@main.route('/user/<int:id>/<full_name>/<active>', defaults={'page': 1})
@main.route('/user/<int:id>/<full_name>/<active>/page/<int:page>')
@login_required
def user(id, full_name, active, page):
    user = db.session.query(User).filter(User.id == id, User.full_name == full_name).first()
    edit_form = PostForm()
    if user == current_user:
        return redirect(url_for('main.profile', active=active))
    if active == 'posts':
        items = user.posts.paginate(page, per_page=10)
    elif active == 'questions':
        items = user.questions.paginate(page, per_page=10)
    else:
        items = []
    return render_template('main/profile.html', user=user, active=active, items=items,
                           edit_form=edit_form)  # , photo=photo)


@main.route('/<int:id>/<full_name>')
@login_required
def user_public_profile(id, full_name):
    user = db.session.query(User).filter(User.id == id, User.full_name == full_name).first()
    if user is None:
        flash('User {} not found.'.format(full_name))
        return redirect(url_for('main.index'))
    if user == current_user:
        flash('You cannot follow yourself!')
        return redirect(url_for('main.user', id=id, full_name=full_name))
    current_user.follow(user)
    db.session.commit()
    flash('You are following {}!'.format(full_name))
    return redirect(url_for('main.user', id=id, full_name=full_name))

@main.route('/<int:id>/follow/<full_name>')
@login_required
def follow(id, full_name):
    user = db.session.query(User).filter(User.id == id, User.full_name == full_name).first()
    if user is None:
        flash('User {} not found.'.format(full_name))
        return redirect(url_for('main.index'))
    if user == current_user:
        flash('You cannot follow yourself!')
        return redirect(url_for('main.user', id=id, full_name=full_name))
    current_user.follow(user)
    #Award Networker points
    current_user.networker_points = current_user.networker_points + 1
    current_user.networker_badge = get_level(current_user.networker_points) + " Networker"
    db.session.commit()
    flash('You are following {}!'.format(full_name))
    return redirect(url_for('main.user', id=id, full_name=full_name))


@main.route('/<int:id>/unfollow/<full_name>')
@login_required
def unfollow(id, full_name):
    user = db.session.query(User).filter(User.id == id, User.full_name == full_name).first()
    if user is None:
        flash('User {} not found.'.format(full_name))
        return redirect(url_for(main.index))
    if user == current_user:
        flash('You cannot follow yourself!')
        return redirect(url_for('main.user', id=id, full_name=full_name))
    current_user.unfollow(user)
    db.session.commit()
    flash('You are not following {}!'.format(full_name))
    return redirect(url_for('main.user', id=id, full_name=full_name))


@main.route("/<user_id>/followers", methods=['GET'], defaults={'page': 1})
@login_required
def followers(user_id, page):
    user_instance = User.query.get(user_id)
    followers_users = user_instance.followers.paginate(page, per_page=10)
    return render_template('main/selection.html', paginated=followers_users, user_id=user_id)


@main.route("/<user_id>/following", methods=['GET'], defaults={'page': 1})
@login_required
def following(user_id, page):
    user_instance = User.query.get(user_id)
    following_users = user_instance.followed.paginate(page, per_page=10)
    return render_template('main/selection.html', paginated=following_users)


@main.route('/photo/upload', methods=['GET', 'POST'])
@login_required
def photo_upload():
    ''' check if photo already exist, if it does, send to homepage. Avoid duplicate upload here'''
    check_photo_exist = db.session.query(Photo).filter(Photo.user_id == current_user.id).count()
    if check_photo_exist >= 1:
        pass
        # return redirect(url_for('main.index'))
    form = PhotoForm()
    if request.method == 'POST':
        if form.validate_on_submit():
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
            flash("Image saved.")
            return redirect(url_for('main.index'))
        else:
            flash('ERROR! Photo was not saved.', 'error')
    return render_template('main/upload.html', form=form)


@main.route('/invite-colleague', methods=['GET', 'POST'])
@login_required
def invite_user():
    """Invites a new user to create an account and set their own password."""

    form = InviteUserForm()
    if form.validate_on_submit():
        invited_by = db.session.query(User).filter_by(id=current_user.id).first()
        user = User(
            invited_by=invited_by.full_name,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            area_code=form.area_code.data,
            mobile_phone=form.mobile_phone.data
            )
        db.session.add(user)
        db.session.commit()
        token = user.generate_confirmation_token()
        invite_link = url_for(
            'account.join_from_invite',
            user_id=user.id,
            token=token,
            _external=True)
        area_code = str(form.area_code.data)
        area_code = area_code.replace(' ', '')
        phone_number = str(form.mobile_phone.data)
        phone_number = phone_number.replace(' ', '')
        if str(area_code)[0] != '+':
            area_code = '+' + str(area_code)
        client.messages.create(
            body=f'Invitation to networked.ng by %s. Click link to complete registration : {invite_link}' % invited_by,
            messaging_service_sid=messaging_service_sid,
            to=str(area_code) + str(phone_number)
        )
        flash('User {} successfully invited'.format(user.full_name),
              'form-success')
        return redirect(url_for('account.invited_users'))
    else:
        flash('Error! Invitation not sent.', 'error')
    return render_template('main/new_user.html', form=form)

        

##
##        get_queue().enqueue(
##            send_email,
##            recipient=user.email,
##            subject='You Are Invited To Join',
##            template='account/email/invite',
##            user=user,
##            invited_by=invited_by,
##            invite_link=invite_link,
##            invite_by=invited_by
##        )
##        #Add a point for inviting user
##        flash('User {} successfully invited'.format(user.full_name),
##              'form-success')
##        return redirect(url_for('main.index'))
##    return render_template('main/new_user.html', form=form)


@main.route('/conversation/<recipient>/<full_name>', methods=['GET', 'POST'])
@login_required
def send_message(recipient, full_name):
    user = User.query.filter(User.id != current_user.id).filter_by(id=recipient).first_or_404()
    for message in current_user.history(user.id):
        if message.recipient_id == current_user.id:
            message.read_at = db.func.now()
        db.session.add(message)
    db.session.commit()
    form = MessageForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            msg = Message(user_id=current_user.id, recipient=user,
                          body=form.message.data)
            db.session.add(msg)
            db.session.commit()
            user.add_notification('unread_message_count', user.new_messages())
            flash('Your message has been sent.')
            return redirect(url_for('main.send_message', recipient=user.id, full_name=user.full_name))
    follow_lists = User.query.filter(User.id != current_user.id).order_by(func.random()).limit(10).all()
    jobs = Job.query.filter(Job.organisation != None).filter(Job.end_date >= datetime.now()).order_by(
        Job.pub_date.asc()).all()
    return render_template('main/send_messages.html', title='Send Message',
                           form=form, recipient=user, current_user=current_user, follow_lists=follow_lists, jobs=jobs)


@main.route('/conversations', defaults={'page': 1}, methods=['GET'])
@main.route('/conversations/<page>',  methods=['GET'])
@login_required
def conversations(page):
    current_user.last_message_read_time = datetime.utcnow()
    db.session.commit()
    messages = current_user.messages_received.order_by(
        Message.timestamp.desc()).paginate(
        page, 10, False)
    conversations = Message.query.filter(
        or_(Message.user_id == current_user.id, Message.recipient_id == current_user.id)).all()
    user_ids = [conversation.user_id for conversation in conversations] + [conversation.recipient_id for conversation in
                                                                           conversations]
    user_ids = list(set(user_ids))
    if current_user.id in user_ids:
        user_ids.remove(current_user.id)
    users = User.query.filter(User.id.in_(user_ids)).paginate(page, per_page=20)
    follow_lists = User.query.filter(User.id != current_user.id).order_by(func.random()).limit(10).all()
    jobs = Job.query.filter(Job.organisation != None).filter(Job.end_date >= datetime.now()).order_by(
        Job.pub_date.asc()).all()
    return render_template('main/messages.html', messages=messages.items, users=users, follow_lists=follow_lists, jobs=jobs)


@main.route('/question/<question_id>/edit', methods=['POST'])
@login_required
def edit_question(question_id):
    question = Question.query.filter_by(user_id=current_user.id).filter_by(id=question_id).first_or_404()
    form = QuestionForm()
    if form.validate_on_submit():
        question.title = form.title.data
        question.description = form.description.data
        db.session.add(question)
        db.session.commit()
        flash("Edited.", 'success')

        return redirect(url_for('main.question'))
    else:
        flash('ERROR! Question was not edited.', 'error')


@main.route('/question/<question_id>/delete', methods=['POST'])
def delete_question(question_id):
    question = Question.query.filter_by(user_id=current_user.id).filter_by(id=question_id).first_or_404()
    db.session.delete(question)
    db.session.commit()
    flash("Delete.", 'success')
    return redirect(url_for('main.question'))


@main.route('/questions', methods=['GET', 'POST'])
@login_required
#@cache.memoize(timeout=5)
def question():
    form = QuestionForm()
    edit_form = QuestionForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            author = db.session.query(User).filter_by(id=current_user.id).first()
            posts = Question(
                title=form.title.data,
                description=form.description.data,
                user_id=current_user.id,
                author=author.full_name,
                level=1
            )
            list_of_posts = cache.get("p")
            if list_of_posts is None or not list_of_posts:
                list_of_posts = []
            list_of_posts.append(posts)
            cache.set("p", list_of_posts)
            author.kw_seeker_points = author.kw_seeker_points + 1
            author.kw_seeker_badge = get_level(author.kw_seeker_points) + " Kw Seeker"
            db.session.add(posts)
            db.session.commit()
            flash("Posted.", 'success')

            return redirect(url_for('main.question'))
        else:
            flash('ERROR! Question was not created.', 'error')
    follow_lists = User.query.filter(User.id != current_user.id).order_by(func.random()).limit(10).all()
    jobs = Job.query.filter(Job.organisation != None).filter(Job.end_date >= datetime.now()).order_by(Job.pub_date.asc()).all()
    users = User.query.filter(Question.user_id == User.id).first()
    questions = Question.query.filter(Question.user_id!=None).order_by(desc(Question.timestamp)).all()
    return render_template('main/create_question.html', form=form,
                           follow_lists=follow_lists, users=users, results=questions,jobs=jobs, edit_form=edit_form)


@main.route('/question/<title>/')
def question_details(title):
    """Provide HTML page with all details on a given question.
    """
    # Query: get Position object by ID.
    post = Question.query.filter(Question.title == title).first()
    edit_form = QuestionForm()
    return render_template('main/question_details.html', post=post, edit_form=edit_form)


@main.route('/question/answer/<answer_id>/edit', methods=['POST'])
@login_required
def edit_answer(answer_id):
    answer = Answer.query.filter_by(user_id=current_user.id).filter_by(id=answer_id).first_or_404()
    question = answer.question
    body = request.form['reply']
    answer.body = body
    db.session.add(answer)
    db.session.commit()
    return redirect(url_for('main.question_details', title=question.title))


@main.route('/question/answer/<answer_id>/delete', methods=['POST'])
def delete_answer(answer_id):
    answer = Answer.query.filter_by(user_id=current_user.id).filter_by(id=answer_id).first_or_404()
    question = answer.question
    db.session.delete(answer)
    db.session.commit()
    flash("Deleted Successfully.", 'success')
    return redirect(url_for('main.question_details', title=question.title))


@main.route('/question/answer', methods=['GET', 'POST'])
@login_required
def parent_answers():
    if request.method == 'POST':
        body = request.form['reply']
        question = Question.query.filter_by(id=request.form['question_id']).first()
        photo = current_user.photos.first()
        answers = Answer(user_id=current_user.id,
                         author=current_user.full_name,
                         question_id=question.id,
                         body=body,
                         )
        if request.form['parent_id'] != '0':
            answers.parent_id = request.form['parent_id']
        if photo:
            answers.image_url = photo.image_url
        current_user.kw_builder_points = current_user.kw_builder_points + 1
        current_user.kw_builder_badge = get_level(current_user.kw_builder_points) + " Kw Builder"
        db.session.add(answers)
        db.session.commit()
        question.user.add_notification('answer', len(question.answers.all()), question.id)
        # return json.dumps({'status': 'OK', 'data':body});
        return redirect(url_for('main.question_details', title=question.title))
    return render_template('main/create_question.html')


@main.route('/notification/read/<notification_id>')
@login_required
def read_notification(notification_id):
    notification = Notification.query.filter_by(id=notification_id).first_or_404()
    notification.read = True
    db.session.add(notification)
    db.session.commit()
    if 'unread_message_count' in notification.name:
        link = url_for('main.conversations')
    elif 'post_likes' in notification.name:
        link = url_for('post.post_create')
    elif 'post_replies' in notification.name:
        link = url_for('post.post_create')
    elif 'answer' in notification.name:
        link = url_for('main.question')
    return redirect(link)


@main.route('/notifications/count')
@login_required
def notifications_count():
    notifications = Notification.query.filter_by(read=False).filter_by(user_id=current_user.id).count()
    messages = current_user.new_messages()

    return jsonify({
        'status': 1,
        'notifications': notifications,
        'messages': messages
    })


@main.route('/notifications')
@login_required
def notifications():
    follow_lists = User.query.filter(User.id != current_user.id).order_by(func.random()).limit(10).all()
    jobs = Job.query.filter(Job.organisation != None).filter(Job.end_date >= datetime.now()).order_by(Job.pub_date.asc()).all()
    users = User.query.order_by(User.full_name).all()
    notifications = Notification.query.filter_by(read=False).filter_by(user_id=current_user.id).all()
    parsed_notifications = []
    for notification in notifications:
        border = "border: 1px solid rgb(98, 170, 175)" if not notification.read else ""
        if 'unread_message_count' in notification.name:
            parsed_notifications.append({
                "link": url_for('main.read_notification', notification_id=notification.id),
                "title": "New Messages",
                "text": "<p>You have <strong><u>{}</u></strong> new messages, please click here to go see them</p>".format(
                    notification.payload_json),
                "timestamp": notification.timestamp,
                "border": border
            })
        elif 'post_likes' in notification.name:
            post = Post.query.filter_by(id=notification.related_id).first()
            if post:
                parsed_notifications.append({
                    "link": url_for('main.read_notification', notification_id=notification.id),
                    "title": "New Post Likes",
                    "text": "<p>You have new likes on post <strong><u>{} ...</u></strong>, please click here to go see them</p>".format(
                        post.text[:20]),
                    "timestamp": notification.timestamp,
                    "border": border
                })
            else:
                notification.read = True
                db.session.add(notification)
                db.session.commit()
        elif 'post_replies' in notification.name:
            post = Post.query.filter_by(id=notification.related_id).first()
            if post:
                parsed_notifications.append({
                    "link": url_for('main.read_notification', notification_id=notification.id),
                    "title": "New Post Replies",
                    "text": "<p>You have new replies on post <strong><u>{} ...</u></strong>, please click here to go see them</p>".format(
                        post.text[:20]),
                    "timestamp": notification.timestamp,
                    "border": border
                })
            else:
                notification.read = True
                db.session.add(notification)
                db.session.commit()
        elif 'answer' in notification.name:
            post = Question.query.filter_by(id=notification.related_id).first()
            if post:
                parsed_notifications.append({
                    "link": url_for('main.read_notification', notification_id=notification.id),
                    "title": "New Question Answers",
                    "text": "<p>You have new answers on question <strong><u>{} ...</u></strong>, please click here to go see them</p>".format(
                        post.title[:20]),
                    "timestamp": notification.timestamp,
                    "border": border
                })
            else:
                notification.read = True
                db.session.add(notification)
                db.session.commit()
    parsed_notifications = sorted(parsed_notifications, key=lambda i: i['timestamp'])
    parsed_notifications.reverse()

    # photo = db.session.query(Photo).filter(Photo.user_id == current_user.id)
    return render_template('main/notifications.html', follow_lists=follow_lists, users=users, jobs=jobs,
                           notifications=parsed_notifications)

"""

### please re-visit. It has a permission error

bucket_name = "networkedng1"

s3 = boto3.client(
   "s3",
   aws_access_key_id=ACCESS_KEY,
   aws_secret_access_key=SECRET_KEY
)
bucket_resource = s3

@main.route("/try/upload", methods=['GET', 'POST'])
def upload():
    form = PhotoForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            img = request.files['photo']
            filename = ''
            if img:
                filename = secure_filename(img.filename)
                img.save(filename)
                bucket_resource.upload_file(
                    Bucket = bucket_name,
                    Filename=filename,
                    Key=filename
                )
                flash("Image saved.")
                return redirect(url_for('main.index'))
        else:
            flash('ERROR! Photo was not saved.', 'error')
    return render_template('main/upload.html', form=form)

"""
