import json
import os

import cv2
from datetime import datetime
from logging import log
from time import time

from flask import current_app, url_for
from flask_login import AnonymousUserMixin, UserMixin
from flask_rq import get_queue
from itsdangerous import BadSignature, SignatureExpired
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from sqlalchemy import ForeignKey, or_, and_
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import backref
from sqlalchemy_mptt.mixins import BaseNestedSets
from werkzeug.security import check_password_hash, generate_password_hash

from app.utils import pretty_date, db, login_manager


###Helper functions
def get_level(points):
    if points < 1:
        return None
    elif points <10 and points >= 1:
        return 'Rookie'
    elif points >= 10 and points <50:
        return 'Newbie'
    elif points >= 50 and points < 150 :
        return 'Apprentice'
    elif points >= 150 and points < 500:
        return 'Guru'
    elif points >= 500 and points < 1000:
        return 'Sage'
    elif points >= 1000 and points < 5000:
        return 'Maestro'
    else:
        return 'Rock Star'




class Permission:
    GENERAL = 0x01
    ADMINISTER = 0xff


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    index = db.Column(db.String(64))
    default = db.Column(db.Boolean, default=False, index=True)
    permissions = db.Column(db.Integer)
    users = db.relationship('User', backref='role', lazy='dynamic')

    @staticmethod
    def insert_roles():
        roles = {
            'User': (Permission.GENERAL, 'main', True),
            'Administrator': (
                Permission.ADMINISTER,
                'admin',
                False  # grants all permissions
            )
        }
        for r in roles:
            role = Role.query.filter_by(name=r).first()
            if role is None:
                role = Role(name=r)
            role.permissions = roles[r][0]
            role.index = roles[r][1]
            role.default = roles[r][2]
            db.session.add(role)
        db.session.commit()

    def __repr__(self):
        return '<Role \'%s\'>' % self.name


