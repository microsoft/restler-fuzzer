# CheckerBase
The checkers are created as subclasses to the CheckerBase abstract base class.  The CheckerBase class is responsible for creating
the subclasses' logs and maintaining data members that are shared across all checkers.
The CheckerBase class also declares and/or defines functions that are required for each checker subclass.

See the checkers in this directory for examples.

## Data Members:
* _checker_log: The CheckerLog log file for the checker
* _req_collection: A reference to the RequestCollection object shared throughout restler
* _fuzzing_requests: The FuzzingRequestCollection object that contains all the requests being fuzzed.
* _enabled: Whether or not this checker is enabled during this run
* _friendly_name: The "friendly" name associated with this checker. It is used to enable/disable checkers from the command-line.
* _connection_settings: The settings for the socket connection (IP address, Port, etc)
* _mode: The checker's mode (optionally used by some checkers)

## Functions:
* apply: This abstract function is required to be defined by each checker. It is called after sequences are rendered for each enabled
checker. It can be thought of as a checker's "main" entry point.
* _send_request: This function sends a request to the service under test and then returns the response. The function request_utilities.call_response_parser() should be called after this function
in order to update resource dependencies (due to the new request that was just executed) and make these visible to the garbage collector (otherwise resources created by the newly sent request will not be garbage collected).
* _render_and_send_data: This function renders data for a request, sends the request to the service under test, and then adds that rendered data and its response to a sequence's sent-request-data list. 
  * This sent-request-data list is used exclusively for replaying sequences to test for bug reproducibility. Because checkers tend not
  to use the sequences.render function to render and send requests, the sent-request-data is never added to the list. This means that,
  in order to replay the sequence when a bug is found, this function must be called.
  * This function thus includes the functionality of both _send_request() and request_utilities.call_response_parser() combined.
* _rule_violation: This function is defined by default in CheckerBase to check a response's status code for "500" or "20x" (note: "20x"
check is optional) and then call an (optional) "false alarm" function to optionally filter out some specific cases (more on this below).
  * This function should be called by each checker subclass to check for rule violations.
  * If the default behavior is not desirable for a new checker, this function can (and should) be overridden in the subclass to better
  match the checker's requirements.
  * See below for more.
* _false_alarm: This function is defined in CheckerBase to return False by default as it is called by the default _rule_violation function.
  * If a checker should check for false alarms this function should be defined/overridden in the subclass.
  * See below for more.
* _print_suspect_sequence: This function prints a "suspect sequence" to the appropriate checker log. This function should be called if a
rule violation is detected.

# Creating a Checker
## To create a checker, the following rules must be adhered to:

* The checker must be defined in its own file and this file must be specified in the settings.json file like this 

  ```"custom_checkers": ["C:\\<path>\\my_new_checker.py"]``` 
  
  or be added to checkers/\_\_init\_\_.py (the order of this list defines the order in which the checkers will be called).
* The checker must inherit from CheckerBase.
* The checker's class name must end with Checker.
* The checker must define an apply function.
* If the checker detects a rule violation, the checker must update bug buckets and print the suspect sequence.
* The checker's constructor must take req_collection and fuzzing_requests as an argument.
* The checker's constructor must call the CheckerBase constructor with req_collection, fuzzing_requests, and a boolean value that defines whether or not this checker
should be enabled by default (True to enable by default, False to disable by default).
* The checker's apply function must take exactly three arguments; valid_rendering, invalid_rendering, and lock
(see __How checkers are called and used in RESTler__ below for details).
* The checker must be independent from all other checkers. This means it should neither interfere with other checkers nor rely on them.

## How checkers are called and used in RESTler
After each sequence rendering an apply_checkers function is called. This function gets a list of CheckerBase subclasses and, for each
subclass, it checks whether or not the checker is enabled and, if so, it then calls the checker's apply function.

A checker's apply function takes three arguments: rendered_sequence and lock.
* The __rendered_sequence__ argument is a RenderedSequence object that contains information about the sequence that was just rendered.
This object contains:
  * sequence - The Sequence object that was rendered.
  * valid - A boolean indicating whether or not the sequence was "valid" (20x) when rendered.
  * faliure_info - A FailureInformation enum that, if set, indicates a reason for the sequence to have failed.
  * final_request_response - The response received after sending the final request in the sequence, as an HttpResponse object.
* The __lock__ argument is a global lock that should be used if any portions of the checker code should be protected from
race conditions when RESTler is run in parallel mode.

### Sending requests and parsing responses
Before sending a new request to the service under test, the request's data must first be rendered. The correct "checker way" of rendering a
request is to call the self._render_and_send_data function with the request and the sequence being rendered.
It is important to pay careful attention to the Sequence object that will be used during the execution of the checker. If a
sequence is being re-rendered by the checker, a new Sequence object should be created and each request should be added to it along
with its rendered data - the rendered data portion is added using the _render_and_send_data function above. For the
cases where the original sequence will _not_ be re-rendered, it is sufficient to append any new requests and their data to the end
of the sequence object that was passed to the apply() function originally. In other words, all these requests are then executed one by one from the current state (which is thus not reset between these executions).

After the sequence has been updated and the request's data has been rendered, the checker can then call self._send_request along
with the parser and rendered data that were returned from the _render_and_send_data function. The _send_request function
will return the server's response (as a string). From there, the checker can make a call to self._rule_violation along with the
Sequence object for the sequence that was just sent to the server and the response returned by _send_request. If _rule_violation
returns True then it means that there was a rule violated and the checker should now update the bug_buckets and print the suspect
sequence. By default, the update_bug_buckets function will attempt to reproduce the bug by replaying the sequence object that is
passed to it. This is where the importance of appending the rendered data to the sequence comes in. The replay function will send the
rendered data exactly as it did the first time. If you do not wish to attempt to reproduce the error, add reproduce=False to the
argument list of update_bug_buckets.

### Rule violations and false alarms
The default _rule_violation function is defined in CheckerBase and takes a Sequence object, a response (string), and a boolean
valid_response_is_violation as arguments.
* The Sequence object is the sequence related to this rule violation check. This is passed through to the _false_alarm function
to be used however a checker may need to use it.
* The response is the response that was returned by the server that will be checked for a rule violation.
* The valid_response_is_violation boolean defaults to True. If this is set to False then "20x" status codes will not be considered
a violation by the default _rule_violation definition

The _rule_violation function can be overriden by an individual checker subclass, but the default definition works by getting the response's
status code and then checking whether or not it is a "500" or "20x" (if valid_response_is_violation is set).  If either of these are true,
the function then calls _false_alarm to make sure a false alarm was not triggered.

The _false_alarm function is defined in CheckerBase to simply return False by default. This essentially means that, by default, no false
alarm check is done.  If a checker wants to define a false alarm check it should override this function and define one itself.
The false alarm function takes a Sequence object and a response (string) as arguments.
* The Sequence object is the sequence that was being rendered when this function was called
* The response is the response that was returned by the server, identified as a rule violation, and will now be checked for a false alarm.




