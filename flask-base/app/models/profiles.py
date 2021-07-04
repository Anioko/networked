from datetime import datetime

from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import query_expression

from app.utils import db, get_lang_name, whooshee
#from app import whooshee


@whooshee.register_model('first_name', 'last_name', 'title', 'header')
class Profile(db.Model):
    __tablename__ = 'profiles'

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(64), index=True)
    last_name = db.Column(db.String(64), index=True)
    title = db.Column(db.String(256), index=True)
    header = db.Column(db.String(512), index=True)
    commitment = db.Column(db.String)
    type_of_work = db.Column(db.String)
    image = db.Column(db.String, default=None, nullable=True)
    cover = db.Column(db.String, default=None, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='cascade'))

    user = db.relationship('User', backref='profiles')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    score = query_expression()

    def employer_can_download(self, employer_id):
        return self.messages.filter(ProfileMessage.recipient_id == employer_id).first()

    @hybrid_property
    def full_name(self):
        return self.first_name + " " + self.last_name

    @property
    def completeness(self):
        perc = 10
        if self.skills:
            perc += 18
        if self.education:
            perc += 18
        if self.jobs:
            perc += 18
        if self.projects:
            perc += 18
        if self.languages:
            perc += 18

        return perc


# Please reflect any changes to this form in account/profile_edit.html template
@whooshee.register_model('name', 'description', 'exp')
class ProfileSkill(db.Model):
    __tablename__ = 'profile_skills'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), index=True)
    description = db.Column(db.String(512), index=True)
    exp = db.Column(db.String)#(name='commitment', N='Nobie', I='Intermediate', E='Experienced', G='Guru'))
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id', ondelete='cascade'))

    profile = db.relationship('Profile', backref='skills')
    score = query_expression()


# Please reflect any changes to this form in account/profile_edit.html template
@whooshee.register_model('school', 'degree')
class ProfileEdu(db.Model):
    __tablename__ = 'profile_education'

    id = db.Column(db.Integer, primary_key=True)
    school = db.Column(db.String(256), index=True)
    degree = db.Column(db.String)#(name='commitment', A='Associate', B='Bachelor', M='Master', D='Doctoral'))
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, default=None, nullable=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id', ondelete='cascade'))

    profile = db.relationship('Profile', backref='education')
    score = query_expression()


# Please reflect any changes to this form in account/profile_edit.html template
@whooshee.register_model('company', 'title')
class ProfileJob(db.Model):
    __tablename__ = 'profile_jobs'

    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(256), index=True)
    title = db.Column(db.String(256), index=True)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, default=None, nullable=True)
    commitment = db.Column(db.String)#(name='commitment', F='Full Time', P='Part Time'))
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id', ondelete='cascade'))

    profile = db.relationship('Profile', backref='jobs')
    score = query_expression()


# Please reflect any changes to this form in account/profile_edit.html template
@whooshee.register_model('lang', 'level')
class ProfileLang(db.Model):
    __tablename__ = 'profile_langs'

    id = db.Column(db.Integer, primary_key=True)
    lang = db.Column(db.String(2), index=True)
    level = db.Column(db.String)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id', ondelete='cascade'))

    profile = db.relationship('Profile', backref='languages')
    score = query_expression()

    @property
    def name(self):
        return get_lang_name(self.lang)

# Please reflect any changes to this form in account/profile_edit.html template
@whooshee.register_model('name', 'description', 'links')
class ProfileProject(db.Model):
    __tablename__ = 'profile_projects'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), index=True)
    description = db.Column(db.String(512), index=True)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, default=None, nullable=True)
    links = db.Column(db.JSON)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id', ondelete='cascade'))

    profile = db.relationship('Profile', backref='projects')
    score = query_expression()


class ProfileMessage(db.Model):
    __tablename__ = 'profile_messages'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='cascade'))
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"))
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id', ondelete='cascade'))
    body = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=db.func.now())
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
    read_at = db.Column(db.DateTime, default=None, nullable=True)

    user = db.relationship('User', primaryjoin="ProfileMessage.user_id==User.id")
    # recipient = db.relationship('User', primaryjoin="ProfileMessage.recipient_id==User.id")
    profile = db.relationship('Profile', backref=db.backref('messages', lazy='dynamic'))

    def __repr__(self):
        return '<Message {}>'.format(self.body)
