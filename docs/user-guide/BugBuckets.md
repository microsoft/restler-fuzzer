# RESTler Bug Bucketing
Whenever RESTler identifies a bug, it reports it in the bug_buckets directory. RESTler will also attempt to reproduce the bug
and report whether or not it was reproducible.
The bug summary will be logged to a central bug_buckets.txt file
and an individual detailed log is separately created for each particular bug,
which can be found in a bug_buckets directory.

## bug_buckets.txt
The main bug buckets log is located in the bug_buckets directory and is called bug_buckets.txt.

The top section of this log contains a list of all bug types associated with this run
and the total number of bugs found for each.
A bug type simply refers to how the bug was found,
i.e., from the main driver or a specific checker.

Below the bucket count, every bug is displayed one by one.

The header for each bug displays the bug type,
whether the bug was reproducible, and the name of a bug log file in the current directory where more detailed information about the bug can be found.
Next, the sequence of requests that was used to trigger the bug is displayed, with the last request in the sequence being the one where the bug was found. The sequence is displayed with each request on a separate line, in order.
The requests are displayed with their method and endpoint only.
The exact request string that contains dynamic object resources is displayed in the detailed bug log file in the bug_buckets directory, which we discuss next.

## Individual bug bucket logs
Along with populating the bug_buckets.txt log,
an individual bug bucket for each bug is created in the bug_buckets directory,
which is located at the same level as the logs directory in the experiment folder.
The name of each log is its bug type followed by a number that increments with each new bug of that type.

The log's header starts with the bug type followed by whether or not the bug was reproduced.
It then continues with an explanation on replaying the bug -
this will be discussed more later.

Within the log, each request in the sequence that created the bug is displayed
and the requests are separated by a whitespace line.

The exact request string that was sent to the server is displayed following the '->' symbol.

Below each request is a list of '!' symbols,
which are notifications about certain settings that were used when sending this request.
These settings will be used again during replay to ensure a similar testing environment.

Below the notifications is the response that was received from the service when the bug was identified.

## Reproducing bugs with RESTler
RESTler has the capability of replaying bugs that were logged from previous fuzzing runs.
This is possible by passing a bug's individual bug bucket log to RESTler in a special mode.

This mode will simply replay the requests in the log.
For this to work properly,
any pre-created resources or environment-specific values
(such as subscriptions, account info, etc)
must be edited in the file manually.
Authorization tokens can be populated by RESTler by supplying the authorization script to RESTler when replaying.
  See [Replay](Replay.md) for details on how to use the replay log to reproduce each bug.