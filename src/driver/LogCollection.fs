// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/// Log collection for RESTler logs.

namespace Restler.Driver

open System
open System.IO
open Microsoft.FSharpLu.File
open Microsoft.FSharpLu.Logging
open Restler.Driver.Types
open Restler.Driver.Files

module LogCollection =

    [<Literal>]
    let RestlerLogShareSettingsKey = "restlerLogsUploadDirectory"

    [<Literal>]
    let RestlerTelemetryShareAccessRetryCount = 10

    [<Literal>]
    let RestlerTelemetryShareAccessRetryDelaySeconds = 2

    /// The log directory used for this invocation.  Example format: 01-24-2019_090535PM_username_Test
    let getLogsDirPath rootDir =
        let userName =
            match System.Environment.UserName with
            | name when String.IsNullOrEmpty name ->
                let id = (new Random()).Next()
                sprintf "unnamed_%d" id
            | name -> name
        let dateFormat = "MM-dd-yyyy_hhmmsstt";

        let timeStamp = DateTime.UtcNow.ToString(dateFormat)
        rootDir ++ (sprintf "%s_%s" (timeStamp.ToString()) userName)

    let uploadInputs (driverArgs:DriverArgs) targetPath logFileName handleFailure =
        createDirectoryWithRetries
            targetPath
            RestlerTelemetryShareAccessRetryCount
            []
            (TimeSpan.FromSeconds(float RestlerTelemetryShareAccessRetryDelaySeconds))
            false

        let checkFileExistsWithUserMessage filePath fileDescription =
            if not (File.Exists filePath) then
                Logging.logError <| sprintf "%s file %s does not exist." fileDescription filePath
                handleFailure()
                false
            else true

        let inputs = System.Collections.Generic.List<string * string>()
        let addInput filePath fileDescription =
            let f = (filePath, fileDescription)
            inputs.Add(f)

        match driverArgs.task, driverArgs.taskParameters with
        | Compile, CompilerParameters p ->
            match p.SwaggerSpecFilePath with
            | None ->
                match p.GrammarInputFilePath with
                | None ->
                    // Neither a Swagger nor grammar is specified.  This is an error.
                    Logging.logError <| sprintf "Either a Swagger or grammar must be specified to be compiled."
                    handleFailure()
                | Some grammarFilePath ->
                    addInput grammarFilePath "Fuzzing grammar"
            | Some swaggerSpecsFilePath ->
                swaggerSpecsFilePath
                |> Seq.iter (fun filePath ->
                                    addInput filePath "Swagger spec")
            match p.CustomDictionaryFilePath with
            | None ->
                // Nothing to upload, default dictionary will be used.
                ()
            | Some dictionaryFilePath ->
                addInput dictionaryFilePath "Fuzzing dictionary"
            match p.EngineSettingsFilePath with
            | None ->
                // Nothing to upload, engine settings are not required for the compile phase.
                ()
            | Some engineSettingsFilePath ->
                addInput engineSettingsFilePath "Engine settings"
        | Test, EngineParameters p
        | FuzzLean, EngineParameters p
        | Fuzz, EngineParameters p ->
            addInput p.grammarFilePath "Python Grammar"
            let grammarJsonFilePath =
                Path.GetDirectoryName(p.grammarFilePath) ++ Path.GetFileNameWithoutExtension(p.grammarFilePath) + ".json"
            addInput grammarJsonFilePath "Json Grammar"
            addInput p.mutationsFilePath "Fuzzing dictionary"
            // engine settings are not yet required for the test phase.
            if not(String.IsNullOrEmpty p.settingsFilePath) then
                addInput p.settingsFilePath "Engine settings"
                // If the payload body checker is specified, copy the recipe file
                match Restler.Engine.Settings.getEngineSettings p.settingsFilePath with
                | Error msg ->
                    Logging.logError <| sprintf "Error reading engine settings: %s" p.settingsFilePath
                    handleFailure()
                | Ok engineSettings ->
                    match engineSettings.getBodyPayloadRecipeFilePath() with
                    | None -> ()
                    | Some bodyCheckerRecipeFilePath ->
                        // Allow the recipe file path to be empty, for cases when the payload body checker is
                        // not turned on (since the driver does not determine which checkers are on).
                        if not (String.IsNullOrEmpty bodyCheckerRecipeFilePath) then
                            addInput bodyCheckerRecipeFilePath "Payload fuzzing recipe"
        | Replay, EngineParameters p ->
            match p.replayLogFilePath with
            | None -> ()
            | Some replayLogFile ->
                addInput replayLogFile "Replay log"
                // engine settings are not yet required for the test phase.
                if not(String.IsNullOrEmpty p.settingsFilePath) then
                    addInput p.settingsFilePath "Engine settings"
        | _,_ ->
            Trace.failwith "Invalid driver arguments: %A" driverArgs

        let existingFiles =
            inputs
            |> Seq.filter (fun (fileName, fileDescription) -> checkFileExistsWithUserMessage fileName fileDescription)
            |> Seq.map (fun (filePath, fileDescription) -> filePath)

        zipFilesAndUpload driverArgs.workingDirectoryPath
            existingFiles
            targetPath
            logFileName
            RestlerTelemetryShareAccessRetryCount
            (TimeSpan.FromSeconds(float RestlerTelemetryShareAccessRetryDelaySeconds))

    let uploadLogs workingDirectory logsDirectoryPath targetPath logFileName =
        if not (Directory.Exists logsDirectoryPath) then
            Trace.failwith "Logs directory for task should exist after running the task."
        uploadDirectory
            workingDirectory
            logsDirectoryPath
            targetPath
            logFileName
            RestlerTelemetryShareAccessRetryCount
            (TimeSpan.FromSeconds(float RestlerTelemetryShareAccessRetryDelaySeconds))


