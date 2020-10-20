# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from flask_restplus import fields
from demo_server.api.restplus import api


blog_post_public = api.model('Blog post public', {
    'id': fields.Integer(readOnly=True,
                         description='The unique identifier of a blog post'),
    'body': fields.String(required=True, description='Article content'),
})

blog_post = api.model('Blog post', {
    'id': fields.Integer(readOnly=True,
                         description='The unique identifier of a blog post'),
    'checksum': fields.String(required=False,
                         description='The sha1 checksum of the body'),
    'body': fields.String(required=True, description='Article content'),
})

pagination = api.model('A page of results', {
    'per_page': fields.Integer(description='Number of items per page of results'),
    'page': fields.Integer(description='Number of this page of results'),
    'total': fields.Integer(description='Total number of results'),
})

page_of_blog_posts = api.inherit('Page of blog posts', pagination, {
    'items': fields.List(fields.Nested(blog_post_public))
})

category = api.model('Blog category', {
    'id': fields.Integer(readOnly=True, description='The unique identifier of a blog category'),
    'name': fields.String(required=True, description='Category name'),
})

category_with_posts = api.inherit('Blog category with posts', category, {
    'posts': fields.List(fields.Nested(blog_post))
})
