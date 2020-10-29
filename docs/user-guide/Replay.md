# How to reproduce bugs found by RESTler

In *Replay* mode, RESTler can replay a sequence from a bug_bucket log that was created during a test or fuzzing run.  These bug_bucket logs can be found in the RestlerResults/experiment##/bug_buckets/ directory.

## Using the replay log

To reproduce a bug bucket using RESTler,
send the following command (as an example):

`C:\RESTler\restler\restler.exe replay --replay_log C:\restler-test\Test\RestlerResults\experiment20652\bug_buckets\PayloadBodyChecker_500_1.txt --token_refresh_command "<command>" --token_refresh_interval 30`

In this example, RESTler will replay the log `PayloadBodyChecker_500_1.txt`.
If authentication is required to replay the sequence, the authentication options must be specified during replay.

As you can see above,
the IP, port, and authorization token refresh command/interval are all used
in the same way that they were when running RESTler in test or fuzz mode.

The results of the replay can be found in a Replay sub-directory of the current working directory where RESTler was executed.
The newly created logs directory will include a single network log with the results of the replay.
This log will show the exact sequence of requests that were sent to the server
and responses that were received.
These results can be used to determine if the service is still behaving in the same way
as it was when the bug was found initially.

__Important note about resource creation during replays:__
Any resources that were created during the replay will NOT be automatically deleted
unless the replaying sequence itself deletes the resource.
Any resources created should be removed manually.

## Replay log format

The replay log is created anytime a new bug bucket is reported.
This replay log consists of the full sequence of requests that were sent to create the bug.
Each request is also paired with the corresponding response that was received from the server.
Each request and response is displayed exactly as sent and received, including dynamic objects,
so that the sequence can be replayed exactly as it was executed before.

Below is an example of the requests and responses from a replay log sequence.

```
-> POST /api/blog/posts HTTP/1.1\r\nAccept: application/json\r\nHost: localhost:8888\r\nContent-Type: application/json\r\n\r\n{\n    "id":0,\n    "body":"fuzzstring"}\r\n
! producer_timing_delay 0
! max_async_wait_time 0
PREVIOUS RESPONSE: 'HTTP/1.1 201 CREATED\r\nContent-Type: application/json\r\nContent-Length: 45\r\nServer: Werkzeug/0.16.0 Python/3.8.2\r\nDate: Thu, 01 Oct 2020 22:00:27 GMT\r\n\r\n{\n    "id": 5875,\n    "body": "fuzzstring"\n}\n'

-> PUT /api/blog/posts/5875 HTTP/1.1\r\nAccept: application/json\r\nHost: localhost:8888\r\nContent-Type: application/json\r\n\r\n{"body":"fuzzstring"}
! producer_timing_delay 0
! max_async_wait_time 0
PREVIOUS RESPONSE: 'HTTP/1.1 500 INTERNAL SERVER ERROR\r\nContent-Type: application/json\r\nContent-Length: 176\r\nServer: Werkzeug/0.16.0 Python/3.8.2\r\nDate: Thu, 01 Oct 2020 22:00:28 GMT\r\n\r\n{\n    "message": "The server encountered an internal error and was unable to complete your request. Either the server is overloaded or there is an error in the application."\n}\n'
```

When replaying the logs,
RESTler will ignore any text line that does not begin with either ```'->'``` or ```'!'```.
The ```'->'``` symbol tells restler that this line contains a request string to be sent.
The ```'!'``` symbol tells RESTler that a setting exists on this line that was used when the bug was found initially, e.g. producer_timing_delay.
The response is printed solely for the user to use when comparing the previous results with a replay run.

You may notice that content-length and user-agent are not included in the replay log.
These fields are populated automatically by RESTler when the request is sent to the server,
so they are not needed (and shouldn't exist) in the log.

## Using replay logs to send custom sequences
While the main purpose of replay logs are to re-test bugs previously found,
it is also possible to use these files as a way to send custom sequences to RESTler, similar to how you may send a request through *curl* or *Postman*.

To do this,
the important thing to note is the format of the request string in the replay log,
so you can mimic it correctly.

Each request must be on a single line in the file and begin with ```'-> '```.
A request must be in the following format (followed by an optional body):

_\<METHOD\>_ _\<endpoint\>_ HTTP/1.1\r\nAccept: application/json\r\nHost: _\<hostname\>_\r\nContent-Type: application/json\r\n\r\n

It is also possible to include a producer timing delay or max async wait time to a request.
 To do this, begin a new line directly below the request string line
and begin the line with ```'! '```.
After the ```'! '```,
enter *producer_timing_delay* OR *max_async_wait_time* followed by the number of seconds desired to wait after the request.
As a reminder,
*producer_timing_delay* will wait a hard number of seconds after the request is sent,
while max_async_wait_time will attempt to perform an asynchronous polling-wait based on the response received from the server,
with a maximum resource-creation-wait-time of the max_async_wait_time setting.


##