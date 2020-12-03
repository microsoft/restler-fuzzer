# Checkers
Checkers are run during fuzzing runs automatically after being triggered after certain request sequences.
They are used for additional bug hunting not carried out by normal fuzzing.

The checkers are intended to work independently from each other
and not affect each other or the fuzzing run.

Unless otherwise specified,
each of the checkers listed in this document
are enabled by default during fuzzing
and disabled by default in 'test' mode.

To enable or disable more checkers during fuzzing (fuzz-lean or fuzz modes),
simply add one, or both, of the following to the command-line (as example):

```
--enable_checkers UseAfterFree,InvalidDynamicObject
--disable_Checkers LeakageRule
```

As you can see from the example above,
the checker names should be specified as they are below,
but without the word "Checker".
The checker names should be specified as comma-separated values.

## UseAfterFreeChecker
Detects that a deleted resource can still be accessed after deletion.

Triggers after a successful sequence where the last request was a DELETE.
Will then send a request that uses the freed resource to see if it is successful (returns 20x).
If so, RESTler reports a bug.

## NameSpaceRuleChecker (off by default)
Detects that an unauthorized user can access service resources.

Triggers after a valid sequence where the last request contains a consumed resource.
Will then attempt to use that resource as a different, unauthorized, user.

## ResourceHierarchyChecker
Detects that a child resource can be accessed from a different parent resource.

Triggers after a successful sequence that does not contain a DELETE request
and where the final request contains at least two consumed resources.
Will then attempt to access a child resource with a different parent.

## LeakageRuleChecker
Detects that a failed resource creation leaks data in subsequent requests.

Triggers after a sequence that ended
with a failed resource-generating request (response 4xx).
Will then attempt to access that resource that failed to be created
by sending a request that uses the resource.

## InvalidDynamicObjectChecker
Detects errors by replacing valid dynamic object IDs with invalid values.

Triggers after a sequence that ends in a request that consumes at least one resource.
Will then re-send the final request with the resource(s) replaced with an invalid resource value.
If more than one resource exists,
each combination of valid/invalid resources will be used.

Note that all _valid-object_ references below will be replaced with the original, valid, dynamic object

The default "invalid dynamic objects" used are:
* '_valid-object_?injected_query_string=123'
* '_valid-object_/?/'
* '_valid-object_??'
* '_valid-object_/_valid-object_'
* '{}'

It is possible to disable these default invalid objects by adding the following section to the settings file:
```
"checkers": {
    "invaliddynamicobject": {
        "no_defaults": true
    }
}
```

It is also possible to define a list of your own custom invalid dynamic objects by specifying them in the settings file:
```
"checkers": {
    "invaliddynamicobject": {
        "invalid_objects" : [
            "someinvalidobject",
            "valid-object/$*"
        ]
    }
}
```

Note that in the the above example the custom list will be added to the default list.
To replace all defaults, you must also include the "no_default" setting.

## PayloadBodyChecker
Detects errors by fuzzing a request's payload body.

Triggers after a request that contains a payload body.
Will then attempt to fuzz the body by
replacing values,
editing the format,
changing object types,
etc.

__Note:__ The algorithms and techniques used in the PayloadBodyChecker
are described in [Intelligent REST API Data Fuzzing​​](https://patricegodefroid.github.io/public_psfiles/fse2020.pdf) (FSE'2020).
As discussed in that paper, this checker has many settings. The default
 setting configuration matches what was found as the 'optimal'
 combination in the experimental study presented in the paper.
 Other checker settings can be specified in the settings file as usual:
```
"checkers": {
    "payloadbody": {
        <new settings go here>
    }
}
```
See the payloadbodychecker code for its list of available settings.

## ExamplesChecker
Detects errors by sending new requests that use their body and query examples.

Triggers after a new request is discovered that has examples.
Will send a new request for every unique example for that request.
Records 5xx errors and logs the status codes received for each sent request.
Status codes can be used to check for valid requests that were previously invalid,
or in scenarios where testing of multiple examples is necessary for full coverage.

# Create your own checker
If you would like to create your own checker,
please follow the README file in the restler\checkers directory.

To enable custom checkers _without_ adding them to the checker \_\_init\_\_ file
you can simply add a list of custom checkers to the settings file,
like in the example below (these custom checkers will run __after__ any other enabled checkers):

`"custom_checkers": ["<path_to_checker>", "<path_to_checker2>"]`
