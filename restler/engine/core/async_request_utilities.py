# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import time
import json

import engine.core.request_utilities as request_utilities
from restler_settings import Settings

def get_polling_request(response):
    """ Helper that exctracts the URL from an azure-async-operation response
    and then creates and returns a valid GET request for it.

    @param response: The response to parse for the URL
    @type  response: Str

    @return: Tuple containing the rendered data for the GET request
             and a boolean that indicates whether or not to expect
             the parsable data to be included in the polling request.
    @rtype : Tuple(str, bool)

    """
    from utils.logger import raw_network_logging as RAW_LOGGING

    data_in_poll_response = False
    if not response or not response.to_str:
        return None, False
    # In our experience with Azure cloud services, there have been two types of indications for async resource creation.
    # One that contains "Azure-AsyncOperation:<polling-url>" in the response and one that contains "Location:<polling-url>"
    # in the response.
    # - For responses that contain only the Azure-AsyncOperation type, the response from the GET request sent
    #   to the supplied polling-URL returns only a "status" that says InProgress, Succeeded, or Failed. Any additional,
    #   parsable, data about the resource must be retrieved by creating and sending a GET request to the original URI.
    # - For responses that contain the Location: type, the GET request sent to the provided polling-url will include the
    #   parsable resource data along with its "provisioningState", which can be Creating, Succeeded, or Failed.
    #   The Location: types will also be returned with "202 - Accepted" status codes. These responses will look very much
    #   like the original response from the PUT request, so they can be parsed as they would normally.
    # - It is possible to see both Azure-Async AND Location in the response. If this is the case (at least in our experience),
    #   the response will act as though it is the Location type and the response will contain the parsable data.
    # See https://github.com/Azure/autorest/blob/master/docs/extensions/readme.md#x-ms-long-running-operation-options
    # for more information on async resource creation in Azure.
    LocationSearchStr = "Location: "
    AzureAsyncSearchStr = "Azure-AsyncOperation: "
    response_str = response.to_str
    if response.status_code in ['202', '201'] and (LocationSearchStr in response_str or LocationSearchStr.lower() in response_str):
        if LocationSearchStr in response_str:
            url = response_str.split(LocationSearchStr)[1]
        elif LocationSearchStr.lower() in response_str:
            url = response_str.split(LocationSearchStr.lower())[1]
        data_in_poll_response = True
    elif (AzureAsyncSearchStr in response_str):
        url = response_str.split(AzureAsyncSearchStr)[1]
    else:
        return None, False

    url_split = url.split("https://")
    if len(url_split) > 1:
        url = url_split[1]
    else:
        return None, False
    try:
        url_part = url.partition('/')
        hostname = url_part[0]
        url = url_part[1] + url_part[2]
        token_value = request_utilities.get_latest_token_value()
        if token_value is None or token_value == request_utilities.NO_TOKEN_SPECIFIED:
            token_value = ''
        # Create the GET request to poll the url
        req_data = 'GET ' + url.split('\r\n')[0] +\
            " HTTP/1.1\r\nAccept: application/json\r\nHost: " +\
            hostname + "\r\nContent-Type: application/json\r\n" +\
            token_value + "\r\n"
        return req_data, data_in_poll_response
    except Exception as err:
        # Log any exception and then return that no polling request exists.
        # It is better to skip polling and continue the fuzzing run than to crash or end.
        # The side effect will be that RESTler may attempt to use a resource before it is
        # created, which may lower coverage during a smoke test, but could also potentially
        # lead to a bug being uncovered in the service being fuzzed.
        RAW_LOGGING(f"Exception while creating the polling request: {err!s}")
        return None, False

def make_GET_request(request_data):
    """ Helper that converts a request's rendered data to a GET
    with a matching endpoint. This function replaces @request_data's
    method with GET and removes a body, if present, before returning
    the new request data.

    @param request_data: The request to convert to a GET. This is fully
                         rendered request data in a format that is ready
                         to be sent to HttpSock's sendRecv function.
    @type  request_data: Str

    @return: The new GET request
    @rtype : Str

    """
    from engine.transport_layer.messaging import DELIM
    # Get the endpoint from the request data
    data_part = request_data.partition(DELIM)
    get_data = data_part[0]
    # Get the method
    method = get_data.partition(' ')[0]
    # Replace the request data's method with GET
    get_data = get_data.replace(method, 'GET')
    # Reinsert the closing delimiters before returning
    return get_data + data_part[1]

def try_parse_GET_request(request_data):
    """ Helper that creates a GET request from a request's rendered
    data, sends that request, and then checks for a success (200) status.

    @param request_data: The request to convert to a GET. This is fully
                         rendered request data in a format that is ready
                         to be sent to HttpSock's sendRecv function.
    @type  request_data: Str

    @return: The response of the GET request if it's a 200, otherwise None
    @rtype : Str

    """
    async_get_data = make_GET_request(request_data)
    get_response = request_utilities.send_request_data(async_get_data)
    if get_response.status_code == '200':
        # The new GET request was successful, set it as the data to parse and return
        return get_response
    return None

