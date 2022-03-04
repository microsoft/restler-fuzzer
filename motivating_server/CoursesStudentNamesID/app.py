from flask import Flask, jsonify, request, abort

app = Flask(__name__)

@app.route("/get_class_names")
def get_class_names():
    classes = ['compiler', 'physics', 'automated_testing']
    return jsonify(classes)

# /get_students_and_ids?class_name=compiler
@app.route("/get_students_and_ids")
def get_students_and_ids():
    class_name = request.args.get('class_name', '')
    if class_name == 'compiler':
        students_and_ids = [('Aatrox', '1111111111'), ('Ahri', '22222222'), ('Akali', '333333333')]
        return jsonify(students_and_ids)
    elif class_name == 'physics':
        students_and_ids = [('Elise', '24253245'), ('Ekko', '23645126'), ('Jax', '7643325345')]
        return jsonify(students_and_ids)
    elif class_name == 'automated_testing':
        # Notice there's a missing comma in the list below
        students_and_ids = [('Sett', '425145'), ('Urgot', '52342543')('Ziggs', '5722145')]
        return jsonify(students_and_ids)
    else:
        # Not found
        abort(404)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=11111)