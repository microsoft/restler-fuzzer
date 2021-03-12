// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/// Main program to execute specified stages of the RESTler workflow, which
/// will be invoked by an end user.

open Microsoft.FSharpLu.File
open Microsoft.FSharpLu.Logging
open System.IO
open System
open Restler.Driver.Types
open Restler.Driver
open Microsoft.FSharpLu.Diagnostics.Process
open Restler.Telemetry

[<Literal>]
let CurrentVersion = "7.3.0"
let EngineErrorCode = -2

let exitRestler status =
    exit status

let usage() =
    // Usage instructions should be formatted to ~100 characters per line.
    Logging.logWarning <| sprintf
        "Usage:

  restler --version
          [--disable_log_upload] [--logsUploadRootDirPath <log upload directory>]
          [--python_path <full path to python executable>]
          [ compile <compile options> |
            test <test options> |
            fuzz-lean <test options> |
            fuzz <fuzz options> ]

    global options:
        --disable_log_upload
            Disable uploading full logs to the configured log upload directory.
        --logsUploadRootDirPath <path where to upload logs>
            Upload full logs to this upload directory.
        --python_path <full path to python executable>
            Specify the full path to the python executable with which to launch the RESTler engine.

    compile options:
        <compiler config file>
        OR
        --api_spec <path to Swagger specification>
            A default compiler config file will be auto-generated.
            You must change it later to fit your needs.

    test options:
        --grammar_file <grammar file>
        --dictionary_file <dictionary file>
        --target_ip <ip>
            If specified, sets the IP address to this specific value instead of using the hostname.
        --target_port <port>
            If specified, overrides the default port, which is 443 with SSL, 80 with no SSL.
        --token_refresh_interval <interval with which to refresh the token>
        --token_refresh_command <full command line to refresh token.>
            The command line must be enclosed in double quotes. Paths must be absolute.
        --producer_timing_delay <delay in seconds after invoking an API that creates a new resource>
        --path_regex <path regex>
            <path regex> is a regular expression used to filter which requests are fuzzed.
            See Python regex for documentation: https://docs.python.org/2/howto/regex.html.
            Example: (\w*)/virtualNetworks/(\w*)
        --no_ssl
            When connecting to the service, do not use SSL.  The default is to connect with SSL.
        --host <Host string>
            If specified, this string will set or override the Host in each request.
        --settings <engine settings file>
        --enable_checkers <list of checkers>
        --disable_checkers <list of checkers>
            <list of checkers> - A comma-separated list of checker names without spaces.
            enable_checkers overrides the default list of checkers,
            while disable_checkers removes checkers from the default list of checkers.
            The default list of checkers in fuzz-lean and fuzz mode is
            all the checkers below except namespacerule.
            Supported checkers: leakagerule, resourcehierarchy, useafterfree,
                                namespacerule, invaliddynamicobject, payloadbody,
                                examples.

        --no_results_analyzer
            If specified, do not run results analyzer on the network logs.
            Results analyzer may be run separately.

    fuzz-lean options:
        <The same options as 'test'>
            This task runs test mode with a subset of checkers, which performs some limited fuzzing.

    fuzz options:
        <The same options as 'test'>
        --time_budget <maximum duration in hours>

    replay options:
        <Required options from 'test' mode as above:
            --token_refresh_cmd. >
        --replay_log <path to the RESTler bug bucket repro file>. "
    exitRestler 1

module Paths =

    let CompilerRelativePath = @"../compiler/Restler.CompilerExe.dll"
    let RestlerPyRelativePath = @"../engine/restler.py"
    let RestlerPyExeRelativePath = @"../engine/engine.exe"
    let ResultsAnalyzerRelativePath = @"../resultsAnalyzer/Restler.ResultsAnalyzer.dll"

    let CurrentAssemblyDirectory =
        let assembly = System.Reflection.Assembly.GetExecutingAssembly()
        System.IO.Path.GetDirectoryName(assembly.Location)

    let CompilerExePath = CurrentAssemblyDirectory ++ CompilerRelativePath
    let RestlerPyPath = CurrentAssemblyDirectory ++ RestlerPyRelativePath
    let RestlerPyInstallerPath = CurrentAssemblyDirectory ++ RestlerPyExeRelativePath
    let ResultsAnalyzerExePath = CurrentAssemblyDirectory ++ ResultsAnalyzerRelativePath