def try_async_poll(request_data, response, max_async_wait_time, poll_delete_status=False):
    """ Helper that will poll the server until a certain resource
    becomes available.

    This function will check the response from a PUT or POST request to
    see if it contains one of the known async resource creations strings and,
    if so, will poll the URL specified in the response until the resource is
    said to be available or a max timeout has been reached.

    @param request_data: The request that was sent's data string
    @type  request_data: Str
    @param response: The response returned after @request was sent
    @type  response: Str
    @param max_async_wait_time: The maximum amount of time we will wait (in
                                seconds) for the resource to become available
    @type  max_async_wait_time: Int

    @return: A tuple containing:
             - The list of responses for parsing, which will either contain the @response
             passed to this function, or in the case of an async request, the
             response from the end of the async operation (if finished),
             and the response from the GET request.
             It is possible that the response of the async request when finished does not
             contain all of the expected fields in the schema of the async response, so as a
             workaround the GET response is also returned to try to obtain this additional information.
             - A boolean that is True if there was an error when creating the
             resource
             - A Boolean that tells the caller whether or not async polling was
             attempted
    @rtype : Tuple(HttpResponse, boolean, boolean)

    """
    from utils.logger import raw_network_logging as RAW_LOGGING
    from utils.logger import print_async_results as LOG_RESULTS

    responses_to_parse = []
    resource_error = False
    async_waited = False
    if  Settings().wait_for_async_resource_creation and max_async_wait_time > 0\
    and (request_data.startswith("PUT") or request_data.startswith("POST") or (poll_delete_status and request_data.startswith("DELETE"))):
        # Get the request used for polling the resource availability
        data, data_in_poll_response = get_polling_request(response)
        if data:
            RAW_LOGGING(f"Waiting for resource to be available... max_async_wait_time: {max_async_wait_time} seconds.")
            async_waited = True
            poll_wait_seconds = 1
            start_time = time.time()
            while (time.time() - start_time) < max_async_wait_time:
                try:
                    # Send the polling request
                    poll_response = request_utilities.send_request_data(data)
                    time_str = str(round((time.time() - start_time), 2))
                    if data_in_poll_response:
                        if poll_response.status_code in ['200' ,'201']:
                        # If this returned a '200' or '201' status code, the response should contain the parsable data.
                        # Otherwise, continue to poll as the resource has not yet been created. These types will
                        # return a '202 - Accepted' while the resource is still being created.

                            responses_to_parse.append(poll_response)
                            if not poll_delete_status:
                                LOG_RESULTS(request_data,
                                    f"Resource creation succeeded after {time_str} seconds.")
                                # Also, attempt to execute a GET request corresponding to this resource and
                                # return the response.  This is used in case all of the expected properties are
                                # not present in the async response.
                                RAW_LOGGING("Attempting to get resources from GET request...")
                                get_response = try_parse_GET_request(request_data)
                                if get_response:
                                    # Use response from the GET request for parsing. If the GET request failed,
                                    # the caller will know to try and use the original PUT response for parsing
                                    responses_to_parse.insert(0, get_response)
                            # Break and return the responses to be parsed
                            break
                        elif int(poll_response.status_code) >= 300:
                            # Error obtaining the polling response.
                            # It may still be possible to extract the relevant ID out of the original response,
                            # which will be added before exiting the function
                            break
                        else:
                            # Continue polling
                            pass
                    else:
                        # There is no data in the polling response.
                        # In such cases, try to execute a corresponding GET request and obtain
                        # information from the response
                        # This comes from Azure-Async responses that do not contain a Location: field
                        # Check for the status of the resource
                        response_body = json.loads(poll_response.json_body)
                        done = str(response_body["status"]).lower()
                        if done == "succeeded":
                            LOG_RESULTS(request_data,
                                f"Resource creation succeeded after {time_str} seconds.")
                            get_response = try_parse_GET_request(request_data)
                            if get_response:
                                responses_to_parse.append(get_response)
                        elif done == "failed":
                            LOG_RESULTS(request_data,
                                f"The server reported that the resource creation Failed after {time_str} seconds.")
                            resource_error = True

                        # Break and return the responses to be parsed
                        break
                except json.JSONDecodeError as err:
                    LOG_RESULTS(request_data, "Failed to parse body of async response, retrying.")
                    # This may have been due to a connection failure. Retry until max_async_wait_time.
                    time.sleep(poll_wait_seconds)
                    continue
                except Exception as err:
                    LOG_RESULTS(request_data,
                        f"An exception occurred while parsing the poll message: {err!s}")
                    break

                try:
                    if not poll_response.status_code.startswith('2'):
                        LOG_RESULTS(request_data, f"Resource creation failed after {time_str} seconds"
                                                f" because status code '{poll_response.status_code}' was received.")
                        # When an error is received in a polling response, the resource may still be created -
                        # This should be checked with a GET request.
                        break
                except Exception as err:
                    LOG_RESULTS(request_data,
                        f"An exception occurred while parsing the poll message: {err!s}")
                    break
                time.sleep(poll_wait_seconds)
            else:
                RAW_LOGGING("Resource polling timed out before the resource was available.")
                LOG_RESULTS(request_data,
                    f"Failed to create resource in {max_async_wait_time} seconds.")
                RAW_LOGGING("Attempting to get resources from GET request...")
                # Do not use a GET to obtain the status for a DELETE request.
                # A resource with the same ID may have been re-created.
                if not request_data.startswith("DELETE"):
                    get_response = try_parse_GET_request(request_data)
                    if get_response:
                        # Use response from the GET request for parsing. If the GET request failed,
                        # the caller will know to try and use the original PUT response for parsing
                        responses_to_parse.append(get_response)

    if len(responses_to_parse) == 0:
        responses_to_parse.append(response)
    return responses_to_parse, resource_error, async_waited
