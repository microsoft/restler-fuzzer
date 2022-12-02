def acquire_token(log):
    log("Returning a valid token")
    return ("{'user1':{}, 'user2':{}}\n" + "Authorization: valid_module_unit_test_token\n" + "Authorization: shadow_unit_test_token")