module Compile =
    open Restler.Config
    let invokeCompiler workingDirectory (config:Config) = async {
        if not (File.Exists Paths.CompilerExePath) then
            Trace.failwith "Could not find path to compiler.  Please re-install RESTler or contact support."

        let compilerConfigPath = workingDirectory ++ "config.json"
        // If a dictionary is not specified, generate a default one.
        let dictionaryFilePath =
            match config.CustomDictionaryFilePath with
            | None ->
                let newDictionaryFilePath = workingDirectory ++ "defaultDict.json"
                Microsoft.FSharpLu.Json.Compact.serializeToFile newDictionaryFilePath Restler.Dictionary.DefaultMutationsDictionary
                Some newDictionaryFilePath
            | Some s ->
                config.CustomDictionaryFilePath

        let compilerOutputDirPath =
            match config.GrammarOutputDirectoryPath with
            | Some d -> d
            | None -> workingDirectory

        let compilerConfig =
            { config with
                GrammarOutputDirectoryPath = Some compilerOutputDirPath
                CustomDictionaryFilePath = dictionaryFilePath }
        Microsoft.FSharpLu.Json.Compact.serializeToFile compilerConfigPath compilerConfig

        // Run compiler
        let! result =
            startProcessAsync
                "dotnet"
                (sprintf "\"%s\" \"%s\"" Paths.CompilerExePath compilerConfigPath)
                workingDirectory
                (ProcessStartFlags.RedirectStandardError ||| ProcessStartFlags.RedirectStandardOutput)
                NoTimeout
                None

        File.WriteAllText(compilerOutputDirPath ++ "StdErr.txt", result.StandardError)
        File.WriteAllText(compilerOutputDirPath ++ "StdOut.txt", result.StandardOutput)
        if result.ExitCode <> 0 then
            Logging.logError <| sprintf "Compiler failed. See logs in %s directory for more information. " compilerOutputDirPath
        return result.ExitCode
    }

