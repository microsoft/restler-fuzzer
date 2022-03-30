# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
import traceback

# Workaround for import error
#    ImportError: cannot import name 'cached_property' from 'werkzeug'
try:
    from flask_restplus import Api
except ImportError:
    import werkzeug, flask.scaffold
    werkzeug.cached_property = werkzeug.utils.cached_property
    flask.helpers._endpoint_from_view_func = flask.scaffold._endpoint_from_view_func
    from flask_restplus import Api
from demo_server import settings
from sqlalchemy.orm.exc import NoResultFound

log = logging.getLogger(__name__)

api = Api(version='1.0', title='My Blog API',
          description='A simple demonstration of a Flask RestPlus powered API')


@api.errorhandler
def default_error_handler(e):
    message = 'An unhandled exception occurred.'
    log.exception(message)

    if not settings.FLASK_DEBUG:
        return {'message': message}, 500


@api.errorhandler(NoResultFound)
def database_not_found_error_handler(e):
    log.warning(traceback.format_exc())
    return {'message': 'A database result was required but none was found.'}, 404
