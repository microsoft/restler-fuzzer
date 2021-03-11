// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.Driver.Types

/// The command that the user specifies to refresh an authentication token
type RefreshTokenCommand =
    // The full command line is specified.
    | UserSpecifiedCommand of string

/// Options for refreshing an authentication token in the RESTler engine
type RefreshableTokenOptions =
    {
        /// The duration after which to refresh the token
        refreshInterval : string

        /// The command that, when run, generates a new token in the form required
        /// by the API (e.g. 'Header : <value>')
        refreshCommand : RefreshTokenCommand
    }

/// The user-facing engine parameters
type EngineParameters =
    {
        /// File path to the REST-ler (python) grammar.
        grammarFilePath : string

        /// File path to the custom fuzzing dictionary.
        mutationsFilePath : string

        /// The IP of the endpoint being fuzzed
        targetIp : string option

        /// The port of the endpoint being fuzzed
        targetPort : string option

        /// The maximum fuzzing time in hours
        maxDurationHours : float

        /// The authentication options, when tokens are required
        refreshableTokenOptions : RefreshableTokenOptions option

        /// The delay in seconds after invoking an API that creates a new resource
        producerTimingDelay : int

        /// The checker options
        /// ["enable or disable", "list of specified checkers"]
        checkerOptions : (string * string) list

        /// Specifies to use SSL when connecting to the server
        useSsl : bool

        /// The string to use in overriding the Host for each request
        host : string option

        /// Specifies the engine settings path.  This parameter is optional.
        settingsFilePath : string

        /// Path regex for filtering tested endpoints
        pathRegex : string option

        /// Replay the specified log.
        replayLogFilePath : string option

        /// Specifies whether to run results analyzer.
        runResultsAnalyzer : bool

    }

let DefaultEngineParameters =
    {
        grammarFilePath = ""
        mutationsFilePath = ""
        targetIp = None
        targetPort = None
        refreshableTokenOptions = None
        maxDurationHours = float 0
        producerTimingDelay = 0
        useSsl = true
        host = None
        settingsFilePath= ""
        checkerOptions = []
        pathRegex = None
        replayLogFilePath = None
        runResultsAnalyzer = true
    }

/// Restler tasks that may be specified by the user
type TaskParameters =
    /// Parameters for the RESTler Swagger compiler
    | CompilerParameters of Restler.Config.Config

    /// Parameters for the RESTler engine
    | EngineParameters of EngineParameters

    /// No parameters specified
    | Undefined

/// The available RESTler tasks
type RestlerTask =
    /// Parse a Swagger specification and generate a RESTler grammar for fuzzing.
    | Compile
    /// Run the RESTler engine in test mode, used for grammar and coverage validation.
    /// This runs the minimum number of sequences to cover all requests defined in the Swagger file.
    | Test
    /// Run the RESTler engine in 'Test' mode with all checkers enabled except namespace.
    | FuzzLean
    /// Run the RESTler engine in fuzzing mode.
    | Fuzz
    /// Replay a log for a bug previously found by RESTler to try to reproduce it.
    | Replay

/// Test driver arguments
type DriverArgs =
    {
        /// The directory to which results should be written.
        outputDirPath : string

        /// Working directory to run tools
        workingDirectoryPath : string

        /// The task to run
        task : RestlerTask

        /// The task arguments
        taskParameters : TaskParameters

        /// The root directory to which logs should be uploaded
        /// If 'None', telemetry is not written
        logsUploadRootDirectoryPath : string option

        /// The full path to the python executable that should be used
        /// to launch the RESTler engine
        pythonFilePath : string option
    }


module Engine =
    open System.Collections.Generic

    /// Testing summary from the RESTler engine
    /// These statistics will be reported in Microsoft telemetry
    //{
    //    "final_spec_coverage": "33 / 33",
    //    "rendered_requests": "33 / 33",
    //    "rendered_requests_valid_status": "33 / 33",
    //    "num_fully_valid": 33,
    //    "num_sequence_failures": 0,
    //    "num_invalid_by_failed_resource_creations": 0,
    //    "throughput": 128.1138759832488,
    //    "total_object_creations": 41,
    //    "total_unique_test_cases": 35.0,
    //    "total_sequences": 31,
    //    "total_requests_sent": {
    //        "gc": 34,
    //        "main_driver": 66
    //    },
    //    "bug_buckets": {
    //        "main_driver_500": 0
    //    }
    //}
    type TestingSummary =
        {
            final_spec_coverage : string // Format: X / Y
            rendered_requests : string   // Format: X / Y
            rendered_requests_valid_status : string // Format: X / Y
            num_fully_valid : int
            num_sequence_failures : int
            num_invalid_by_failed_resource_creations : int
            total_object_creations : int
            total_requests_sent : Dictionary<string, int>
            bug_buckets : Dictionary<string, int>
        }

/// Helper module to produce compact messages in the console, but more
/// verbose messages in a log file to assist troubleshooting.
module Logging =
    open Microsoft.FSharpLu.Logging

    let logInfo (message:string) =
        printfn "%s" message
        Trace.info "%s" message

    let logWarning (message:string) =
        printfn "%s" message
        Trace.warning "%s" message

    let logError (message:string) =
        printfn "\nERROR: %s\n" message
        Trace.error "%s" message

module Platform =
    type Platform =
        | Linux
        | Windows

    open System
    open System.Runtime.InteropServices
    let getOSPlatform() =
        if RuntimeInformation.IsOSPlatform(OSPlatform.Linux) then
            Platform.Linux
        else if RuntimeInformation.IsOSPlatform(OSPlatform.Windows) then
            Platform.Windows
        else
            raise (Exception("Platform not supported."))
