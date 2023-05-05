# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Collection of Request utility functions """
import hashlib
import time
import subprocess
import sys
import ast
import uuid
import types
import threading
import os

from engine.errors import ResponseParsingException
from engine.errors import TransportLayerException
from restler_settings import Settings
from restler_settings import TokenAuthMethod
import engine.primitives as primitives
import engine.dependencies as dependencies
from engine.transport_layer.response import HttpResponse
from engine.transport_layer.response import RESTLER_BUG_CODES
from engine.transport_layer.messaging import UTF8
from engine.transport_layer.messaging import HttpSock
from engine.core.retry_handler import RetryHandler
from utils import import_utilities


last_refresh = 0
NO_TOKEN_SPECIFIED = 'NO-TOKEN-SPECIFIED\r\n'
latest_token_value = NO_TOKEN_SPECIFIED
NO_SHADOW_TOKEN_SPECIFIED = 'NO-SHADOW-TOKEN-SPECIFIED\r\n'
latest_shadow_token_value = NO_SHADOW_TOKEN_SPECIFIED

HOST_PREFIX = 'Host: '

threadLocal = threading.local()

class EmptyTokenException(Exception):
    pass

class InvalidTokenAuthMethodException(Exception):
    pass

def get_latest_token_value():
    global latest_token_value
    return latest_token_value


def str_to_hex_def(val_str):
    """ Creates a hex definition from a specified string

    @param val_str: The string to convert to a hex definition
    @type  val_str: Str

    @return: The hex definition of the string
    @rtype : Int

    """
    return hashlib.sha1(val_str.encode(UTF8)).hexdigest()


def execute_token_refresh(token_dict):
    """ Executes token refresh based on parameters in token_dict.
    @param token_dict: Dictionary containing data required to fetch token
    @type: token_dict: Dict

    @return: None. Updates global latest_token_value and latest_shadow_token_value
    @type: None
    """
    global latest_token_value, latest_shadow_token_value
    ERROR_VAL_STR = 'ERROR\r\n'
    result = None
    token_auth_method = token_dict["token_auth_method"]

    retry_handler = RetryHandler()

    while retry_handler.can_retry():
        try:
            if token_auth_method == TokenAuthMethod.LOCATION:
                result = execute_location_token_refresh(
                    token_dict["token_location"])
            elif token_auth_method == TokenAuthMethod.CMD:
                result = execute_token_refresh_cmd(
                    token_dict["token_refresh_cmd"])
            elif token_auth_method == TokenAuthMethod.MODULE:
                result = execute_token_refresh_module(
                    token_dict["token_module_file"],
                    token_dict["token_module_function"],
                    token_dict["token_module_data"])

            _, latest_token_value, latest_shadow_token_value = parse_authentication_tokens(
                result)
            break
        except EmptyTokenException:
            error_str = "Error: Authentication token was empty."
            print(error_str)
            _RAW_LOGGING(error_str)
            sys.exit(-1)
        except InvalidTokenAuthMethodException as exc:
            error_str = f"Error: Invalid token authentication mechanism. \n Failed with {exc}"
            print(error_str)
            _RAW_LOGGING(error_str)
            sys.exit(-1)
        except Exception as error:
            error_str = f"Authentication failed when refreshing token:\n\nUsing Token authentication method: \n{token_auth_method} \n with error {error}"
            print(f'\n{error_str}')
            latest_token_value = ERROR_VAL_STR
            latest_shadow_token_value = ERROR_VAL_STR
            _RAW_LOGGING(error_str)
            retry_handler.wait_for_next_retry()

def execute_location_token_refresh(location):
    """ Executes token refresh by attempting to read a token from a file path.
    @param location: File path to a text file containing token
    @type: location: string (filepath)

    @return: token
    @type: Str:
    """
    try:
        with open(location,"r") as f:
            token_result = f.read()
            return token_result
    except FileNotFoundError:
        error_str = f"Could not find token file at {location}. Please ensure that you've passed a valid path"
        _RAW_LOGGING(error_str)
        raise InvalidTokenAuthMethodException(error_str)