class Follower(db.Model):
    __tablename__ = 'followers'
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'))
    followed_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'))
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    confirmed = db.Column(db.Boolean, default=False)
    verified = db.Column(db.Boolean, default=False)
    first_name = db.Column(db.String(64), index=True)
    last_name = db.Column(db.String(64), index=True)
    email = db.Column(db.String(64), unique=True, index=True)
    gender = db.Column(db.String(64), index=True)
    profession = db.Column(db.String(64), index=True)
    area_code = db.Column(db.String(6), index=True)
    mobile_phone = db.Column(db.BigInteger, unique=True, index=True)
    summary_text = db.Column(db.Text)
    zip = db.Column(db.String(10), index=True)
    city = db.Column(db.String(64), index=True)
    state = db.Column(db.String(64), index=True)
    country = db.Column(db.String(64), index=True)
    password_hash = db.Column(db.String(128))
    socket_id = db.Column(db.String(256))
    online = db.Column(db.String(1), default='N')
    invited_by = db.Column(db.String(128))
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id', ondelete="CASCADE"))
    interests = db.relationship('Interest', backref='user',
                                lazy='dynamic')
    posts = db.relationship('Post', backref='user', lazy='dynamic')
    resume = db.relationship('Resume', backref='user', lazy='dynamic', cascade='all')

    comments = db.relationship('Comment', backref='user', lazy='dynamic')
    photos = db.relationship('Photo', backref='user',
                             lazy='dynamic')

    followed = db.relationship('User',
                               secondary='followers',
                               primaryjoin=(Follower.follower_id == id),
                               secondaryjoin=(Follower.followed_id == id),
                               backref=db.backref('followers', lazy='dynamic'),
                               lazy='dynamic')

    messages_received = db.relationship('Message',
                                        foreign_keys='Message.recipient_id',
                                        backref='recipient', lazy='dynamic')
    last_message_read_time = db.Column(db.DateTime)
    notifications = db.relationship('Notification', backref='user',
                                    lazy='dynamic')
    positions_created = db.relationship('Job', backref='user', lazy='subquery', cascade='all')
    questions = db.relationship('Question', backref='user', lazy='dynamic')
    newscaster_badge = db.Column(db.String())
    ambassador_badge = db.Column(db.String())
    networker_badge = db.Column(db.String())
    kw_builder_badge = db.Column(db.String())
    kw_seeker_badge = db.Column(db.String())
    newscaster_points = db.Column(db.Integer, default=0)
    ambassador_points = db.Column(db.Integer, default=0)
    networker_points =  db.Column(db.Integer, default=0)
    kw_builder_points = db.Column(db.Integer, default=0)
    kw_seeker_points = db.Column(db.Integer, default=0)
    user_applicants = db.relationship('Application', backref='user', lazy='joined')
    user_submissions = db.relationship('Submission', backref='user', lazy='joined')
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if self.role is None:
            if self.email == current_app.config['ADMIN_EMAIL']:
                self.role = Role.query.filter_by(
                    permissions=Permission.ADMINISTER).first()
            if self.role is None:
                self.role = Role.query.filter_by(default=True).first()

    @hybrid_property
    def full_name(self):
        return self.first_name + " " + self.last_name

    def can(self, permissions):
        return self.role is not None and \
               (self.role.permissions & permissions) == permissions

    def is_admin(self):
        return self.can(Permission.ADMINISTER)

    @property
    def created_day(self):
        return self.created_at.date()

    @property
    def password(self):
        raise AttributeError('`password` is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_confirmation_token(self, expiration=604800):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return str(s.dumps({'confirm': self.id}).decode())

    def generate_email_change_token(self, new_email, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'change_email': self.id, 'new_email': new_email})

    def generate_password_reset_token(self, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return str(s.dumps({'reset': self.id}).decode())

    def confirm_account(self, token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except (BadSignature, SignatureExpired):
            return False
        if data.get('confirm') != self.id:
            return False
        self.confirmed = True
        db.session.add(self)
        db.session.commit()
        return True

    def change_email(self, token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except (BadSignature, SignatureExpired):
            return False
        if data.get('change_email') != self.id:
            return False
        new_email = data.get('new_email')
        if new_email is None:
            return False
        if self.query.filter_by(email=new_email).first() is not None:
            return False
        self.email = new_email
        db.session.add(self)
        db.session.commit()
        return True

    def reset_password(self, token, new_password):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except (BadSignature, SignatureExpired):
            return False
        if data.get('reset') != self.id:
            return False
        self.password_hash = generate_password_hash(new_password)
        db.session.add(self)
        db.session.commit()
        return True

    @staticmethod
    def generate_fake(count=100, **kwargs):
        from sqlalchemy.exc import IntegrityError
        from random import seed, choice
        from faker import Faker

        fake = Faker()
        roles = Role.query.all()
        if len(roles) <= 0:
            Role.insert_roles()
            roles = Role.query.all()

        seed()
        for i in range(count):
            u = User(
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                email=fake.email(),
                profession=fake.job(),
                city=fake.city(),
                zip=fake.postcode(),
                state=fake.state(),
                summary_text=fake.text(),
                password='password',
                confirmed=True,
                role=choice(roles),
                **kwargs)
            db.session.add(u)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()

    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)
            return self

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)
            return self

    def is_following(self, user):
        return self.followed.filter(Follower.followed_id == user.id).count() > 0

    def followed_posts(self):
        followed = Post.query.join(
            Follower, (Follower.followed_id == Post.user_id)).filter(
            Follower.follower_id == self.id)
        own = Post.query.filter_by(user_id=self.id)
        return followed.union(own).order_by(Post.timestamp.desc())

    def last_message(self, user_id):
        message = Message.query.order_by(Message.timestamp.desc()). \
            filter(or_(and_(Message.recipient_id == user_id, Message.user_id == self.id),
                       and_(Message.recipient_id == self.id, Message.user_id == user_id))).first()
        return message

    def history(self, user_id, unread=False):
        messages = Message.query.order_by(Message.timestamp.asc()). \
            filter(or_(and_(Message.recipient_id == user_id, Message.user_id == self.id),
                       and_(Message.recipient_id == self.id, Message.user_id == user_id))).all()
        return messages

    def new_messages(self, user_id=None):
        if not user_id:
            return Message.query.filter_by(recipient=self).filter(Message.read_at == None).distinct('user_id').count()
        else:
            return Message.query.filter_by(recipient=self).filter(Message.read_at == None).filter(
                Message.user_id == user_id).count()

    def add_notification(self, name, data, related_id=0):
        from app.email import send_email
        self.notifications.filter_by(name=name).delete()
        n = Notification(name=name, payload_json=json.dumps(data), user=self, related_id=related_id)
        db.session.add(n)
        get_queue().enqueue(
            send_email,
            recipient=self.email,
            subject='You have a new notification on Networked.ng',
            template='account/email/notification',
            user=self,
            link=url_for('main.notifications', _external=True),
            notification=n
        )
        return n

    def get_post_karma(self):
        """
        fetch the number of votes this user has had on his/her posts
        1.) Get id's of all posts by this user
        2.) See how many of those posts also were upvoted but not by
        the person him/her self.
        """
        post_ids = [t.id for t in self.posts]
        select = PostUpvote.select(db.and_(
            PostUpvote.post_id.in_(post_ids),
            PostUpvote.user_id != self.id
        )
        )
        rs = db.engine.execute(select)
        return rs.rowcount

    def get_comment_karma(self):
        """
        fetch the number of votes this user has had on his/her comments
        """
        comment_ids = [c.id for c in self.comments]
        select = CommentUpvote.select(db.and_(
            CommentUpvote.comment_id.in_(comment_ids),
            CommentUpvote.user_id != self.id
        )
        )
        rs = db.engine.execute(select)
        return rs.rowcount

    def get_photo(self):
        photos = self.photos.all()
        if len(photos) > 0:
            return url_for('_uploads.uploaded_file', setname='images',
                           filename=photos[0].image_filename, _external=True)
        else:
            if self.gender == 'Female':
                return "https://1.semantic-ui.com/images/avatar/large/veronika.jpg"
            else:
                return "https://1.semantic-ui.com/images/avatar/large/jenny.jpg"

    def __repr__(self):
        return '<User \'%s\'>' % self.full_name


class AnonymousUser(AnonymousUserMixin):
    def can(self):
        return False

    def is_admin(self):
        return False


login_manager.anonymous_user = AnonymousUser


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class EntryTag(db.Model):
    __tablename__ = 'entry_tags'
    __table_args__ = (db.PrimaryKeyConstraint('question_id', 'tag_id'), {})
    tag_id = db.Column('tag_id', db.Integer, db.ForeignKey('tags.id', ondelete='CASCADE'), nullable=False)
    question_id = db.Column('question_id', db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'),
                            nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())


class Tag(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    tag = db.Column(db.String(25))
    questions = db.relationship('Question', secondary='entry_tags', backref='tag')


class PositionApplication(db.Model):
    __tablename__ = 'job_applications'
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id', ondelete="CASCADE"))
    position_id = db.Column(db.Integer, db.ForeignKey('jobs.id', ondelete="CASCADE"))
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

class PromoSubmission(db.Model):
    __tablename__ = 'promo_submissions'
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id', ondelete="CASCADE"))
    promo_id = db.Column(db.Integer, db.ForeignKey('promos.id', ondelete="CASCADE"))
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())


class EventAttendee(db.Model):
    __tablename__ = 'event_attendees'
    id = db.Column(db.Integer, primary_key=True)
    attendee_id = db.Column(db.Integer, db.ForeignKey('attendees.id', ondelete="CASCADE"))
    event_id = db.Column(db.Integer, db.ForeignKey('events.id', ondelete="CASCADE"))
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='cascade'))
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"))
    body = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=db.func.now())
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
    read_at = db.Column(db.DateTime, default=None, nullable=True)

    user = db.relationship('User', primaryjoin="Message.user_id==User.id")

    def __repr__(self):
        return '<Message {}>'.format(self.body)


