# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# The examples in this file come from the Flask-SQLAlchemy documentation
# For more information take a look at:
# http://flask-sqlalchemy.pocoo.org/2.1/quickstart/#simple-relationships
import os,binascii

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text)
    checksum = db.Column(db.Text)

    def __init__(self, body):
        self.body = body
        self.checksum =  binascii.b2a_hex(os.urandom(100))[:5]

class Category(db.Model):
    categoryId = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '<Category %r>' % self.name