def execute_token_refresh_module(module_path, function, data):
    """ Executes token refresh by attempting to execute a user provided auth module
    @param: module_path: Path to auth module
    @type:  module_path: Str (filepath)

    @param: function: function to call in auth module to retrieve a token
    @type:  function: Str

    @param: data: Data to pass to authentication module
    @type:  data: Dict

    @return: token
    @type: string:
    """
    try:
        token_refresh_function = import_utilities.import_attr(module_path, function)
        token_result = token_refresh_function(data, _AUTH_LOGGING)
        return token_result
    except FileNotFoundError:
        error_str = f"Could not find token module file at {module_path}. Please ensure that you've passed a valid path"
        _RAW_LOGGING(error_str)
        raise InvalidTokenAuthMethodException(error_str)
    except AttributeError:
        error_str = f"Could not execute token refresh function {function} in module {module_path}. Please ensure that you've passed a valid function"
        _RAW_LOGGING(error_str)
        raise InvalidTokenAuthMethodException(error_str)


def execute_token_refresh_cmd(cmd):
    """ Forks a subprocess to execute @param cmd to refresh token.

    @param cmd: The user-provided command to refresh the token.
    @type  cmd: Str

    @return: The result of the command
    @rtype : Str

    """
    global latest_token_value, latest_shadow_token_value
    _RAW_LOGGING(f"Will refresh token: {cmd}")
    if sys.platform.startswith('win'):
        cmd_result = subprocess.getoutput(str(cmd).split(' '))
    else:
        cmd_result = subprocess.getoutput([cmd])
    return cmd_result


def parse_authentication_tokens(cmd_result):
    """ Parses the output @param cmd_result from token scripts to refresh tokens.

    Format:
    {u'app1': {}, u'app2':{}}  // Metadata
    ApiTokenTag: 9A            // Auth header for application 1
    ApiTokenTag: ZQ            // Auth header for application 2

    Format for multiple authenication headers per request:
    {u'app1': {}, u'app2':{}}  // Metadata
    ApiTokenTag: 9A            // Auth header for application 1
    ApiTokenTag2: E8           // Auth header for application 1
    ---                        // Delimiter
    ApiTokenTag: ZQ            // Auth header for application 2
    ApiTokenTag2: UI           // Auth header for application 2

    @param cmd_result: The result of the user-provided command to refresh the token.
    @type  cmd_result: Str

    @return: Metadata, token values and shadow token values
    @rtype : Tuple[Dict, Str, Str]

    """
    token_value = NO_TOKEN_SPECIFIED
    shadow_token_value = NO_SHADOW_TOKEN_SPECIFIED
    DELIMITER = '---'

    metadata = cmd_result.split("\n")[0]
    if not metadata:
        raise EmptyTokenException
    metadata = ast.literal_eval(metadata)

    n_apps = len(metadata.keys())
    tokens = [line.strip() for line in cmd_result.strip().split('\n')[1:]]

    if n_apps == 1 and DELIMITER not in tokens:
        token_value = '\r\n'.join(tokens) + '\r\n'
    elif n_apps == 2 and DELIMITER not in tokens:
        token_value = tokens[0] + '\r\n'
        shadow_token_value = tokens[1] + '\r\n'
    else:
        token_value = '\r\n'.join(tokens[:tokens.index(DELIMITER)]) + '\r\n'
        if n_apps == 2:
            shadow_token_value = '\r\n'.join(tokens[tokens.index(DELIMITER)+1:]) + '\r\n'

    if not latest_token_value:
        raise EmptyTokenException

    return metadata, token_value, shadow_token_value

def replace_auth_token(data, replace_str):
    """ Replaces any authentication tokens from a data string with a
    specified @replace_str and returns the new data

    @param data: The data to replace the auth token in
    @type  data: Str
    @param replace_str: The string to replace the token with
    @type  replace_str: Str

    @return: The data with the token(s) replaced
    @rtype : Str

    """
    if data:
        if latest_token_value:
            data = data.replace(latest_token_value.strip('\r\n'), replace_str)
        if latest_shadow_token_value:
            data = data.replace(latest_shadow_token_value.strip('\r\n'), replace_str)
    return data