module Fuzz =

    let DefaultFuzzingDurationHours = 1.0

    let SupportedCheckers =
        [
            "leakagerule"
            "resourcehierarchy"
            "useafterfree"
            "namespacerule"
            "invaliddynamicobject"
            "payloadbody"
            "examples"
            "*"
        ]

    let DefaultFuzzModeCheckerOptions =
        [
            ("--enable_checkers", "*")
            ("--disable_checkers", "namespacerule")
        ]

    let getPythonVersionString pythonExeName workingDirectory = async {
        let! versionStr = async {
            try
                let! result =
                    startProcessAsync
                        pythonExeName
                        "--version"
                        workingDirectory
                        (ProcessStartFlags.RedirectStandardError ||| ProcessStartFlags.RedirectStandardOutput)
                        NoTimeout
                        None
                if result.ExitCode = 0 then
                    return Some result.StandardOutput
                else
                    return None
            with ex ->
                return None
        }
        return versionStr
    }

    /// Gets the RESTler engine parameters common to any fuzzing mode
    let getCommonParameters (parameters:EngineParameters) maxDurationHours =

        [
            sprintf "--restler_grammar \"%s\"" parameters.grammarFilePath
            sprintf "--custom_mutations \"%s\"" parameters.mutationsFilePath
            sprintf "--set_version %s" CurrentVersion

            (match parameters.refreshableTokenOptions with
                | None -> ""
                | Some options ->
                    let refreshInterval =
                        if String.IsNullOrWhiteSpace options.refreshInterval then ""
                        else sprintf "--token_refresh_interval %s" options.refreshInterval
                    let refreshCommand =
                        match options.refreshCommand with
                        | UserSpecifiedCommand cmd ->
                            sprintf "--token_refresh_cmd \"%s\"" cmd
                    sprintf "%s %s" refreshInterval refreshCommand
            )
            (if parameters.producerTimingDelay > 0 then
                sprintf "--producer_timing_delay %d" parameters.producerTimingDelay
            else "")
            (if not parameters.useSsl then "--no_ssl" else "")
            (match parameters.host with
             | Some h -> sprintf "--host %s" h
             | None -> "")
            (match parameters.pathRegex with
             | Some r -> sprintf "--path_regex %s" r
             | None -> "")
            (if String.IsNullOrWhiteSpace parameters.settingsFilePath then ""
             else sprintf "--settings \"%s\"" parameters.settingsFilePath)

            // Checkers
            (if parameters.checkerOptions.Length > 0 then
                parameters.checkerOptions
                |> List.map (fun (x, y) -> sprintf "%s %s" x y)
                |> String.concat " "
            else "")
            (match maxDurationHours with
             | None -> ""
             | Some t ->
                sprintf "--time_budget %f" t)
            (match parameters.targetIp with
             | Some t -> sprintf "--target_ip %s" t
             | None -> "")
            (match parameters.targetPort with
             | Some t -> sprintf "--target_port %s" t
             | None -> "")
            // internal options
            "--include_user_agent"
            "--no_tokens_in_logs t"
            "--garbage_collection_interval 30"
        ]

    let runRestlerEngine workingDirectory engineArguments pythonFilePath = async {
        if not (File.Exists Paths.RestlerPyInstallerPath || File.Exists Paths.RestlerPyPath) then
            Trace.failwith "Could not find path to RESTler engine.  Please re-install RESTler or contact support."

        let restlerParameterCmdLine = engineArguments |> String.concat " "
        let pythonFilePaths =
            match pythonFilePath with
            | None ->
                match Platform.getOSPlatform() with
                | Platform.Platform.Linux ->
                    ["python3" ; "python"]
                | Platform.Platform.Windows ->
                    ["python.exe"]
            | Some p -> [p]

        let! validPythonFilePaths =
            pythonFilePaths
            |> List.map (fun fp ->
                            // Use the first python executable that can be successfully invoked
                            async {
                                let! versionString = getPythonVersionString fp workingDirectory
                                match versionString with
                                | None -> return None
                                | Some str ->
                                    return Some (fp, str)
                            })
            |> Async.Parallel

        let processName, commandArgs =
            if (File.Exists Paths.RestlerPyInstallerPath) then
                Paths.RestlerPyInstallerPath, restlerParameterCmdLine
            else
                match validPythonFilePaths |> Seq.choose (id) |> Seq.tryHead with
                | None ->
                    printfn "ERROR: python (%A) was not found on the path" pythonFilePaths
                    usage()
                | Some (pythonFilePath, versionString) ->
                    printfn "Using python: '%s' (%s)" pythonFilePath (versionString.Trim())
                    pythonFilePath, (sprintf "-B \"%s\" %s" Paths.RestlerPyPath restlerParameterCmdLine)

        let! result =
            startProcessAsync
                processName
                commandArgs
                workingDirectory
                (ProcessStartFlags.RedirectStandardError ||| ProcessStartFlags.RedirectStandardOutput)
                NoTimeout
                None
        File.WriteAllText(workingDirectory ++ "EngineStdErr.txt", result.StandardError)
        File.WriteAllText(workingDirectory ++ "EngineStdOut.txt", result.StandardOutput)
        if result.ExitCode <> 0 || result.StandardError.Length <> 0 then
            Logging.logError <| sprintf "Restler engine failed. See logs in %s directory for more information. " workingDirectory
        return result
    }

    /// Runs the results analyzer.  Note: the results analyzer searches for all
    /// logs in the specified root directory
    let runResultsAnalyzer fuzzingWorkingDirectory dictionaryFilePath = async {
        if not (File.Exists Paths.ResultsAnalyzerExePath) then
            Trace.failwith "Could not find path to RESTler results analyzer.  Please re-install RESTler or contact support."

        let outputDirPath = fuzzingWorkingDirectory ++ "ResponseBuckets"
        recreateDir outputDirPath
        let resultsAnalyzerParameters =
            [
                sprintf "analyze \"%s\"" fuzzingWorkingDirectory
                sprintf "--output_dir \"%s\"" outputDirPath
                sprintf "--dictionary_file \"%s\"" dictionaryFilePath
                "--max_instances_per_bucket 10"
            ]
        let resultsAnalyzerCmdLine = resultsAnalyzerParameters |> String.concat " "
        let! result =
            startProcessAsync
                "dotnet"
                (sprintf "\"%s\" %s" Paths.ResultsAnalyzerExePath resultsAnalyzerCmdLine)
                fuzzingWorkingDirectory
                (ProcessStartFlags.RedirectStandardError ||| ProcessStartFlags.RedirectStandardOutput)
                NoTimeout
                None

        File.WriteAllText(fuzzingWorkingDirectory ++ "ResultsAnalyzerStdErr.txt", result.StandardError)
        File.WriteAllText(fuzzingWorkingDirectory ++ "ResultsAnalyzerStdOut.txt", result.StandardOutput)
        if result.ExitCode <> 0 then
            Logging.logError <| sprintf "Results analyzer for logs in %s failed." fuzzingWorkingDirectory
        return result.ExitCode
    }

    let runSmokeTest workingDirectory (parameters:EngineParameters) pythonFilePath = async {
        let maxDurationHours =
            if parameters.maxDurationHours = float 0 then None
            else Some parameters.maxDurationHours

        let smokeTestParameters =
            (getCommonParameters parameters maxDurationHours)
            @
            [
                "--fuzzing_mode directed-smoke-test"
            ]

        return! runRestlerEngine workingDirectory smokeTestParameters pythonFilePath
    }

    let fuzz workingDirectory (parameters:EngineParameters) pythonFilePath = async {
        let maxDurationHours =
            if parameters.maxDurationHours = float 0 then DefaultFuzzingDurationHours
            else parameters.maxDurationHours

        let fuzzingParameters =
            (getCommonParameters parameters (Some maxDurationHours))
            @
            [
                "--fuzzing_mode bfs-cheap"
            ]

        return! runRestlerEngine workingDirectory fuzzingParameters pythonFilePath
    }

    let replayLog workingDirectory (parameters:EngineParameters) pythonFilePath = async {
        let replayLogFilePath =
            match parameters.replayLogFilePath with
            | None ->
                Logging.logError "ERROR: replay log must be specified in 'replay' mode."
                usage()
            | Some f -> f

        let fuzzingParameters =
            (getCommonParameters parameters None)
            @
            [
               sprintf "--replay_log %s" replayLogFilePath
            ]

        return! runRestlerEngine workingDirectory fuzzingParameters pythonFilePath
    }

