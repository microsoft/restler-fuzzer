# Authentication

RESTler supports token-based authentication.  

The user must provide a separate program to generate tokens, which implements the authentication method required by the API.  This will be invoked in a separate process by RESTler to obtain and regularly refresh tokens.  When invoked, this program must print metadata about the tokens on the first line, followed by each token and the required token header on a separate line.  For example:

`>my_gettoken.exe <args to my_gettoken>`

```
{u'app1': {<any additional metadata you'd like to print. currently only used for troubleshooting. >}, u'app2':{}}
ApiTokenTag: 9A
ApiTokenTag: ZQ
```


RESTler will obtain new tokens by invoking the token generation script with the frequency specified in the *--token_refresh_interval* option.


Note: in the above example, there are two different applications.  This is only required by the 'namespace' checker (off by default).  This checker is used to detect unauthorized access by one user/app to the data of another user/app.  To have this checker work as intended to find bugs, you should specify two users that do not have access to each other's private resources (for example, two different accounts with private data to each).​

**Token values in logs**

RESTler has logic to prevent token values from being written to the network logs.  It is recommended to check the RESTler network logs and make sure that the token values are, indeed,  successfully omitted from the logs. 