def resolve_dynamic_primitives(values, candidate_values_pool):
    """ Dynamic primitives (i.e., uuid4) must be filled with a new value
        each time the request is rendered.

    @param values: List of primitive type payloads. Each item is going to
                    be a string, except for dynamic primitives that will be
                    fuction pointer and will be substituted with fresh value
                    within this routine.
    @type values: List
    @param candidate_values_pool: The pool of values for primitive types.
    @type  candidate_values_pool: Dict

    @return: List of string of primitive type payloads for which any dynamic
                primitive (e.g., uuid4) with be substituted with a fresh and
                unique value.
            Note: this function will also update the values in place as a side effect.
    @rtype : List

    """
    global last_refresh, latest_token_value, latest_shadow_token_value
    from utils import logger
    # There should only be one uuid4_suffix in the request for a given name
    current_uuid_suffixes = {}
    for i in range(len(values)):
        # Look for function pointers assigned to dynamic primitives
        if isinstance(values[i], tuple)\
        and values[i][0] == primitives.restler_fuzzable_uuid4:
            val = f'{uuid.uuid4()}'
            quoted = values[i][1]
            (writer_variable, is_quoted) = values[i][2]

            if quoted:
                values[i] = f'"{val}"'
            else:
                values[i] = val

        elif isinstance(values[i], tuple)\
        and values[i][0] == primitives.CUSTOM_PAYLOAD_UUID4_SUFFIX:
            current_uuid_type_name = values[i][1]
            writer_variable = values[i][5]
            quoted = False
            if len(current_uuid_type_name) >= 2 and current_uuid_type_name[0] == '"' and current_uuid_type_name[-1] == '"':
                quoted = True
                current_uuid_type_name = current_uuid_type_name.strip('"')
            if current_uuid_type_name not in current_uuid_suffixes:
                current_uuid_suffixes[current_uuid_type_name] =\
                    current_uuid_type_name + uuid.uuid4().hex[:10]
            if quoted:
                values[i] = f'"{current_uuid_suffixes[current_uuid_type_name]}"'
            else:
                values[i] = current_uuid_suffixes[current_uuid_type_name]

        elif isinstance(values[i], tuple)\
        and isinstance(values[i][0], types.GeneratorType):
            # Handle the case of a custom value generator.
            # The value needs to be quoted, and if a writer variable is present, it needs to be
            # set (similar to restler_fuzzable_uuid4)
            value_generator = values[i][0]
            val = str(next(value_generator))
            quoted = values[i][1]
            (writer_variable, is_quoted) = values[i][2]
            if quoted:
                values[i] = f'"{val}"'
            else:
                values[i] = val

        elif isinstance(values[i], types.FunctionType)\
        and values[i] == primitives.restler_refreshable_authentication_token:
            token_dict = candidate_values_pool.get_candidate_values(
                primitives.REFRESHABLE_AUTHENTICATION_TOKEN
            )
            if not isinstance(token_dict, dict):
                raise Exception("Refreshable token was not specified as a setting, but a request was expecting it.")
            if "token_auth_method" in token_dict and token_dict["token_auth_method"]:
                token_refresh_interval = token_dict['token_refresh_interval']
                if int(time.time()) - last_refresh > token_refresh_interval:
                    execute_token_refresh(token_dict)
                    last_refresh = int(time.time())
                    #print("-{}-\n-{}-".format(repr(latest_token_value),
                    #                          repr(latest_shadow_token_value)))
                values[i] = latest_token_value
            else:
                # If the dictionary is empty, there is no authentication specified.
                # Simply return the empty string.
                values[i] = ""

    return values

