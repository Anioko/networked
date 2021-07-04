import json
import operator
import os
import uuid
from hashlib import sha512

from flask import Flask
from flask_assets import Environment
from flask_ckeditor import CKEditor
from flask_compress import Compress
from flask_mail import Mail
from flask_moment import Moment
from flask_rq import RQ
from flask_share import Share
from flask_uploads import UploadSet, configure_uploads, IMAGES
from flask_wtf import CSRFProtect
#import flask_monitoringdashboard as dashboard
#from werkzeug.contrib.profiler import ProfilerMiddleware
#from flask_s3 import FlaskS3
#from flask_jwt_extended import JWTManager
from flask_session import Session

from flask_whooshee import Whooshee

from app.blueprints.api.views import main_api
from app.utils import db, login_manager
from config import config
from .assets import app_css, app_js, vendor_css, vendor_js
from flask_caching import Cache

from flask_recaptcha import ReCaptcha

# from app.models import Notification

basedir = os.path.abspath(os.path.dirname(__file__))

mail = Mail()
csrf = CSRFProtect()
compress = Compress()
images = UploadSet('images', IMAGES)
docs = UploadSet('docs', ('rtf', 'odf', 'ods', 'gnumeric', 'abw', 'doc', 'docx', 'xls', 'xlsx', 'pdf'))
share = Share()
moment = Moment()
#jwt = JWTManager()
sess = Session()
# Set up Flask-Login
login_manager.session_protection = 'strong'
login_manager.login_view = 'account.login'
#s3 = FlaskS3()

# Set up Flask-Login
login_manager.session_protection = 'strong'
login_manager.login_view = 'account.login'

import app.models as models

whooshee = Whooshee()
recaptcha = ReCaptcha()


def json_load(string):
    return json.loads(string)


def create_app(config_name):
    app = Flask(__name__)
    #whooshee = Whooshee(app)
    app.config.from_object(config[config_name])
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_POOL_RECYCLE']=280
    #app.config['SQLALCHEMY_POOL_SIZE'] = 10
    #app.config['SQLALCHEMY_MAX_OVERFLOW'] = 5
    # not using sqlalchemy event system, hence disabling it
    app.config['UPLOADED_IMAGES_DEST'] = '/home/ubuntu/flaskapp/flask-base/appstatic/photo/' if \
        not os.environ.get('UPLOADED_IMAGES_DEST') else os.path.dirname(os.path.realpath(__file__)) + os.environ.get(
        'UPLOADED_IMAGES_DEST')
    app.config['UPLOADED_DOCS_DEST'] = '/home/ubuntu/flaskapp/flask-base/appstatic/docs/' if \
        not os.environ.get('UPLOADED_DOCS_DEST') else os.path.dirname(os.path.realpath(__file__)) + os.environ.get(
        'UPLOADED_DOCS_DEST')
    app.config['docs'] = app.config['UPLOADED_DOCS_DEST']

    app.config['CKEDITOR_SERVE_LOCAL'] = True
    app.config['CKEDITOR_HEIGHT'] = 400
    app.config['CKEDITOR_FILE_UPLOADER'] = 'upload'
    app.config['CKEDITOR_ENABLE_CSRF'] = True  # if you want to enable CSRF protect, uncomment this line
    app.config['UPLOADED_PATH'] = os.path.join(basedir, 'uploads')
    #app.config['FLASKS3_BUCKET_NAME'] = 'networkedng1'
    #s3 = FlaskS3(app)
    app.config["DEBUG"] = True
    
    app.config['CACHE_TYPE'] = 'simple'
    config[config_name].init_app(app)

    # Set up extensions
    mail.init_app(app)
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    compress.init_app(app)
    RQ(app)
    configure_uploads(app, images)
    configure_uploads(app, docs)
    CKEditor(app)
    share.init_app(app)
    moment.init_app(app)
    #jwt.init_app(app)
    sess.init_app(app)
    #whooshee.init_app(app)


    # Register Jinja template functions
    from .utils import register_template_utils
    register_template_utils(app)

    # Set up asset pipeline
    assets_env = Environment(app)
    dirs = ['assets/styles', 'assets/scripts']
    for path in dirs:
        assets_env.append_path(os.path.join(basedir, path))
    assets_env.url_expire = True

    assets_env.register('app_css', app_css)
    assets_env.register('app_js', app_js)
    assets_env.register('vendor_css', vendor_css)
    assets_env.register('vendor_js', vendor_js)

    # Configure SSL if platform supports it
    if not app.debug and not app.testing and not app.config['SSL_DISABLE']:
        from flask_sslify import SSLify
        SSLify(app)

    # Create app blueprints
    from .blueprints.public import public as public_blueprint
    app.register_blueprint(public_blueprint)

    from .blueprints.main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .blueprints.account import account as account_blueprint
    app.register_blueprint(account_blueprint, url_prefix='/account')

    from .blueprints.admin import admin as admin_blueprint
    app.register_blueprint(admin_blueprint, url_prefix='/admin')

    from .blueprints.events import events as events_blueprint
    app.register_blueprint(events_blueprint, url_prefix='/events')

    from .blueprints.products import products as products_blueprint
    app.register_blueprint(products_blueprint, url_prefix='/products')

    from .blueprints.services import services as services_blueprint
    app.register_blueprint(services_blueprint, url_prefix='/services')

    from .blueprints.promos import promos as promos_blueprint
    app.register_blueprint(promos_blueprint, url_prefix='/promos')
    
    from .blueprints.jobs import jobs as jobs_blueprint
    app.register_blueprint(jobs_blueprint, url_prefix='/jobs')

    from .blueprints.posts import post_blueprint as post_blueprint
    app.register_blueprint(post_blueprint)

    from .blueprints.seo_lagos import seo_lagos as seo_lagos_blueprint
    app.register_blueprint(seo_lagos_blueprint)


    from .blueprints.organisations import organisations as organisations_blueprint
    app.register_blueprint(organisations_blueprint, url_prefix='/organisations')

    from .blueprints.directory import directory as directory_blueprint
    app.register_blueprint(directory_blueprint, url_prefix='/directory')

    from .blueprints.sitemaps import sitemaps as sitemaps_blueprint
    app.register_blueprint(sitemaps_blueprint)

    from .blueprints.employer import employer
    app.register_blueprint(employer, url_prefix='/employer')

    #from .blueprints.crawlers import crawlers as crawlers_blueprint
    #app.register_blueprint(crawlers_blueprint)

    main_api.init_app(app)
    app.jinja_env.globals.update(json_load=json_load)

    @app.cli.command()
    def reindex():
        with app.app_context():
            whooshee.reindex()

    @app.cli.command()
    def routes():
        """'Display registered routes"""
        rules = []
        for rule in app.url_map.iter_rules():
            methods = ','.join(sorted(rule.methods))
            rules.append((rule.endpoint, methods, str(rule)))

        sort_by_rule = operator.itemgetter(2)
        for endpoint, methods, rule in sorted(rules, key=sort_by_rule):
            route = '{:50s} {:25s} {}'.format(endpoint, methods, rule)
            print(route)
        
    whooshee.init_app(app)
    recaptcha.init_app(app)
    
    return app
