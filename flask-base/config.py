import os
import sys
from sqlalchemy import create_engine

from raygun4py.middleware import flask as flask_raygun

PYTHON_VERSION = sys.version_info[0]
if PYTHON_VERSION == 3:
    import urllib.parse
else:
    import urlparse

basedir = os.path.abspath(os.path.dirname(__file__))

#env_file = "/home/ubuntu/flaskapp/flask-base/config.env"
if os.path.exists('config.env'):
    print('Importing environment from .env file')
    for line in open('config.env'):
        var = line.strip().split('=')
        if len(var) == 2:
            os.environ[var[0]] = var[1].replace("\"", "")

class Config:
    APP_NAME = os.environ.get('APP_NAME') or 'Networked.ng'

    if os.environ.get('SECRET_KEY'):
        SECRET_KEY = os.environ.get('SECRET_KEY')
    else:
        SECRET_KEY = 'SECRET_KEY_ENV_VAR_NOT_SET'
        print('SECRET KEY ENV VAR NOT SET! SHOULD NOT SEE IN PRODUCTION')
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    

    # Email
    MAIL_SERVER='smtp.sendgrid.net'
    MAIL_DEFAULT_SENDER='Support@networked.ng'
    MAIL_USE_TLS=True
    MAIL_USE_SSL=False
    SSL_DISABLE=False
    EMAIL_SUBJECT_PREFIX='Networked.ng'
    MAIL_DEFAULT_SENDER_NAME='Networked.ng'
    MAIL_PORT=587
    MAIL_USERNAME='apikey'
    MAIL_PASSWORD='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'
    MAIL_SUPPRESS_SEND=False
    MAIL_DEBUG=False 
    # Analytics
    GOOGLE_ANALYTICS_ID = os.environ.get('GOOGLE_ANALYTICS_ID') or 'UA-154005901-1'
    SEGMENT_API_KEY = os.environ.get('SEGMENT_API_KEY') or 'fmBge3EWLw3KPoi1rdzeUyz9Yxzc6bjo'

    # Admin account
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'PasswordAnicHANGEmE12309JA'
    ADMIN_MOBILE_PHONE='07548129001'
    ADMIN_AREA_CODE='+44'
    ADMIN_EMAIL = os.environ.get(
        'ADMIN_EMAIL') or 'aniekanokono@gmail.com'
    EMAIL_SUBJECT_PREFIX = '[{}]'.format(APP_NAME)
    EMAIL_SENDER = '{app_name} Admin <{email}>'.format(
        app_name=APP_NAME, email=MAIL_USERNAME)

    REDIS_URL = os.getenv('REDISTOGO_URL') or 'http://localhost:6379'

    RAYGUN_APIKEY = os.environ.get('RAYGUN_APIKEY')
    
    ## AWS S3 Bucket
    #AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID') or 'AKIAJNQ5ECCZMGUNDJTA'
    #AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY') or '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'
    #ACL = 'public-read'
    #FLASKS3_BUCKET_NAME = os.environ.get('FLASKS3_BUCKET_NAME') or 'networkedng2'
    #FLASKS3_REGION = os.environ.get('FLASKS3_REGION') or 'us-east-1'

    # Parse the REDIS_URL to set RQ config variables
    if PYTHON_VERSION == 3:
        urllib.parse.uses_netloc.append('redis')
        url = urllib.parse.urlparse(REDIS_URL)
    else:
        urlparse.uses_netloc.append('redis')
        url = urlparse.urlparse(REDIS_URL)

    RQ_DEFAULT_HOST = url.hostname
    RQ_DEFAULT_PORT = url.port
    RQ_DEFAULT_PASSWORD = url.password
    RQ_DEFAULT_DB = 0

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True
    ASSETS_DEBUG = True
    ###seems like the app doesn't connect to config.env to get Database URI
    ### so I am commenting it out. Maybe it can be re-enabled once a solution is found
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
                              'postgresql+psycopg2://postgres:ub_dev+WhenToChangePAssW0rd_pst_pg_db@localhost:5432/postgres'

    @classmethod
    def init_app(cls, app):
        print('THIS APP IS IN DEBUG MODE. \
                YOU SHOULD NOT SEE THIS IN PRODUCTION.')


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, 'data-test.sqlite')
    WTF_CSRF_ENABLED = False

    @classmethod
    def init_app(cls, app):
        print('THIS APP IS IN TESTING MODE.  \
                YOU SHOULD NOT SEE THIS IN PRODUCTION.')


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'postgresql+psycopg2://postgres:ub_dev+WhenToChangePAssW0rd_pst_pg_db@localhost:5432/postgres'    
    SSL_DISABLE = (os.environ.get('SSL_DISABLE') or 'True') == 'True'

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        assert os.environ.get('SECRET_KEY'), 'SECRET_KEY IS NOT SET!'

        flask_raygun.Provider(app, app.config['RAYGUN_APIKEY']).attach()


class HerokuConfig(ProductionConfig):
    @classmethod
    def init_app(cls, app):
        ProductionConfig.init_app(app)

        # Handle proxy server headers
        from werkzeug.contrib.fixers import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app)
        import logging
        from logging.handlers import SysLogHandler
        syslog_handler = SysLogHandler()
        syslog_handler.setLevel(logging.WARNING)
        app.logger.addHandler(syslog_handler)


class UnixConfig(ProductionConfig):
    @classmethod
    def init_app(cls, app):
        ProductionConfig.init_app(app)

        # Log to syslog
        import logging
        from logging.handlers import SysLogHandler
        syslog_handler = SysLogHandler()
        syslog_handler.setLevel(logging.WARNING)
        app.logger.addHandler(syslog_handler)


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
    'heroku': HerokuConfig,
    'unix': UnixConfig
}
