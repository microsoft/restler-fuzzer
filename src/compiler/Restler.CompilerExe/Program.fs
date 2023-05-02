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

// Make sure NewtOnSoft.Json is loaded with a higher than default MaxDepth limit, which
// is required by some OpenAPI specifications
open Newtonsoft.Json
JsonConvert.DefaultSettings <- fun () -> JsonSerializerSettings(MaxDepth = 128)


[<EntryPoint>]
let main argv =

    let config =
        match argv with
        | [|configFilePath|] ->
            if File.Exists configFilePath then
                let config = Restler.Utilities.JsonSerialization.deserializeFile<Config> configFilePath
                let config =
                    match config.GrammarOutputDirectoryPath with
                    | None ->
                        raise (exn("'GrammarOutputDirectoryPath' must be specified in the config file."))
                    | Some _ -> config
                convertRelativeToAbsPaths configFilePath config
            else
                printfn "Path not found: %s" configFilePath
                exit 1
        | _ ->
            usage()
            exit 1


    Restler.Workflow.generateRestlerGrammar config
    0