/// Analyzes the checker arguments specified by the user and returns
/// the corresponding checker arguments that should be passed to the engine.
let getCheckerOptions defaultCheckerOptions userSpecifiedCheckerOptions =
    let defaultDisabledCheckers =
        match defaultCheckerOptions
            |> List.filter (fun (cmd,checkers) -> cmd = "--disable_checkers")
            |> List.map (fun (cmd,checkers) -> checkers)
            |> List.tryHead with
        | None -> ""
        | Some x -> x
    let engineCheckerOptions =
        match userSpecifiedCheckerOptions with
        | [] ->
            defaultCheckerOptions
        | [("--enable_checkers", ec)] ->
            // Enable only the user-specified checkers
            [
                ("--disable_checkers", "*")
                ("--enable_checkers", ec)
            ]
        | [("--disable_checkers", dc)] ->
            // Append the user's disable checkers to the default disable list.
            [
                ("--enable_checkers", "*")
                ("--disable_checkers", sprintf "%s %s" defaultDisabledCheckers dc)
            ]
        | _ ->
            Logging.logError <| sprintf "Error: command line contains several checker actions. \
                                         Either --enable_checkers or --disable_checkers may be specified once."
            usage()
    engineCheckerOptions

let rec parseEngineArgs task (args:EngineParameters) = function
    | [] ->
        // Check for unspecified parameters
        match task with
        | Compile ->
            failwith "Invalid function usage."
        | Test
        | FuzzLean
        | Fuzz ->
            if args.grammarFilePath = DefaultEngineParameters.grammarFilePath then
                Logging.logError <| sprintf "Grammar file path must be specified."
                usage()
            if args.mutationsFilePath = DefaultEngineParameters.mutationsFilePath then
                Logging.logError <| sprintf "Fuzzing dictionary file path must be specified."
                usage()
        | Replay ->
            if args.replayLogFilePath.IsNone then
                Logging.logError <| sprintf "Replay log file path must be specified."
                usage()
        args
    | "--grammar_file"::grammarFilePath::rest ->
        if not (File.Exists grammarFilePath) then
            Logging.logError <| sprintf "The RESTler grammar file path %s does not exist." grammarFilePath
            usage()
        parseEngineArgs task { args with grammarFilePath = Path.GetFullPath(grammarFilePath) } rest
    | "--dictionary_file"::mutationsFilePath::rest ->
        if not (File.Exists mutationsFilePath) then
            Logging.logError <| sprintf "The RESTler dictionary file path %s does not exist." mutationsFilePath
            usage()
        parseEngineArgs task  { args with mutationsFilePath = Path.GetFullPath(mutationsFilePath) } rest
    | "--target_ip"::targetIp::rest ->
        parseEngineArgs task { args with targetIp = Some targetIp } rest
    | "--target_port"::targetPort::rest ->
        parseEngineArgs task { args with targetPort = Some targetPort } rest
    | "--token_refresh_command"::refreshCommand::rest ->
        let parameters = UserSpecifiedCommand refreshCommand
        let options =
            match args.refreshableTokenOptions with
            | None ->
                { refreshInterval = "" ; refreshCommand = parameters }
            | Some options -> { options with refreshCommand = parameters }
        parseEngineArgs task { args with refreshableTokenOptions = Some options } rest
    | "--token_refresh_interval"::refreshInterval::rest ->
        let options =
            match args.refreshableTokenOptions with
            | None ->
                { refreshInterval = refreshInterval ; refreshCommand = UserSpecifiedCommand "" }
            | Some options -> { options with refreshInterval = refreshInterval }
        parseEngineArgs task { args with refreshableTokenOptions = Some options } rest
    | "--time_budget"::timeBudget::rest ->
        match Double.TryParse timeBudget with
        | true, h ->
            parseEngineArgs task { args with maxDurationHours = h } rest
        | false, _ ->
            Logging.logError <| sprintf "Invalid argument for time_budget: %s" timeBudget
            usage()
    | "--producer_timing_delay"::delaySeconds::rest ->
        match Int32.TryParse delaySeconds with
        | true, s ->
            parseEngineArgs task { args with producerTimingDelay = s } rest
        | false, _ ->
            Logging.logError <| sprintf "Invalid argument for producer_timing_delay: %s" delaySeconds
            usage()
    | "--no_ssl"::rest ->
        parseEngineArgs task { args with useSsl = false } rest
    | "--host"::host::rest->
        parseEngineArgs task { args with host = Some host } rest
    | "--settings"::settingsFilePath::rest ->
        if not (File.Exists settingsFilePath) then
            Logging.logError <| sprintf "The RESTler settings file path %s does not exist." settingsFilePath
            usage()
        parseEngineArgs task { args with settingsFilePath = Path.GetFullPath(settingsFilePath) } rest
    | "--path_regex"::pathRegex::rest ->
        parseEngineArgs task { args with pathRegex = Some pathRegex } rest
    | "--replay_log"::replayLogFilePath::rest ->
        if not (File.Exists replayLogFilePath) then
            Logging.logError <| sprintf "The replay log file path %s does not exist." replayLogFilePath
            usage()
        parseEngineArgs task { args with replayLogFilePath = Some (Path.GetFullPath(replayLogFilePath)) } rest
    | checkerAction::checkers::rest when
        (checkerAction = "--enable_checkers" || checkerAction = "--disable_checkers") ->
        let specifiedCheckers = checkers.Split([|','|], StringSplitOptions.RemoveEmptyEntries)
        // Check for invalid options
        specifiedCheckers
        |> Array.iter (fun x ->
                        let valid = Fuzz.SupportedCheckers |> Seq.contains x
                        if not valid then
                            Logging.logWarning <| sprintf "Unknown checker %s specified. If this is a custom checker, ignore this message." x
                      )
        parseEngineArgs task { args with checkerOptions = args.checkerOptions @ [(checkerAction, specifiedCheckers |> String.concat " ")] } rest
    | "no_results_analyzer"::rest ->
        parseEngineArgs task { args with runResultsAnalyzer = false } rest
    | invalidArgument::rest ->
        Logging.logError <| sprintf "Invalid argument: %s" invalidArgument
        usage()

