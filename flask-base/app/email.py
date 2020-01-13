import os

from flask import render_template
from flask_mail import Message
from flask_mail import Mail

from app import create_app

# from app import mail
mail = Mail()

env_file = "/home/ubuntu/flaskapp/flask-base/config.env"
if os.path.exists(env_file):
    print('Importing environment from .env file')
    for line in open(env_file):
        var = line.strip().split('=')
        if len(var) == 2:
            os.environ[var[0]] = var[1].replace("\"", "")


def send_email(recipient, subject, template, **kwargs):
    app = create_app(os.getenv('FLASK_CONFIG') or 'default')
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER') or 'smtp.sendgrid.net'
    app.config['MAIL_PORT'] = os.environ.get('MAIL_PORT') or 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USE_SSL'] = False
    app.config['SSL_DISABLE'] = os.environ.get('SSL_DISABLE') or False
    app.config['MAIL_AUTH_TYPE'] = 'sendgrid'
    app.config['SENDGRID_API_KEY'] = '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'
    app.config['MAIL_USERNAME'] = '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'
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = 'support@networked.ng'
    app.config['MAIL_DEFAULT_SENDER_NAME'] = os.environ.get('MAIL_DEFAULT_SENDER_NAME') or 'Networked.ng'
    app.config['EMAIL_SENDER'] = app.config['MAIL_DEFAULT_SENDER']
    app.config['MAIL_SUPPRESS_SEND'] = False
    mail.init_app(app)
    f = open("/home/ubuntu/flaskapp/log", 'w')
    f.write(str(app.config))
    f.close()
    with app.app_context():
        if app.config['MAIL_AUTH_TYPE'] == 'sendgrid':
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail as SendGridMail
            message = SendGridMail(
                from_email=app.config['MAIL_DEFAULT_SENDER'],
                to_emails=recipient,
                subject=app.config['EMAIL_SUBJECT_PREFIX'] + ' ' + subject,
                html_content=render_template(template + '.html', **kwargs))
            try:
                sg = SendGridAPIClient(app.config['SENDGRID_API_KEY'])
                response = sg.send(message)
                print(response.status_code)
                print(response.body)
                print(response.headers)
            except Exception as e:
                print(e.message)
        else:
            msg = Message(
                app.config['EMAIL_SUBJECT_PREFIX'] + ' ' + subject,
                sender=(app.config['MAIL_DEFAULT_SENDER_NAME'], app.config['EMAIL_SENDER']),
                recipients=[recipient])
            msg.body = render_template(template + '.txt', **kwargs)
            msg.html = render_template(template + '.html', **kwargs)
            open("/home/ubuntu/flaskapp/log", 'w').write(str(app.config))
            mail.send(msg)