class Interest(db.Model):
    __tablename__ = 'interests'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(), unique=True)
    desc = db.Column(db.String())
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"))
    posts = db.relationship('Post', backref='interest', lazy='dynamic')
    status = db.Column(db.SmallInteger)
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def __init__(self, name, desc, admin_id):
        self.name = name
        self.desc = desc
        self.admin_id = admin_id

    def __repr__(self):
        return '<interest %r>' % self.name

    def get_posts(self, order_by='timestamp'):
        if order_by == 'timestamp':
            return self.posts.order_by(db.desc(Post.created_at)). \
                all()
        else:
            return self.posts.order_by(db.desc(Post.created_at)). \
                all()

    def get_age(self):
        return (self.created_at - datetime(1970, 1, 1)).total_seconds()

    def pretty_date(self, typeof='created'):
        if typeof == 'created':
            return pretty_date(self.created_at)
        elif typeof == 'updated':
            return pretty_date(self.updated_at)


class Organisation(db.Model):
    __tablename__ = 'organisations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    image_filename = db.Column(db.String, default=None, nullable=True)
    image_url = db.Column(db.String, default=None, nullable=True)
    org_name = db.Column(db.String(255))
    org_city = db.Column(db.String(255))
    org_state = db.Column(db.String(255))
    org_country = db.Column(db.String(255))
    org_website = db.Column(db.String(255))
    org_industry = db.Column(db.String(255))
    org_description = db.Column(db.Text)
    logos = db.relationship('Logo', backref='organisation', lazy='dynamic')
    user = db.relationship('User', backref='organisations', cascade='all, delete')
    jobs = db.relationship('Job', backref='organisation')
    promos = db.relationship('Promo', backref='organisation')
    services = db.relationship('Service', backref='organisation')
    products = db.relationship('Product', backref='organisation')
    events = db.relationship('Event', backref='organisation')
    positions = db.relationship('Job', backref='organisation_positions',
                                primaryjoin="Organisation.id==Job.organisation_id")
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return u'<{self.__class__.__name__}: {self.id}>'.format(self=self)

    def get_staff(self):
        ids = [user.user_id for user in self.staff]
        return User.query.filter(User.id.in_(ids)).all()

    def get_photo(self):
        if self.image_filename:
            return url_for('_uploads.uploaded_file', setname='images', filename=self.image_filename, _external=True)
        else:
            return url_for('static', filename="images/medium_logo_default.png")


