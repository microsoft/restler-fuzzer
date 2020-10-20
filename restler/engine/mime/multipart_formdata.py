# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Handling of multipart/form-data MIME type. """
import time


def render(payloads):
    """ Render multipart/form-data MIME type.

    @param payloads: The payload to render according to the MIME type.
    @type payloads: Str

    @return: The properly rendered payload.
    @rtype : String

    Note: To understand why we iterate over multipart/formdata like this one
    should first take a look at this example:
        https://stackoverflow.com/questions/4526273/what-does-enctype-multipart-form-data-mean
    and then read the correspinding RFC:
        https://www.ietf.org/rfc/rfc2388.txt

    Overall, there is nothing exotic here but one needs to be careful
    positioning the delimiters and the proper structure and headers.

    payloads may contain an arbitrary number of content-disposition and
    datasteam path dictionaries, as follows:

    payloads = [
      {
          'content-disposition': 'name="file"; filename="bla1.gz"',
          'datastream': 'bla.gz'
      },
      {
          'content-disposition': 'name="file"; filename="bla2.gz"',
          'datastream': 'bla2.gz'
      },
      ...
    ]

    """
    boundary = "_CUSTOM_BOUNDARY_{}".format(str(int(time.time())))

    req = "Content-Type: multipart/form-data; boundary={}\r\n\r\n".\
        format(boundary)
    req+= '--{}\r\n'.format(boundary)

    for i, payload in enumerate(payloads):
        req += 'Content-Disposition: form-data; {}\r\n'.\
            format(payload['content-disposition'])
        req += 'Content-Type: {}\r\n\r\n'.\
            format("application/octet-stream")
        try:
            f = open(payload['datastream'], 'r')
            data = f.read()
            f.close()
        except Exception as error:
            print("Unhandled exception reading stream. Error:{}".format(error))
            raise
        req += '{}\r\n\r\n'.format(data)
        if i == len(payloads) - 1:
            req += '--{}--\r\n'.format(boundary)
        else:
            req += '--{}\r\n\r\n'.format(boundary)

    return req
