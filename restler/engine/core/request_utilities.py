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

from engine.errors import ResponseParsingException
from engine.errors import TransportLayerException
from restler_settings import Settings
import engine.primitives as primitives
import engine.dependencies as dependencies
from engine.transport_layer.response import HttpResponse
from engine.transport_layer.response import RESTLER_BUG_CODES
from engine.transport_layer.messaging import UTF8
from engine.transport_layer.messaging import HttpSock

last_refresh = 0
NO_TOKEN_SPECIFIED = 'NO-TOKEN-SPECIFIED'
latest_token_value = NO_TOKEN_SPECIFIED
NO_SHADOW_TOKEN_SPECIFIED = 'NO-SHADOW-TOKEN-SPECIFIED'
latest_shadow_token_value = NO_SHADOW_TOKEN_SPECIFIED

HOST_PREFIX = 'Host: '

class EmptyTokenException(Exception):
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

def execute_token_refresh_cmd(cmd):
    """ Forks a subprocess to execute @param cmd to refresh token.

    @param cmd: The user-provided command to refresh the token.
    @type  cmd: Str

    @return: The result of the command
    @rtype : Str

    """
    global latest_token_value, latest_shadow_token_value
    _RAW_LOGGING(f"Will refresh token: {cmd}")

    MAX_RETRIES = 5
    RETRY_SLEEP_TIME_SEC = 2
    ERROR_VAL_STR = 'ERROR\r\n'
    retry_count = 0
    while retry_count < MAX_RETRIES:
        try:
            if sys.platform.startswith('win'):
                cmd_result = subprocess.getoutput(str(cmd).split(' '))
            else:
                cmd_result = subprocess.getoutput([cmd])

            _, latest_token_value, latest_shadow_token_value = parse_authentication_tokens(cmd_result)
            _RAW_LOGGING(f"New value: {cmd_result}")
            break
        except subprocess.CalledProcessError:
            error_str = f"Authentication failed when refreshing token:\n\nCommand that failed: \n{cmd}"
            print(f'\n{error_str}')
            latest_token_value = ERROR_VAL_STR
            latest_shadow_token_value = ERROR_VAL_STR
            _RAW_LOGGING(error_str)
            retry_count = retry_count + 1
            time.sleep(RETRY_SLEEP_TIME_SEC)
        except EmptyTokenException:
            error_str = "Error: Authentication token was empty."
            print(error_str)
            _RAW_LOGGING(error_str)
            sys.exit(-1)
        except Exception as error:
            error_str = f"Exception refreshing token with cmd {cmd}.  Error: {error}"
            print(error_str)
            _RAW_LOGGING(error_str)
            sys.exit(-1)
    else:
        _RAW_LOGGING(f"\nMaximum number of retries ({MAX_RETRIES}) exceeded. Exiting program.")
        sys.exit(-1)

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
            writer_variable = values[i][2]

            if quoted:
                values[i] = f'"{val}"'
            else:
                values[i] = val
            ## Check if a writer is present.  If so, assign the value generated above
            ## to the dynamic object variable.
            if writer_variable is not None:
                dependencies.set_variable(writer_variable, values[i])

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

            ## Check if a writer is present.  If so, assign the value generated above
            ## to the dynamic object variable.
            if writer_variable is not None:
                dependencies.set_variable(writer_variable, values[i])
        elif isinstance(values[i], types.FunctionType)\
        and values[i] == primitives.restler_refreshable_authentication_token:
            token_dict = candidate_values_pool.get_candidate_values(
                primitives.REFRESHABLE_AUTHENTICATION_TOKEN
            )
            if not isinstance(token_dict, dict):
                raise Exception("Refreshable token was not specified as a setting, but a request was expecting it.")
            token_refresh_interval = token_dict['token_refresh_interval']
            token_refresh_cmd = token_dict['token_refresh_cmd']
            if int(time.time()) - last_refresh > token_refresh_interval:
                execute_token_refresh_cmd(token_refresh_cmd)
                last_refresh = int(time.time())
                #print("-{}-\n-{}-".format(repr(latest_token_value),
                #                          repr(latest_shadow_token_value)))
            values[i] = latest_token_value

    return values

def send_request_data(rendered_data):
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
    while num_retries < MAX_RETRIES:
        try:
            # Establish connection to server
            sock = HttpSock(Settings().connection_settings)
        except TransportLayerException as error:
            _RAW_LOGGING(str(error))
            return HttpResponse()

        # Send the request and receive the response
        success, response = sock.sendRecv(rendered_data,
            Settings().max_request_execution_time)

        status_code = response.status_code

        if status_code and status_code in RESTLER_BUG_CODES:
            return response

        if not success or not status_code:
            _RAW_LOGGING(response.to_str)
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
                # For backwards compatibility, check if the parser accepts named arguments.
                # If not, this is an older grammar that only supports a json body as the argument
                import inspect
                args, varargs, varkw, defaults = inspect.getargspec(parser)

                if varkw=='kwargs':
                    parser(response.json_body, headers=response.headers_dict)
                else:
                    parser(response.json_body)
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
            _RAW_LOGGING(str(error))

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
