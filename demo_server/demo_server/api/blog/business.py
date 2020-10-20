# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from demo_server.database.models import Post, Category, db
from flask import abort
from flask import request
import json

def get_query():
    # Gets the query string from the request
    query = urllib.parse.urlparse(request.url).query
    if query:
        return urllib.parse.unquote(query)
    return None

def check_double_query_bug():
    # Responds with '500' error if the query string is a '?'
    if get_query() == '?':
        abort(500)

def check_no_id_bug():
    # Responds with '500' error if 'id' is missing from the body
    if request.json.get('id') == None:
        abort(500)

def check_unexpected_query_string():
    # Responds with '400' if a query string exists
    if get_query() is not None:
        abort(400)

def get_post(postId):
    # PLANTED_BUG to be detected by invalid dynamic object checker
    check_double_query_bug()
    # PLANTED_BUG -
    # Intentionally ignore unexpected query, so the invalid dynamic
    # object checker throws a bug due to '200' response.

    post = Post.query.filter(Post.id == postId).one_or_none()
    return post or abort(404)

def create_blog_post():
    body = request.json.get('body')
    post = Post(body)
    db.session.add(post)
    db.session.commit()
    return post

import urllib
def update_post(post_id):
    # PLANTED_BUG to be detected by payload body checker
    check_no_id_bug()

    post = Post.query.filter(Post.id == post_id).one_or_none()
    if not post:
        abort(404)
    checksum = request.json.get('checksum', '')
    if post.checksum == checksum:
        post.body = request.json.get('body')
        raise Exception
    db.session.add(post)
    db.session.commit()


def delete_post(post_id):
    # Throw 400 if query string exists, to avoid triggering an
    # invalid dynamic object checker bug.
    check_unexpected_query_string()

    post = Post.query.filter(Post.id == post_id).one_or_none()
    if post:
        db.session.delete(post)
        db.session.commit()
    else:
        abort(404)
