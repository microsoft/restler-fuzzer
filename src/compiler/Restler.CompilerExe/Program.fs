// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/// Main program to analyze a Swagger specification and generate a RESTler fuzzing grammar

open Microsoft.FSharpLu
open Restler.Config
open System.IO

let usage() =
    printfn "Usage: dotnet RestlerCompilerExe.dll <path to config file>"
    let sampleConfig = Json.Compact.serialize SampleConfig
    printfn "Sample config:\n %s" sampleConfig

[<EntryPoint>]
let main argv =

    let config =
        match argv with
        | [|configFilePath|] ->
            if File.Exists configFilePath then
                let config = Json.Compact.deserializeFile<Config> configFilePath
                let config =
                    match config.GrammarOutputDirectoryPath with
                    | None -> { config with GrammarOutputDirectoryPath = Some System.Environment.CurrentDirectory }
                    | Some _ -> config
                convertRelativeToAbsPaths configFilePath config
            else
                printfn "Path not found: %s" configFilePath
                exit 1
        | _ ->
            usage()
            exit 1


    Restler.Workflow.generateRestlerGrammar None config
    0