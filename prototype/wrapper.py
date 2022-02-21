from flask import Flask, request, g
from app import app
import warnings

with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")

    @app.before_request
    def before_req():
        print('request intercepted before processing')
        print(request)

        # clear warnings before processing requests
        w.clear()


    @app.after_request
    def after_req(response):
        print('response intercepted after processing')
        print(response)

        # We can access captured warnings in w
        print('When processing the reqeust, the following warnings were observed')
        print(w)

        # clear warnings after response
        w.clear()
        return response

    app.run(debug=True, host='0.0.0.0')