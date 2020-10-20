# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from flask_restplus import reqparse

pagination_arguments = reqparse.RequestParser()
pagination_arguments.add_argument('per_page', type=int, required=False, choices=[2, 10, 50],
                                  default=10, help='Results per page {error_msg}')
pagination_arguments.add_argument('page', type=int, required=False, default=1,
                                  help='Page number')