let rec parseArgs (args:DriverArgs) = function
    | [] ->
        args
    | "--version"::_ ->
        printfn "RESTler version: %s" CurrentVersion
        exit 0
    | "--disable_log_upload"::rest ->
        Logging.logWarning "Log upload will be disabled.  Logs will only be written locally in the working directory."
        parseArgs { args with logsUploadRootDirectoryPath = None } rest
    | "--logsUploadRootDirPath"::logsUploadDirPath::rest ->
        if not (Directory.Exists logsUploadDirPath) then
            Logging.logError <| sprintf "Directory %s does not exist." logsUploadDirPath
            usage()
        parseArgs { args with logsUploadRootDirectoryPath = Some logsUploadDirPath } rest
    | "--python_path"::pythonFilePath::rest ->
        if not (File.Exists pythonFilePath) then
            Logging.logError <| sprintf "The specified python path %s does not exist." pythonFilePath
            usage()
        parseArgs { args with pythonFilePath = Some pythonFilePath } rest
    | "compile"::"--api_spec"::swaggerSpecFilePath::rest ->
        if not (File.Exists swaggerSpecFilePath) then
            Logging.logError <| sprintf "API specification file %s does not exist." swaggerSpecFilePath
            usage()
        let swaggerSpecAbsFilePath = Restler.Config.convertToAbsPath Environment.CurrentDirectory swaggerSpecFilePath

        let config = { Restler.Config.DefaultConfig with
                        SwaggerSpecFilePath = Some [ swaggerSpecAbsFilePath ]
                        IncludeOptionalParameters = true
                        // Data fuzzing is on by default here because data fuzzing is on by default
                        // in the RESTler engine for fuzzing.
                        DataFuzzing = true
                     }
        parseArgs { args with task = Compile ; taskParameters = CompilerParameters config } rest

    | "compile"::compilerConfigFilePath::rest ->

        if not (File.Exists compilerConfigFilePath) then
            Logging.logError <| sprintf "File %s does not exist." compilerConfigFilePath
            usage()

        match Microsoft.FSharpLu.Json.Compact.tryDeserializeFile<Restler.Config.Config> compilerConfigFilePath with
        | Choice1Of2 config->
            let config = Restler.Config.convertRelativeToAbsPaths compilerConfigFilePath config
            let config = { config with
                                UseQueryExamples = if config.UseQueryExamples.IsSome then
                                                       config.UseQueryExamples
                                                   else Restler.Config.DefaultConfig.UseQueryExamples
                                UseBodyExamples = if config.UseBodyExamples.IsSome then
                                                      config.UseBodyExamples
                                                  else Restler.Config.DefaultConfig.UseBodyExamples
                                IncludeOptionalParameters = true }
            parseArgs { args with task = Compile ; taskParameters = CompilerParameters config } rest
        | Choice2Of2 error ->
            Logging.logError <| sprintf "Invalid format for compiler config file %s. \
                                         Please refer to the documentation for the compiler config file format."
                                         compilerConfigFilePath
            Logging.logError <| sprintf "Deserialization exception: %A" (error.Split('\n') |> Seq.head)
            usage()
    | "test"::rest ->
        let engineParameters = parseEngineArgs RestlerTask.Test DefaultEngineParameters rest
        let engineParameters =
            { engineParameters with
                  checkerOptions = getCheckerOptions [] engineParameters.checkerOptions }
        { args with task = Test
                    taskParameters = EngineParameters engineParameters}
    | "fuzz"::rest ->
        let engineParameters = parseEngineArgs RestlerTask.Fuzz DefaultEngineParameters rest

        let engineParameters =
            { engineParameters with
                checkerOptions = getCheckerOptions Fuzz.DefaultFuzzModeCheckerOptions engineParameters.checkerOptions }
        { args with task = Fuzz
                    taskParameters = EngineParameters engineParameters}
    | "fuzz-lean"::rest ->
        // Fuzz-lean is 'test' with all checkers except the namespace checker turned on.
        let engineParameters = parseEngineArgs RestlerTask.Test DefaultEngineParameters rest
        let engineParameters =
            { engineParameters with
                  checkerOptions = getCheckerOptions Fuzz.DefaultFuzzModeCheckerOptions engineParameters.checkerOptions }
        { args with task = FuzzLean
                    taskParameters = EngineParameters engineParameters}
    | "replay"::rest ->
        let engineParameters = parseEngineArgs RestlerTask.Replay DefaultEngineParameters rest
        let engineParameters = { engineParameters with
                                    checkerOptions = getCheckerOptions Fuzz.DefaultFuzzModeCheckerOptions engineParameters.checkerOptions }
        { args with task = Replay
                    taskParameters = EngineParameters engineParameters}
    | invalidArgument::_ ->
        Logging.logError <| sprintf "Invalid argument: %s" invalidArgument
        usage()

