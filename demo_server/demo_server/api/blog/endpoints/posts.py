# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging

from flask import request
from flask_restplus import Resource
from demo_server.api.blog.business import create_blog_post, update_post, delete_post, get_post
from demo_server.api.blog.serializers import blog_post, blog_post_public,\
    page_of_blog_posts
from demo_server.api.blog.parsers import pagination_arguments
from demo_server.api.restplus import api
from demo_server.database.models import Post

log = logging.getLogger(__name__)

ns = api.namespace('blog/posts', description='Operations related to blog posts')


@ns.route('')
class PostsCollection(Resource):

    @api.expect(pagination_arguments)
    @api.marshal_with(page_of_blog_posts)
    def get(self):
        """
        Returns a list of blog posts.
        """
        args = pagination_arguments.parse_args(request)
        page = args.get('page', 1)
        per_page = args.get('per_page', 1)
        posts_query = Post.query
        posts_page = posts_query.paginate(page, per_page)

        return posts_page

    @api.expect(blog_post_public)
    @api.marshal_with(blog_post_public)
    def post(self):
        """
        Creates a new blog post.
        """
        post = create_blog_post()
        return post, 201


@ns.route('/<int:postId>')
@api.response(404, 'Post not found.')
@api.response(201, 'Post found.')
class PostItem(Resource):

    @api.marshal_with(blog_post)
    def get(self, postId):
        """
        Returns a blog post with matching \"postId\".
        """
        return get_post(postId)

    @api.expect(blog_post)
    @api.response(204, 'Post successfully updated.')
    def put(self, postId):
        """
        Updates a blog post with matching \"postId\" and \"checksum\".
        """
        update_post(postId)

    @api.response(204, 'Post successfully deleted.')
    def delete(self, postId):
        """
        Deletes a blog post with matching \"postId\".
        """

        delete_post(postId)


ns = api.namespace('/', description='Operations related to blog categories')
@ns.route('/doc')
class Doc(Resource):

    def get(self):
        """
        Returns list of blog categories.
        """
        return api.__schema__
