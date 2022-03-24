from flask import Flask
import warnings
app = Flask(__name__)

@app.route('/')
def hello_world():
    # no warning here
    return 'helloworld'

@app.route('/deprecated_api')
def deprecated():
    warnings.warn("devil hides in the detail: deprecated", DeprecationWarning)
    return 'everything looks perfectly fine!!'
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')