let getConfigValue key =
    match System.AppContext.GetData(key) with
    | s when isNull s -> None
    | s when String.IsNullOrEmpty (s.ToString()) -> None
    | s ->
        Some (s.ToString())

let getDataFromTestingSummary taskWorkingDirectory =
    let bugBucketCounts, specCoverageCounts =
        // Read the bug buckets file
        let bugBucketsFiles = Directory.GetFiles(taskWorkingDirectory, "testing_summary.json", SearchOption.AllDirectories)
        match bugBucketsFiles |> Seq.tryHead with
        | None ->
            Logging.logInfo <| "Testing summary was not found."
            [], []
        | Some testingSummaryFilePath ->
            let testingSummary =
                Microsoft.FSharpLu.Json.Compact.deserializeFile<Engine.TestingSummary> testingSummaryFilePath

            Logging.logInfo <| sprintf "Request coverage (successful / total): %s" testingSummary.final_spec_coverage

            let bugBuckets = testingSummary.bug_buckets
                                |> Seq.map (fun kvp -> kvp.Key, sprintf "%A" kvp.Value)
                                |> Seq.toList
            if bugBuckets.Length > 0 then
                Logging.logInfo <| "Bugs were found!"
                Logging.logInfo <| "Bug buckets:"
                let bugBucketsFormatted =
                    bugBuckets
                    |> List.fold (fun str (x,y) -> str + (sprintf "\n%s: %s" x y)) ""

                Logging.logInfo <| sprintf "%s" bugBucketsFormatted
            else
                Logging.logInfo <| "No bugs were found."

            let coveredRequests, totalRequests =
                let finalCoverageValues =
                    testingSummary.final_spec_coverage.Split("/")
                                        |> Array.map (fun x -> x.Trim())
                Int32.Parse(finalCoverageValues.[0]),
                Int32.Parse(finalCoverageValues.[1])
            let totalMainDriverRequestsSent =
                match testingSummary.total_requests_sent.TryGetValue("main_driver") with
                | (true, v ) -> v
                | (false, _ ) -> 0

            let requestStats =
                [
                    "total_executed_requests_main_driver", totalMainDriverRequestsSent
                    "covered_spec_requests", coveredRequests
                    "total_spec_requests", totalRequests
                ]
                |> List.map (fun (x,y) -> x, sprintf "%A" y)
            (requestStats, bugBuckets)
    {|
        bugBucketCounts = bugBucketCounts
        specCoverageCounts = specCoverageCounts
    |}

