# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

def acquire_token_no_data(data, log):
    log("Returning a valid token")
    token_lines = [
        "{'user1':{}, 'user2':{}}",
        "Authorization: valid_module_unit_test_token",
        "Authorization: shadow_unit_test_token"
    ]
    return "\n".join(token_lines)

def acquire_token_data(data, log):
    log(data)
    token_lines = [
        "{'user1':{}, 'user2':{}}",
        "Authorization: valid_module_unit_test_token",
        "Authorization: shadow_unit_test_token"
    ]
    return "\n".join(token_lines)
