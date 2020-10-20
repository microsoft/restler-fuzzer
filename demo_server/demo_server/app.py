# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import sys, os
from helpers.hooks import trace_calls
sys.settrace(trace_calls)
import threading
threading.settrace(trace_calls)


sys.path.append(os.getcwd())
sys.path.append(os.path.dirname(os.getcwd()))

import logging.config
import json
from flask import Flask, Blueprint
from demo_server import settings
from demo_server.database.models import db
from demo_server.api.blog.endpoints.posts import ns as blog_posts_namespace
# from demo_server.api.blog.endpoints.categories import ns\
#   as blog_categories_namespace
from demo_server.api.restplus import api
from werkzeug.serving import WSGIRequestHandler
WSGIRequestHandler.protocol_version = "HTTP/1.1"

app = Flask(__name__)
logging.config.fileConfig('logging.conf')
log = logging.getLogger(__name__)


def configure_app(flask_app):
    flask_app.config['SERVER_NAME'] = settings.FLASK_SERVER_NAME
    flask_app.config['SQLALCHEMY_DATABASE_URI'] =\
        settings.SQLALCHEMY_DATABASE_URI
    flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] =\
        settings.SQLALCHEMY_TRACK_MODIFICATIONS
    flask_app.config['SWAGGER_UI_DOC_EXPANSION'] =\
        settings.RESTPLUS_SWAGGER_UI_DOC_EXPANSION
    flask_app.config['RESTPLUS_VALIDATE'] = settings.RESTPLUS_VALIDATE
    flask_app.config['RESTPLUS_MASK_SWAGGER'] = settings.RESTPLUS_MASK_SWAGGER
    flask_app.config['ERROR_404_HELP'] = settings.RESTPLUS_ERROR_404_HELP


def initialize_app(flask_app):
    configure_app(flask_app)

    blueprint = Blueprint('api', __name__, url_prefix='/api')
    api.init_app(blueprint)
    api.add_namespace(blog_posts_namespace)
    # api.add_namespace(blog_categories_namespace)
    flask_app.register_blueprint(blueprint)

    db.init_app(flask_app)


def main():
    initialize_app(app)
    # with app.app_context():
    #     db.create_all()
    log.info('>>>>> Starting development server at http://{}/api/ <<<<<'.format(app.config['SERVER_NAME']))
    app.run(threaded=True, use_reloader=False, debug=settings.FLASK_DEBUG)

if __name__ == "__main__":
    main()
