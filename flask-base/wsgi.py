#!/usr/bin/python3
import sys
import logging
logging.basicConfig(stream=sys.stderr)
sys.path.insert(0,"/home/ubuntu/flaskapp/flask-base/")

from manage import app as application

if __name__ == "__main__":
    application.run()



