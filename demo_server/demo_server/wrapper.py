from distutils.log import warn
from logging import warning
from pydoc import resolve
from flask import Flask, request, g
from app import app, main
import warnings
from pandas.core.common import SettingWithCopyWarning

warning_map = {
    "Warning": 289,
    "UserWarning": 290,
    "DeprecationWarning": 291,
    "SyntaxWarning": 292,
    "RuntimeWarning": 293,
    "FutureWarning": 294,
    "PendingDeprecationWarning": 295,
    "ImportWarning": 296,
    "UnicodeWarning": 297,
    "BytesWarning": 298,
    "ResourceWarning": 299
}

with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")

    @app.before_request
    def before_req():
        # print('request intercepted before processing')
        # print(request)

        # clear warnings before processing requests
        w.clear()

    @app.after_request
    def after_req(response):
        print('response intercepted after processing')
        print(response)

        # We can access captured warnings in w
        print('When processing the reqeust, the following warnings were observed')
        print(w)

        if len(w) > 0:
            # Only return the first warning code...
            warning_category = w[0].category.__name__
            status_code = warning_map.get(warning_category, warning_map["Warning"])
            response.status_code = status_code

            # Concat message
            warning_msg = ''
            for warning in w:
                warning_msg += str(warning.message) + '\n'
            print(warning_msg)

        print('response after warning check')
        print(response)
        # clear warnings after response
        w.clear()
        return response

    main()