class Logo(db.Model):
    __tablename__ = 'logos'
    id = db.Column(db.Integer, primary_key=True)
    image_filename = db.Column(db.String, default=None, nullable=True)
    image_url = db.Column(db.String, default=None, nullable=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id', ondelete="CASCADE"), nullable=False)
    owner_organisation = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return u'<{self.__class__.__name__}: {self.id}>'.format(self=self)

#Uncomment to use
class Product_Image(db.Model):
    __tablename__ = 'product_images'
    id = db.Column(db.Integer, primary_key=True)
    image_filename = db.Column(db.String, default=None, nullable=True)
    image_url = db.Column(db.String, default=None, nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete="CASCADE"), nullable=False)
    owner_product = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return u'<{self.__class__.__name__}: {self.id}>'.format(self=self)

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organisations.id', ondelete="CASCADE"), nullable=False)
    image_filename = db.Column(db.String, default=None, nullable=True)
    image_url = db.Column(db.String, default=None, nullable=True)
    product_name = db.Column(db.String(255))
    product_description = db.Column(db.Text)
    product_price = db.Column(db.Integer)
    price_currency = db.Column(db.String(255))
    min_order_quantity = db.Column(db.Integer)
    product_availability = db.Column(db.String(255))
    product_category = db.Column(db.String(255))
    product_images = db.relationship('Product_Image', backref='product', lazy='dynamic')
    product_length = db.Column(db.Integer)
    product_weight = db.Column(db.Integer)
    product_height = db.Column(db.Integer)
    delivery_terms = db.Column(db.String(255))
    lead_time = db.Column(db.String(255))
    #organisation = db.relationship('Organisation', backref='products', cascade='all, delete')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return u'<{self.__class__.__name__}: {self.id}>'.format(self=self)

    def get_photo(self):
        if self.image_filename:
            return url_for('_uploads.uploaded_file', setname='images', filename=self.image_filename, _external=True)
        else:
            return url_for('static', filename="images/medium_logo_default.png")


class Photo(db.Model):
    __tablename__ = 'photos'
    id = db.Column(db.Integer, primary_key=True)
    image_filename = db.Column(db.String, default=None, nullable=True)
    image_url = db.Column(db.String, default=None, nullable=True)
    user_id = db.Column(db.Integer(), db.ForeignKey(User.id, ondelete="CASCADE"))
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete="CASCADE"))
    answer_id = db.Column(db.Integer, db.ForeignKey('answers.id', ondelete="CASCADE"))
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return u'<{self.__class__.__name__}: {self.id}>'.format(self=self)


class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String)
    description = db.Column(db.String)
    timestamp = db.Column(db.DateTime, index=True, default=db.func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"))
    author = db.Column(db.String(128))
    tags = db.relationship('Tag', secondary='entry_tags', backref='question')
    answers = db.relationship('Answer', backref='question', lazy='dynamic')
    photos = db.relationship('Photo', backref='question_photos', lazy='dynamic')
    comments = db.relationship('Comment', backref='question_comments', lazy='dynamic')
    level = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())


class Answer(db.Model, BaseNestedSets):
    __tablename__ = 'answers'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String, index=True)
    timestamp = db.Column(db.DateTime, index=True, default=db.func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"))
    author = db.Column(db.String(128))
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete="CASCADE"))
    photos = db.relationship('Photo', backref='answers_photos', lazy='dynamic')
    creator = db.relationship('User')
    image_url = db.Column(db.String, default=None, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())


class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"))
    related_id = db.Column(db.Integer, default=0)
    timestamp = db.Column(db.Float, index=True, default=time)
    payload_json = db.Column(db.Text)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def get_data(self):
        return json.loads(str(self.payload_json))