let tryRecreateDir dirPath =
    if Directory.Exists dirPath then
        try
            Directory.Delete(dirPath, true)
        with
        | :? UnauthorizedAccessException
        | :? IOException as ex ->
            let message = sprintf "The directory %s cannot be deleted.\n\
                                   Please check for files you have opened from that directory,\
                                   close them, and re-try RESTler."
                                  dirPath
            Logging.logError <| message
            exitRestler 1

    Directory.CreateDirectory(dirPath) |> ignore

[<EntryPoint>]
let main argv =
    let logsDirPath = Environment.CurrentDirectory ++ "RestlerLogs"
    tryRecreateDir logsDirPath

    use tracing = System.Diagnostics.Listener.registerFileTracer
                        "restler"
                        (Some logsDirPath)

    Console.CancelKeyPress.Add(fun arg ->
                                    Trace.info "Ctrl-C intercepted. Long running tasks should have exited. Uploading logs."
                                    arg.Cancel <- true
                               )

    if argv.Length = 0 then
        usage()

    let logShareDirPath = getConfigValue LogCollection.RestlerLogShareSettingsKey

    let args = parseArgs { outputDirPath = logsDirPath
                           task = Compile
                           taskParameters = Undefined
                           workingDirectoryPath = Environment.CurrentDirectory
                           logsUploadRootDirectoryPath = logShareDirPath
                           pythonFilePath = None
                         }
                         (argv |> Array.toList)

    // Instrumentation key is from the app insights resource in Azure Portal
    let instrumentationKey =
        let optOutFromTelemetry = Telemetry.getMicrosoftOptOut()
        if optOutFromTelemetry then
            // Telemetry does not get sent if the instrumentation key is an empty string
            String.Empty
        else
            match getConfigValue Telemetry.AppInsightsInstrumentationSettingsKey with
            | None -> Restler.Telemetry.InstrumentationKey
            | Some key -> key
    let machineId = Telemetry.getMachineId()
    use telemetryClient = new TelemetryClient(machineId, instrumentationKey)

    // Run task
    let runRestlerTask executionId taskName = async {
        let taskWorkingDirectory = args.workingDirectoryPath ++ taskName
        tryRecreateDir taskWorkingDirectory
        let logsUploadDirPath =
            match args.logsUploadRootDirectoryPath with
            | None -> None
            | Some rootDir ->
                Logging.logInfo <| sprintf "Log share was specified.  Logs will be uploaded to %s." rootDir
                Some (sprintf "%s_%s" (LogCollection.getLogsDirPath rootDir) taskName)

        try
            if logsUploadDirPath.IsSome then
                Logging.logInfo <| sprintf "Uploading input files..."
                LogCollection.uploadInputs args logsUploadDirPath.Value "task_inputs" usage
        with e ->
            Logging.logError <| sprintf "Log upload failed, please contact support.  Upload directory: %A, exception: %A"
                                        logsUploadDirPath e

        // Run the specified task
        let! result = async {
            try
                Logging.logInfo <| sprintf "Starting task %A..." args.task
                telemetryClient.RestlerStarted(CurrentVersion, taskName, executionId, [])

                match args.task, args.taskParameters with
                | Compile, CompilerParameters p ->
                    let! result = Compile.invokeCompiler taskWorkingDirectory p
                    return
                        {|
                            taskResult = result
                            analyzerResult = None
                            testingSummary = None
                        |}
                | Test, EngineParameters p
                | FuzzLean, EngineParameters p ->
                    let! result = Fuzz.runSmokeTest taskWorkingDirectory p args.pythonFilePath
                    let! analyzerResult = async {
                        if p.runResultsAnalyzer then
                            let! analyzerResult = Fuzz.runResultsAnalyzer taskWorkingDirectory p.mutationsFilePath
                            return Some analyzerResult
                        else
                            return None
                    }
                    let exitCode =
                        if result.ExitCode = 0 && result.StandardError.Length <> 0 then
                            EngineErrorCode
                        else
                            result.ExitCode
                    let testingSummary =
                        if exitCode = 0 then
                            getDataFromTestingSummary taskWorkingDirectory |> Some
                        else None

                    return
                        {|
                            taskResult = exitCode
                            analyzerResult = analyzerResult
                            testingSummary = testingSummary
                        |}

                | Fuzz, EngineParameters p ->
                    let! result =  Fuzz.fuzz taskWorkingDirectory p args.pythonFilePath
                    let! analyzerResult = async {
                        if p.runResultsAnalyzer then
                            let! analyzerResult = Fuzz.runResultsAnalyzer taskWorkingDirectory p.mutationsFilePath
                            return Some analyzerResult
                        else
                            return None
                    }
                    let exitCode =
                        if result.ExitCode = 0 && result.StandardError.Length <> 0 then
                            EngineErrorCode
                        else
                            result.ExitCode
                    let testingSummary =
                        if exitCode = 0 then
                            getDataFromTestingSummary taskWorkingDirectory |> Some
                        else None

                    return
                        {|
                            taskResult = exitCode
                            analyzerResult = analyzerResult
                            testingSummary = testingSummary
                        |}
                | Replay, EngineParameters p ->
                    let! result = Fuzz.replayLog taskWorkingDirectory p args.pythonFilePath
                    return
                        {|
                            taskResult = result.ExitCode
                            analyzerResult = None
                            testingSummary = None
                        |}
                | _,_ ->
                    telemetryClient.RestlerStarted(CurrentVersion, "invalid arguments", executionId, [])
                    // The application should have validated user arguments and exited by this point
                    // if user-specified arguments were incorrect.  This is considered a bug.
                    Trace.failwith "Invalid driver arguments: %A." args
                    return // Required for compilation.
                        {|
                            taskResult = -1
                            analyzerResult = None
                            testingSummary = None
                        |}

            with e ->
                Logging.logError <| sprintf "Task %A failed.  Exception: %A" args.task e
                return
                    {|
                        taskResult = 1
                        analyzerResult = None
                        testingSummary = None
                    |}
        }

        Logging.logInfo <| sprintf "Task %A %s." args.task (if result.taskResult = 0 then "succeeded" else "failed")

        let bugBucketCounts, specCoverageCounts =
            match result.testingSummary with
            | None -> [], []
            | Some s -> s.bugBucketCounts, s.specCoverageCounts
        telemetryClient.RestlerFinished(CurrentVersion, taskName, executionId, result.taskResult,
                                        bugBucketCounts, specCoverageCounts)

        if result.analyzerResult.IsSome then
            telemetryClient.ResultsAnalyzerFinished(CurrentVersion, taskName, executionId, result.analyzerResult.Value)

        try
            Logging.logInfo <| sprintf "Collecting logs..."
            Trace.flush()
            // Copy the log files to the task working directory, so there is only one directory to upload.
            let logFiles = Directory.GetFiles(logsDirPath, "restler*", SearchOption.TopDirectoryOnly);
            logFiles |> Array.iter (fun filePath -> File.Copy(filePath, taskWorkingDirectory ++ Path.GetFileName(filePath)))
            if logsUploadDirPath.IsSome then
                Logging.logInfo <| sprintf "Uploading logs..."
                LogCollection.uploadLogs args.workingDirectoryPath taskWorkingDirectory logsUploadDirPath.Value "task_logs"
        with e ->
            Logging.logError <| sprintf "Log upload failed, please contact support.  Upload directory: %A, exception: %A" logsUploadDirPath e
    }

    let executionId = System.Guid.NewGuid()
    let taskName = args.task.ToString()
    try
        async {
            do! runRestlerTask executionId taskName
        }
        |> Async.RunSynchronously
    with e ->
        // Report that an error occurred in telemetry
        telemetryClient.RestlerDriverFailed(CurrentVersion, taskName, executionId)
        reraise()
    0

