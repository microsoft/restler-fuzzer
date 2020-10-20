# Best Practices When Using RESTler

This high-level guide discusses how to use RESTler effectively.

## Fuzzing in Production vs Staging/Test/Canary

Whenever possible, fuzzing in a staging/test/canary environment is recommended
because RESTler fuzzing can cause resource outages if it triggers a bug.

Indeed, RESTler typically creates and deletes 1000s of resources per hour (if the service allows it). If
the service under test does not handle such operations properly, RESTler can trigger
outages due to leaks, bugs in quota management, flooded backend services, or
crippled back-end states (and has done so in a few occasions).

However, if no test deployment is available, remember that fuzzing in production is typically
better than no fuzzing at all!

## Monitoring Service Health while Fuzzing

During or after fuzzing with RESTler, check the health monitors of the service under test to see
if there was a resource leak or other impact on service health.  If so, file a bug!   Add to the report that the incident was
triggered while fuzzing with RESTler, as this may help debug and root-cause the issue later.

If possible, examine the logs of service under test to see if any assertion violations were triggered
during fuzzing. Such service-internal events are invisible to RESTler and it will not detect and report
these. If there are assertion violations, file one bug for each assertion type.

## How to File a Fuzzing Bug

If you file bug reports about bugs found by RESTler or in the process of using RESTler,
please add the tag "RESTler" in the bug report to faciltate bug tracking. 

## Fundamental Limitations of RESTler

RESTler works best when fuzzing CRUD services: RESTler can then Create (PUT/POST), Read (GET),
Update (PATCH) and Delete (DELETE) cloud resources and challenges these operations during fuzzing.

In contrast, RESTler requires user-assistance when fuzzing non-CRUD services, or when fuzzing services requiring
*pre-provisioning* of specific resources.

As an example, consider a network-watcher service which can monitor an existing network but which
cannot create a network (and all its elements) through its API. In that case, prior to fuzzing with RESTler,
the user needs to pre-create a network and then enter specific values relevant to the network-watcher service
in a fuzzing dictionary, such as names/Ids for VMs, storage nodes, firewalls, and other network elements
which are either created manually or automatically using other APIs. Only after this pre-provisioning step,
RESTler can be used to properly fuzz the network-watcher API.
