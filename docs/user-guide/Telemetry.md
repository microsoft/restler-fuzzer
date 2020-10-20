# Telemetry

RESTler collects telemetry in order to understand usage and prioritize improvements.

RESTler telemetry contains:

- Information about the task RESTler ran and whether it succeeded or failed
- When available, request coverage and bug statistics (for example, how many requests were executed, and how many of which type of bugs were found).  




## How to disable sending telemetry to Microsoft

Set the ```RESTLER_TELEMETRY_OPTOUT``` environment variable to ```1``` or ```true```. 

Or, if you prefer to make a one-time code change, you may set the ```InstrumentationKey``` to an empty string in ```src\compiler\Restler.Compiler\Telemetry.fs``` . 

You may also configure this key (to an empty string or your own AppInsights instrumentation key) via the ```Restler.runtimeconfig.json``` settings file (in the ```restler``` drop sub-directory).    Configuring this to your own AppInsights allows you to see exactly the telemetry that Microsoft collects.