class Job(db.Model):
    __tablename__ = 'jobs'
    id = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id', ondelete="CASCADE"), nullable=True)
    image_filename = db.Column(db.String, default=None, nullable=True)
    pub_date = db.Column(db.DateTime, default=datetime.now, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    position_title = db.Column(db.String(255))
    position_city = db.Column(db.String(255))
    position_state = db.Column(db.String(255))
    position_country = db.Column(db.String(255))
    required_skill_one = db.Column(db.String(255))
    required_skill_two = db.Column(db.String(255))
    required_skill_three = db.Column(db.String(255))
    required_skill_four = db.Column(db.String(255))
    required_skill_five = db.Column(db.String(255))
    required_skill_six = db.Column(db.String(255))
    required_skill_seven = db.Column(db.String(255))
    required_skill_eight = db.Column(db.String(255))
    required_skill_nine = db.Column(db.String(255))
    required_skill_ten = db.Column(db.String(255))
    description = db.Column(db.Text)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    applications = db.relationship("Application", secondary='job_applications',
                                   backref=backref("positions", cascade='all'),
                                   primaryjoin='Job.id==Application.position_id', cascade='all,delete')
    creator = db.relationship("User")
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    @property
    def org_name(self):
        return Organisation.get(self.organisation_id).org_name

    def get_photo(self):
        if self.image_filename:
            return url_for('_uploads.uploaded_file', setname='images', filename=self.image_filename, _external=True)
        else:
            return self.organisation.get_photo()

    def __repr__(self):
        return u'<{self.__class__.__name__}: {self.id}>'.format(self=self)

class Promo(db.Model):
    __tablename__ = 'promos'
    id = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id', ondelete="CASCADE"), nullable=True)
    image_filename = db.Column(db.String, default=None, nullable=True)
    pub_date = db.Column(db.DateTime, default=datetime.now, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    promo_title = db.Column(db.String(255))
    promo_city = db.Column(db.String(255))
    promo_state = db.Column(db.String(255))
    promo_country = db.Column(db.String(255))
    requirement_one = db.Column(db.String(255))
    requirement_two = db.Column(db.String(255))
    requirement_three = db.Column(db.String(255))
    requirement_four = db.Column(db.String(255))
    requirement_five = db.Column(db.String(255))
    requirement_six = db.Column(db.String(255))
    requirement_seven = db.Column(db.String(255))
    requirement_eight = db.Column(db.String(255))
    requirement_nine = db.Column(db.String(255))
    requirement_ten = db.Column(db.String(255))
    description = db.Column(db.Text)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    submissions = db.relationship("Submission", secondary='promo_submissions',
                                   backref=backref("promos", cascade='all'),
                                   primaryjoin='Promo.id==Submission.promo_id', cascade='all,delete')
    creator = db.relationship("User")
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    @property
    def org_name(self):
        return Organisation.get(self.organisation_id).org_name

    def get_photo(self):
        if self.image_filename:
            return url_for('_uploads.uploaded_file', setname='images', filename=self.image_filename, _external=True)
        else:
            return self.organisation.get_photo()

    def __repr__(self):
        return u'<{self.__class__.__name__}: {self.id}>'.format(self=self)

#### Uncomment to put to use ###
##class product(db.Model):
##    __tablename__ = 'products'
##    id = db.Column(db.Integer, primary_key=True)
##    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id', ondelete="CASCADE"), nullable=True)
##    image_filename = db.Column(db.String, default=None, nullable=True)
##    image_url = db.Column(db.String, default=None, nullable=True)
##    pub_date = db.Column(db.DateTime, default=datetime.now, nullable=False)
##    product_category = db.Column(db.String(255))
##    product_name = db.Column(db.String(255))
##    brand_name = db.Column(db.String(255))
##    product_type = db.Column(db.String(255))
##    product_size = db.Column(db.String(255))
##    material = db.Column(db.String(255))
##    min_order_quantity = db.Column(db.Integer)
##    lead_time = db.Column(db.String(255))
##    product_weight = db.Column(db.String(255))
##    delivery_terms = db.Column(db.String(255))
##    description = db.Column(db.Text)
##    creator_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
##    creator = db.relationship("User")
##    created_at = db.Column(db.DateTime, default=datetime.now)
##    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
##
##    @property
##    def org_name(self):
##        return Organisation.get(self.organisation_id).org_name
##
##    def get_photo(self):
##        if self.image_filename:
##            return url_for('_uploads.uploaded_file', setname='images', filename=self.image_filename, _external=True)
##        else:
##            return self.organisation.get_photo()
##
##    def __repr__(self):
##        return u'<{self.__class__.__name__}: {self.id}>'.format(self=self)

class Service(db.Model):
    __tablename__ = 'services'
    id = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id', ondelete="CASCADE"), nullable=True)
    pub_date = db.Column(db.DateTime, default=datetime.now, nullable=False)
    service_category = db.Column(db.String(255))
    service_title = db.Column(db.String(255))
    service_city = db.Column(db.String(255))
    service_state = db.Column(db.String(255))
    service_country = db.Column(db.String(255))
    mobile_phone = db.Column(db.BigInteger, unique=True, index=True)
    street_address = db.Column(db.String(255))
    description = db.Column(db.Text)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    creator = db.relationship("User")
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    @property
    def org_name(self):
        return Organisation.get(self.organisation_id).org_name

    def get_photo(self):
        if self.image_filename:
            return url_for('_uploads.uploaded_file', setname='images', filename=self.image_filename, _external=True)
        else:
            return self.organisation.get_photo()

    def __repr__(self):
        return u'<{self.__class__.__name__}: {self.id}>'.format(self=self)

class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id', ondelete="CASCADE"), nullable=True)
    image_filename = db.Column(db.String, default=None, nullable=True)
    pub_date = db.Column(db.DateTime, default=datetime.now, nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    event_title = db.Column(db.String(255))
    event_city = db.Column(db.String(255))
    event_state = db.Column(db.String(255))
    event_country = db.Column(db.String(255))
    description = db.Column(db.Text)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    attendees = db.relationship("Attendee", secondary='event_attendees',
                                   backref=backref("events", cascade='all'),
                                   primaryjoin='Event.id==Attendee.event_id', cascade='all,delete')
    creator = db.relationship("User")
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    @property
    def org_name(self):
        return Organisation.get(self.organisation_id).org_name

    def get_photo(self):
        if self.image_filename:
            return url_for('_uploads.uploaded_file', setname='images', filename=self.image_filename, _external=True)
        else:
            return self.organisation.get_photo()

    def __repr__(self):
        return u'<{self.__class__.__name__}: {self.id}>'.format(self=self)

class Attendee(db.Model):
    __tablename__ = 'attendees'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id', ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    event = db.relationship('Event', cascade='all, delete')
    users = db.relationship('User', order_by=User.id, backref="attendees", cascade="all")
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

class Submission(db.Model):
    __tablename__ = 'submissions'
    id = db.Column(db.Integer, primary_key=True)
    promo_id = db.Column(db.Integer, db.ForeignKey('promos.id', ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    event = db.relationship('Promo', cascade='all, delete')
    users = db.relationship('User', order_by=User.id, backref="submissions", cascade="all")
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
   
class ApplicationExtra(db.Model):
    __tablename__ = 'application_extras'
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id', ondelete="CASCADE"))
    extra_id = db.Column(db.Integer, db.ForeignKey('extras.id', ondelete="CASCADE"))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


class Application(db.Model):
    __tablename__ = 'applications'
    id = db.Column(db.Integer, primary_key=True)
    extras = db.relationship('Extra', secondary='application_extras', backref='applications')
    position_id = db.Column(db.Integer, db.ForeignKey('jobs.id', ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    position = db.relationship('Job', cascade='all, delete')
    users = db.relationship('User', order_by=User.id, backref="application", cascade="all")
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


class Extra(db.Model):
    __tablename__ = 'extras'
    id = db.Column(db.Integer, primary_key=True)
    image_filename = db.Column(db.String, default=None, nullable=True)
    image_url = db.Column(db.String, default=None, nullable=True)
    required_skill_one = db.Column(db.String(255))
    required_skill_two = db.Column(db.String(255))
    required_skill_three = db.Column(db.String(255))
    required_skill_four = db.Column(db.String(255))
    required_skill_five = db.Column(db.String(255))
    required_skill_six = db.Column(db.String(255))
    required_skill_seven = db.Column(db.String(255))
    required_skill_eight = db.Column(db.String(255))
    required_skill_nine = db.Column(db.String(255))
    required_skill_ten = db.Column(db.String(255))
    user_id = db.Column(db.Integer(), db.ForeignKey(User.id, ondelete="cascade"))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

class PostUpvote(db.Model):
    __tablename__ = 'post_upvotes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"))
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id', ondelete="CASCADE"))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


class CommentUpvote(db.Model):
    __tablename__ = 'comment_upvotes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"))
    comment_id = db.Column(db.Integer, db.ForeignKey('post_comments.id', ondelete="CASCADE"))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


class PostLike(db.Model):
    __tablename__ = 'post_likes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, default=1)
    post_id = db.Column(db.Integer, ForeignKey('posts.id', ondelete="CASCADE"))
    user = db.relationship('User', foreign_keys=[user_id], primaryjoin="User.id==PostLike.user_id")
    post = db.relationship('Post', foreign_keys=[post_id])
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())


class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String())
    text = db.Column(db.String(), default=None)
    thumbnail = db.Column(db.String(), default=None)
    post_privacy = db.Column(db.Integer, default=0)
    author = db.Column(db.String(128))
    image_filename = db.Column(db.Text, default=None, nullable=True)
    image_url = db.Column(db.Text, default=None, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"))
    interest_id = db.Column(db.Integer, db.ForeignKey('interests.id', ondelete="CASCADE"))
    comments = db.relationship('Comment', backref=backref('post'), lazy='dynamic',
                               cascade="all, delete-orphan")
    likes = db.relationship('PostLike', lazy='dynamic', cascade="all, delete-orphan")
    votes = db.Column(db.Integer, default=1)
    hotness = db.Column(db.Float(15, 6), default=0.00)
    creator = db.relationship('User')
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def image_size(self, val):
        curr = os.path.dirname(os.path.realpath(__file__))
        img = cv2.imread(curr+'/../../appstatic/photo/'+val, 0)
        if img is not None:
            height, width = img.shape[:2]
        else:
            height, width = 0, 0
        return json.dumps([width, height])

    def user_likes(self, user_id):
        likes = PostLike.query.filter_by(post_id=self.id).all()
        user_ids = [like.user_id for like in likes]
        if user_id in user_ids:
            return True
        return False

    def __repr__(self):
        return '<post %r>' % self.title

    def get_comments(self, order_by='timestamp'):
        """
        default order by timestamp
        return only top levels!
        """
        if order_by == 'timestamp':
            return self.comments.filter_by(depth=1). \
                order_by(db.desc(Comment.created_at)).all()
        else:
            return self.comments.filter_by(depth=1). \
                order_by(db.desc(Comment.created_at)).all()

    def get_age(self):
        """
        returns the raw age of this post in seconds
        """
        return (self.created_at - datetime(1970, 1, 1)).total_seconds()

    def get_hotness(self):
        """
        returns the reddit hotness algorithm (votes/(age^1.5))
        """
        order = log(max(abs(self.votes), 1), 10)  # Max/abs are not needed in our case
        seconds = self.get_age() - 1134028003
        return round(order + seconds / 45000, 6)

    def set_hotness(self):
        """
        returns the reddit hotness algorithm (votes/(age^1.5))
        """
        self.hotness = self.get_hotness()
        db.session.commit()

    def pretty_date(self, typeof='created'):
        """
        returns a humanized version of the raw age of this post,
        eg: 34 minutes ago versus 2040 seconds ago.
        """
        if typeof == 'created':
            return pretty_date(self.created_at)
        elif typeof == 'updated':
            return pretty_date(self.updated_at)

    def add_comment(self, comment_text, comment_parent_id, user_id):
        """
        add a comment to this particular post
        """
        if int(comment_parent_id) != 0:
            # parent_comment = Comment.query.get_or_404(comment_parent_id)
            # if parent_comment.depth + 1 > post.MAX_COMMENT_DEPTH:
            #    flash('You have exceeded the maximum comment depth')
            comment_parent_id = int(comment_parent_id)
            comment = Comment(post_id=self.id, user_id=user_id,
                              text=comment_text, parent_id=comment_parent_id)
        else:
            comment = Comment(post_id=self.id, user_id=user_id,
                              text=comment_text)

        db.session.add(comment)
        db.session.commit()
        comment.set_depth()
        return comment

    def get_voter_ids(self):
        """
        return ids of users who voted this post up
        """
        select = PostUpvote.select(PostUpvote.post_id == self.id)
        rs = db.engine.execute(select)
        ids = rs.fetchall()  # list of tuples
        return ids

    def has_voted(self, user_id):
        """
        did the user vote already
        """
        select_votes = PostUpvote.select(
            db.and_(
                PostUpvote.user_id == user_id,
                PostUpvote.post_id == self.id
            )
        )
        rs = db.engine.execute(select_votes)
        return False if rs.rowcount == 0 else True

    def vote(self, user_id):
        """
        allow a user to vote on a post. if we have voted already
        (and they are clicking again), this means that they are trying
        to unvote the post, return status of the vote for that user
        """
        already_voted = self.has_voted(user_id)
        vote_status = None
        if not already_voted:
            # vote up the post
            db.engine.execute(
                PostUpvote.insert(),
                user_id=user_id,
                post_id=self.id
            )
            self.votes = self.votes + 1
            vote_status = True
        else:
            # unvote the post
            db.engine.execute(
                PostUpvote.delete(
                    db.and_(
                        PostUpvote.user_id == user_id,
                        PostUpvote.post_id == self.id
                    )
                )
            )
            self.votes = self.votes - 1
            vote_status = False
        db.session.commit()  # for the vote count
        return vote_status

    def extract_thumbnail(self):
        """
        ideally this type of heavy content fetching should be put on a
        celery background task manager or at least a crontab.. instead of
        setting it to run literally as someone posts a post. but once again,
        this repo is just a simple example of a reddit-like crud application!
        """
        default_thumbnail = 'https://reddit.codelucas.com/static/imgs/reddit-camera.png'
        thumbnail = None
        if self.link:
            thumbnail = 'https://reddit.codelucas.com/static/imgs/reddit-camera.png'
        if not thumbnail:
            thumbnail = default_thumbnail
        self.thumbnail = thumbnail
        db.session.commit()


class Comment(db.Model, BaseNestedSets):
    __tablename__ = 'post_comments'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(), default=None)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"))
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id', ondelete="CASCADE"))
    author = db.relationship('User')
    depth = db.Column(db.Integer, default=1)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete="CASCADE"))
    votes = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return '<Comment %r>' % (self.text[:25])

    def __init__(self, post_id, user_id, text, parent_id=None):
        self.post_id = post_id
        self.user_id = user_id
        self.text = text
        self.parent_id = parent_id

    def set_depth(self):
        """
        call after initializing
        """
        if self.parent:
            self.depth = self.parent.depth + 1
            db.session.commit()

    def get_comments(self, order_by='timestamp'):
        """
        default order by timestamp
        """
        if order_by == 'timestamp':
            return self.children.order_by(db.desc(Comment.created_at)). \
                all()
        else:
            return self.comments.order_by(db.desc(Comment.created_at)). \
                all()

    def get_margin_left(self):
        """
        nested comments are pushed right on a page
        -15px is our default margin for top level comments
        """
        margin_left = 15 + ((self.depth - 1) * 32)
        margin_left = min(margin_left, 680)
        return str(margin_left) + "px"

    def get_age(self):
        """
        returns the raw age of this post in seconds
        """
        return (self.created_at - datetime.datetime(1970, 1, 1)).total_seconds()

    def pretty_date(self, typeof='created'):
        """
        returns a humanized version of the raw age of this post,
        eg: 34 minutes ago versus 2040 seconds ago.
        """
        if typeof == 'created':
            return pretty_date(self.created_at)
        elif typeof == 'updated':
            return pretty_date(self.updated_at)


class OrgStaff(db.Model):
    __tablename__ = 'org_staff'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"))
    invited_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"))
    org_id = db.Column(db.Integer, db.ForeignKey('organisations.id', ondelete="CASCADE"))
    user = db.relationship("User", primaryjoin="User.id==OrgStaff.user_id")
    referer = db.relationship("User", primaryjoin="User.id==OrgStaff.invited_by")
    org = db.relationship("Organisation", primaryjoin="Organisation.id==OrgStaff.org_id", backref='staff')
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())


class ContactMessage(db.Model):
    __tablename__ = 'contact_messages'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"), nullable=True)
    name = db.Column(db.String(), default=None, nullable=True)
    email = db.Column(db.String(64), default=None, nullable=True)
    text = db.Column(db.Text)
    user = db.relationship("User")

    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())




class Resume(db.Model):
    __tablename__ = 'resumes'
    id = db.Column(db.Integer, primary_key=True)

    company_name_one = db.Column(db.String(255))
    company_summary_one = db.Column(db.String(255))
    role_one = db.Column(db.String(255))
    role_description_one = db.Column(db.Text)
    start_date_one = db.Column(db.DateTime)
    end_date_one = db.Column(db.DateTime)
    currently_one = db.Column(db.String(3))
    location_city_one = db.Column(db.String(255))
    location_state_one = db.Column(db.String(255))
    location_country_one = db.Column(db.String(255))


    company_name_two = db.Column(db.String(255))
    company_summary_two = db.Column(db.String(255))
    role_two = db.Column(db.String(255))
    role_description_two = db.Column(db.Text)
    start_date_two = db.Column(db.DateTime)
    end_date_two = db.Column(db.DateTime)
    currently_two = db.Column(db.String(3))
    location_city_two = db.Column(db.String(255))
    location_state_two = db.Column(db.String(255))
    location_country_two = db.Column(db.String(255))
    
    
    company_name_three = db.Column(db.String(255))
    company_summary_three = db.Column(db.String(255))
    role_three = db.Column(db.String(255))
    role_description_three = db.Column(db.Text)
    start_date_three = db.Column(db.DateTime)
    end_date_three = db.Column(db.DateTime)
    currently_three = db.Column(db.String(3))
    location_city_three = db.Column(db.String(255))
    location_state_three = db.Column(db.String(255))
    location_country_three = db.Column(db.String(255))

    company_name_four = db.Column(db.String(255))
    company_summary_four = db.Column(db.String(255))
    role_four = db.Column(db.String(255))
    role_description_four = db.Column(db.Text)
    start_date_four = db.Column(db.DateTime)
    end_date_four = db.Column(db.DateTime)
    currently_four = db.Column(db.String(3))
    location_city_four = db.Column(db.String(255))
    location_state_four = db.Column(db.String(255))
    location_country_four = db.Column(db.String(255))

    company_name_five = db.Column(db.String(255))
    company_summary_five = db.Column(db.String(255))
    role_five = db.Column(db.String(255))
    role_description_five = db.Column(db.Text)
    start_date_five = db.Column(db.DateTime)
    end_date_five = db.Column(db.DateTime)
    currently_five = db.Column(db.String(3))
    location_city_five = db.Column(db.String(255))
    location_state_five = db.Column(db.String(255))
    location_country_five = db.Column(db.String(255))    

    company_name_six = db.Column(db.String(255))
    company_summary_six = db.Column(db.String(255))
    role_six = db.Column(db.String(255))
    role_description_six = db.Column(db.Text)
    start_date_six = db.Column(db.DateTime)
    end_date_six = db.Column(db.DateTime)
    currently_six = db.Column(db.String(3))
    location_city_six = db.Column(db.String(255))
    location_state_six = db.Column(db.String(255))
    location_country_six = db.Column(db.String(255))


    school_name_one = db.Column(db.String(255))
    degree_description_one = db.Column(db.String(255))
    grading_one = db.Column(db.String(255))
    school_start_date_one = db.Column(db.DateTime)
    school_end_date_one = db.Column(db.DateTime)
    school_currently_one = db.Column(db.String(3))
    state_school_one = db.Column(db.String(255))
    city_school_one = db.Column(db.String(255))
    country_school_one = db.Column(db.String(255))

    school_name_two = db.Column(db.String(255))
    degree_description_two = db.Column(db.String(255))
    grading_two = db.Column(db.String(255))
    school_start_date_two = db.Column(db.DateTime)
    school_end_date_two = db.Column(db.DateTime)
    school_currently_two = db.Column(db.String(3))
    state_school_two = db.Column(db.String(255))
    city_school_two = db.Column(db.String(255))
    country_school_two = db.Column(db.String(255))

    school_name_three = db.Column(db.String(255))
    degree_description_three = db.Column(db.String(255))
    grading_three = db.Column(db.String(255))
    school_start_date_three = db.Column(db.DateTime)
    school_end_date_three = db.Column(db.DateTime)
    school_currently_three = db.Column(db.String(255))
    state_school_three = db.Column(db.String(255))
    city_school_three = db.Column(db.String(255))
    country_school_three = db.Column(db.String(255))

    school_name_four = db.Column(db.String(255))
    degree_description_four = db.Column(db.String(255))
    grading_four = db.Column(db.String(255))
    school_start_date_four = db.Column(db.DateTime)
    school_end_date_four = db.Column(db.DateTime)
    school_currently_four = db.Column(db.String(255))
    state_school_four = db.Column(db.String(255))
    city_school_four = db.Column(db.String(255))
    country_school_four = db.Column(db.String(255))

    school_name_five = db.Column(db.String(255))
    degree_description_five = db.Column(db.String(255))
    grading_five = db.Column(db.String(255))
    school_start_date_five = db.Column(db.DateTime)
    school_end_date_five = db.Column(db.DateTime)
    school_currently_five = db.Column(db.String(255))
    state_school_five = db.Column(db.String(255))
    city_school_five = db.Column(db.String(255))
    country_school_five = db.Column(db.String(255))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


    def __repr__(self):
        return u'<{self.__class__.__name__}: {self.id}>'.format(self=self)
    



