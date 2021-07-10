# pull official base image
FROM python:3.8.11-slim-buster
RUN python3 -m venv /opt/venv


# set work directory
WORKDIR /usr/src/app





# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install dependencies
COPY ./requirementss.txt /usr/src/app/requirementss.txt
RUN . /opt/venv/bin/activate && pip install -r requirementss.txt


# copy project
COPY . .
 

CMD . /opt/venv/bin/activate && exec gunicorn --bind=unix:/workspace/networker/flaskapp/src/flask-base/flaskapp.sock --workers 4 wsgi:application && python manage.py run_worker
