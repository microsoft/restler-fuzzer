# Authentication

RESTler supports token-based and certificate based authentication.

**Token based authentication**


The user has three options for providing token based authentication; Module, Location, and CMD. For details on the format of these options in the settings file, please see SettingsFile.md. All options must return the token in the format specified in the Token Formatting section below.

**Module**

The user must provide the path to a python module (.py) that implements a function that returns a token, and the name of the function (default: `acquire_token`). RESTler will import the module and call the function to obtain tokens.

Additionally, a user can opt to add data (e.g. with additional authentication-related parameters specific to the service under test) to pass to this function. The function signature must be as follows:

```python
def acquire_token(data, log):
    ## Return token
```

Where

- `data` is a dictionary containing the json payload specified in the corresponding engine setting (see SettingsFile.md)
- `log` is a function that may be used to write logs to a network auth text file that will be saved in the RESTler results directory next to the network logs.


**Location**

The user must provide the full path to a text file containing a token. RESTler will read this text file to obtain tokens.

**Command**

The user must provide a separate program to generate tokens, which implements the authentication method required by the API.  This will be invoked in a separate process by RESTler to obtain tokens.

`>my_gettoken.exe <args to my_gettoken>`

**Token Formatting**

All token-based authentication mechanisms require tokens to be specified as follows - metadata about the tokens on the first line, followed by each token and the required token header on a separate line for each application.  For example:

```
{u'app1': {<any additional metadata you'd like to print. currently only used for troubleshooting. >}, u'app2':{}}
ApiTokenTag: 9A
ApiTokenTag: ZQ
```

When multiple token headers are required for each request, they could be defined on multiple lines, separated with the delimiter `---` on a new line:

```
{u'app1': {}, u'app2':{}}
ApiTokenTag: 9A
ApiTokenTag2: 9B
---
ApiTokenTag: ZQ
ApiTokenTag2: BZZ
```

RESTler will obtain new tokens by invoking the token generation script with the frequency specified in the *--token_refresh_interval* option.


Note: in the above example, there are two different applications.  This is only required by the 'namespace' checker (off by default).  This checker is used to detect unauthorized access by one user/app to the data of another user/app.  To have this checker work as intended to find bugs, you should specify two users that do not have access to each other's private resources (for example, two different accounts with private data to each).​

**Token Refresh Interval**

All token-based authentication mechanisms require the user to provide "token_refresh_interval" an interval in seconds after which RESTler will attempt to refresh the token by executing the specified token authentication mechanism.


**Token values in logs**

RESTler has logic to prevent token values from being written to the network logs.  It is recommended to check the RESTler network logs and make sure that the token values are, indeed,  successfully omitted from the logs.

**Certificate based authentication**

A Certificate and corresponding keys can be used as an authentication mechanism. See the SettingsFile.md for the settings that should be used to specify a certificate. If both the keyfile and certificate path are valid, RESTler will attempt to use it during the SSL handshake.