def send_request_data(rendered_data, req_timeout_sec=None, reconnect=None, http_sock=None):
    """ Helper that sends a request's rendered data to the server
    and parses its response.

    @param rendered_data: The data to send to the server
    @type  rendered_data: Str

    @return: The response from the server
    @rtype : HttpResponse

    """
    # Set max retries and retry sleep time to be used in case
    # a status code from the retry list is encountered.
    MAX_RETRIES = 5
    custom_retry_codes = Settings().custom_retry_codes
    custom_retry_text = Settings().custom_retry_text
    custom_retry_interval_sec = Settings().custom_retry_interval_sec

    RETRY_SLEEP_SEC = 5 if custom_retry_interval_sec is None else custom_retry_interval_sec
    RETRY_CODES = ['429'] if custom_retry_codes is None else custom_retry_codes
    # Note: the default text below is specific to Azure cloud services
    # Because 409s were previously unconditionally re-tries, it is being added here
    # as a constant for backwards compatibility.  In the future, this should move into
    # a separate settings file.
    RETRY_TEXT = ['AnotherOperationInProgress'] if custom_retry_text is None else custom_retry_text
    num_retries = 0

    try:
        main_sock = threadLocal.main_sock
    except AttributeError:
        # Socket not yet initialized.
        threadLocal.main_sock = HttpSock(Settings().connection_settings)
        main_sock = threadLocal.main_sock

    while num_retries < MAX_RETRIES:
        # Send the request and receive the response
        reconnect = Settings().reconnect_on_every_request if reconnect is None else reconnect
        # The connection may have been closed as part of throttling, so re-connect when re-trying.
        if num_retries > 0:
            reconnect = True
        req_timeout_sec = Settings().max_request_execution_time if req_timeout_sec is None else req_timeout_sec
        success, response = main_sock.sendRecv(rendered_data,
            req_timeout_sec, reconnect=reconnect)

        status_code = response.status_code

        if status_code and status_code in RESTLER_BUG_CODES:
            return response

        if not success or (status_code is None):
            _RAW_LOGGING(f"Failed to receive response.  Success: {success}, status: {status_code}, Response: {response.to_str}")
            return HttpResponse()

        # Check whether a custom re-try text was provided.
        response_contains_retry_text = False
        for text in RETRY_TEXT:
            if text in response.to_str:
                response_contains_retry_text = True
                break

        if status_code in RETRY_CODES or response_contains_retry_text:
            num_retries += 1
            if num_retries < MAX_RETRIES:
                time.sleep(RETRY_SLEEP_SEC)
                _RAW_LOGGING("Retrying request")
                continue
            else:
                return response

        return response

def call_response_parser(parser, response, request=None, responses=None):
    """ Calls a specified parser on a response

    @param parser: The parser function to calls
    @type  parser: Func
    @param response: The response to parse
    @type  response: HttpResponse
    @param request: The request whose parser is being called
    @type  request: Request (None ok)
    @param responses: A list of responses
                     This parameter is used if the response is not specified
    @type  responses: List[HttpResponse]

    @return False if there was a parser exception
    @rtype  Boolean

    """
    from utils.logger import write_to_main
    # parse response and set dependent variables (for garbage collector)

    if responses is None:
        responses = []
        responses.append(response)

    for response in responses:
        try:
            if parser:
                parser(response.json_body, headers=response.headers_dict)
                # Print a diagnostic message if some dynamic objects were not set.
                # The parser only fails if all of the objects were not set.
                if request:
                    for producer in request.produces:
                        if dependencies.get_variable(producer) == 'None':
                            err_str = f'Failed to parse {producer}; it is now set to None.'
                            write_to_main(err_str)
                            _RAW_LOGGING(err_str)
                return True
        except (ResponseParsingException, AttributeError) as error:
            _RAW_LOGGING(f"Parser exception: {str(error)}.")

    return False

def get_hostname_from_line(line):
    """ Gets the hostname from a request definition's Host: line

    @param line: The line to extract the hostname
    @type  line: Str
    @return: The hostname or None if not found
    @rtype : Str or None

    """
    try:
        return line.split(HOST_PREFIX, 1)[1].split('\r\n', 1)[0]
    except:
        return None

def _RAW_LOGGING(log_str):
    """ Wrapper for the raw network logging function.
    Necessary to avoid circular dependency with logging.

    @param log_str: The string to log
    @type  log_str: Str

    @return: None
    @rtype : None

    """
    from utils.logger import raw_network_logging as RAW_LOGGING
    RAW_LOGGING(log_str)

def _AUTH_LOGGING(log_str):
    from utils.logger import auth_logging as AUTH_LOGGING
    AUTH_LOGGING(log_str)