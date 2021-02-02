// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.Workflow

open System.IO
open Restler.Config
open Restler.Engine.Settings
open Restler.Utilities.Logging
open Restler.Compiler.Main.Types
open System
open Restler.Grammar

module Constants =
    let DefaultJsonGrammarFileName = "grammar.json"
    let DefaultRestlerGrammarFileName = "grammar.py"
    let NewDictionaryFileName = "dict.json"
    let UnresolvedDependenciesFileName = "unresolved_dependencies.json"
    let DependenciesFileName = "dependencies.json"
    let DependenciesDebugFileName = "dependencies_debug.json"
    let DefaultExampleMetadataFileName = "examples.json"
    let DefaultEngineSettingsFileName = "engine_settings.json"

let generatePython grammarOutputDirectoryPath config grammar =
    let codeFile = Path.Combine(grammarOutputDirectoryPath, Constants.DefaultRestlerGrammarFileName)
    use stream = System.IO.File.CreateText(codeFile)
    Restler.CodeGenerator.Python.generateCode grammar config.IncludeOptionalParameters stream.Write


let getSwaggerDataForDoc doc workingDirectory =
    let swaggerDoc = Restler.Swagger.getSwaggerDocument doc.SpecFilePath workingDirectory
    let globalAnnotations =
        match doc.AnnotationFilePath with
        | None -> None
        | Some fp when File.Exists fp ->
            Annotations.getGlobalAnnotationsFromFile fp |> Some
        | Some fp ->
            printfn "ERROR: invalid path found in the list of annotation files given: %A" fp
            raise (ArgumentException("invalid annotation file path"))
    let dictionary =
        match doc.DictionaryFilePath, doc.Dictionary with
        | None, None -> None
        | Some fp, None ->
            if File.Exists fp then
                match Dictionary.getDictionary fp with
                | Ok d -> Some d
                | Error msg ->
                    printfn "ERROR: invalid dictionary file %s, error: %s" fp msg
                    raise (ArgumentException(msg))
            else
                printfn "ERROR: invalid path found in the list of dictionary files given: %A" fp
                raise (ArgumentException("invalid dictionary file path"))
        | None, Some dictionaryText ->
            match Dictionary.getDictionaryFromString dictionaryText with
            | Ok d -> Some d
            | Error msg ->
                printfn "ERROR: invalid inline dictionary %s, error: %s" dictionaryText msg
                raise (ArgumentException(msg))
        | Some _, Some _ ->
            let error = sprintf "invalid dictionary specified for Swagger file: %s" doc.SpecFilePath
            printfn "ERROR: specify either a dictionary file or inline dictionary."
            raise (ArgumentException(error))


    {   swaggerDoc = swaggerDoc
        dictionary = dictionary
        globalAnnotations = globalAnnotations
    }   

let generateGrammarFromSwagger grammarOutputDirectoryPath swaggerDoc config =

    // Extract the Swagger documents and corresponding document-specific configuration, if any
    let swaggerDocs =
        match swaggerDoc with
        | Some s -> [ s ]
        | None ->
            match config.SwaggerSpecFilePath with
            | None ->
                if config.SwaggerSpecConfig.IsNone then
                    printfn "ERROR: must specify Swagger or grammar file."
                    raise (ArgumentException("unspecified API spec file path"))
                else
                    // Swagger specified in config.  handled below.
                    []
            | Some swaggerSpecFilePaths when swaggerSpecFilePaths
                                             |> Seq.forall (fun fp -> File.Exists fp) ->
                swaggerSpecFilePaths
                |> List.map (fun fp -> Restler.Swagger.getSwaggerDocument fp grammarOutputDirectoryPath)
            | Some p ->
                printfn "ERROR: invalid path found in the list of Swagger specs given: %A" p
                raise (ArgumentException(sprintf "invalid API spec file path found: %A" p))

    let docsWithEmptyConfig =
        swaggerDocs
        |> List.map (fun x ->
                        {   swaggerDoc = x
                            dictionary = None
                            globalAnnotations = None
                        })

    let configuredSwaggerDocs =
        match config.SwaggerSpecConfig with
        | None ->
            if swaggerDocs.Length = 0 then
                printfn "ERROR: must specify at least one Swagger or grammar file."
                raise (ArgumentException("unspecified API spec file path"))
            else
                docsWithEmptyConfig
        | Some docs when docs |> Seq.forall (fun doc -> File.Exists doc.SpecFilePath) ->
            let configuredDocs =
                docs
                |> List.map (fun doc -> getSwaggerDataForDoc doc grammarOutputDirectoryPath)
            docsWithEmptyConfig @ configuredDocs
        | Some docs ->
            printfn "ERROR: invalid path found in the list of Swagger configurations given: %A" docs
            raise (ArgumentException(sprintf "invalid API spec file path found: %A" docs))

    let dictionary =
        match config.CustomDictionaryFilePath with
        | None ->
            Restler.Dictionary.DefaultMutationsDictionary
        | Some dictionaryFilePath ->
            match Restler.Dictionary.getDictionary dictionaryFilePath with
            | Ok d ->
                // Initialize required uuid4_suffix field, in case the customer did not specify it.
                match d.restler_custom_payload_uuid4_suffix with
                | Some _ -> d
                | None ->
                    { d with restler_custom_payload_uuid4_suffix = Some (Map.empty<string, string>) }
            | Error e ->
                raise (ArgumentException(sprintf "Could not read dictionary: %s" e))

    let globalExternalAnnotations =
        match config.AnnotationFilePath with
        | None -> List.empty
        | Some fp when File.Exists fp ->
            Annotations.getGlobalAnnotationsFromFile fp
        | Some fp ->
            printfn "ERROR: invalid global annotation file given: %A" fp
            raise (ArgumentException("invalid annotation file path"))

    let examplesDirectory =
        if String.IsNullOrEmpty config.ExamplesDirectory then
            Path.Combine(grammarOutputDirectoryPath, "examples")
        else config.ExamplesDirectory

    if config.DiscoverExamples then
        Microsoft.FSharpLu.File.recreateDir examplesDirectory


    let grammar, dependencies, (newDictionary, perResourceDictionaries), examples =
        Restler.Compiler.Main.generateRequestGrammar
                        configuredSwaggerDocs
                        dictionary
                        { config with ExamplesDirectory = examplesDirectory }
                        globalExternalAnnotations

    let grammarFilePath = Path.Combine(grammarOutputDirectoryPath, Constants.DefaultJsonGrammarFileName)

    use fs = new Restler.Utilities.Stream.FileStreamWithoutPreamble(grammarFilePath, IO.FileMode.Create)
    Microsoft.FSharpLu.Json.Compact.serializeToStream fs grammar
    fs.Flush()
    fs.Dispose()
    // The below statement is present as an assertion, to check for deserialization issues for
    // specific grammars.

    let ignoreStream = new System.IO.MemoryStream()
    Microsoft.FSharpLu.Json.Compact.deserializeStream<GrammarDefinition>(ignoreStream)
    |> ignore

    let examplesFilePath = Path.Combine(grammarOutputDirectoryPath, Constants.DefaultExampleMetadataFileName)
    Microsoft.FSharpLu.Json.Compact.serializeToFile examplesFilePath examples

    // Write the updated dictionary.
    let writeDictionary dictionaryName newDict =
        let newDictionaryFilePath = System.IO.Path.Combine(grammarOutputDirectoryPath, dictionaryName)
        printfn "Writing new dictionary to %s" newDictionaryFilePath
        Microsoft.FSharpLu.Json.Compact.serializeToFile newDictionaryFilePath newDict
    writeDictionary Constants.NewDictionaryFileName newDictionary

    // Write the per-resource dictionaries.
    perResourceDictionaries
    |> Map.toSeq
    |> Seq.map snd
    // The per-resource dictionaries are expected to be read-only.
    // TODO: add assertion.
    |> Seq.distinctBy(fun (dictName, _) -> dictName)
    |> Seq.iter (fun (dictName, dictContents) ->
                    writeDictionary (sprintf "%s.json" dictName) dictContents)

    let unresolvedDependenciesFilePath = Path.Combine(grammarOutputDirectoryPath, Constants.UnresolvedDependenciesFileName)
    Dependencies.writeDependencies unresolvedDependenciesFilePath dependencies true
    let dependenciesFilePath = Path.Combine(grammarOutputDirectoryPath, Constants.DependenciesFileName)
    Dependencies.writeDependencies dependenciesFilePath dependencies false

    let dependenciesDebugFilePath = Path.Combine(grammarOutputDirectoryPath, Constants.DependenciesDebugFileName)
    let dependenciesSorted =
        dependencies
        |> List.sortBy (fun x -> x.consumer.id.RequestId, x.consumer.id.AccessPath)
    Dependencies.writeDependenciesDebug dependenciesDebugFilePath dependenciesSorted

    // Update engine settings
    let newEngineSettingsFilePath =
       System.IO.Path.Combine(grammarOutputDirectoryPath, Constants.DefaultEngineSettingsFileName)
    let perResourceDictionaryFileNames =
        perResourceDictionaries
        |> Map.map (fun k (dictName, dict) ->
                            dictName)

    let updateEngineSettingsResult = updateEngineSettings grammar.Requests
                                            perResourceDictionaryFileNames
                                            config.EngineSettingsFilePath
                                            grammarOutputDirectoryPath
                                            newEngineSettingsFilePath
    match updateEngineSettingsResult with
    | Ok () -> ()
    | Error message ->
        printfn "%s" message
        exit 1

    grammar

let generateRestlerGrammar swaggerDoc (config:Config) =
    let grammarOutputDirectoryPath =
        match config.GrammarOutputDirectoryPath with
        | Some p -> p
        | None ->
            raise (ArgumentException("GrammarOutputDirectoryPath must be specified in the config"))

    Microsoft.FSharpLu.File.createDirIfNotExists grammarOutputDirectoryPath

    let grammar =
        match config.GrammarInputFilePath with
        | Some grammarFilePath when File.Exists grammarFilePath ->
            use f = System.IO.File.OpenRead(grammarFilePath)
            Microsoft.FSharpLu.Json.Compact.deserializeStream<GrammarDefinition> f
        | None ->
             logTimingInfo "Generating grammar..."
             generateGrammarFromSwagger grammarOutputDirectoryPath swaggerDoc config
        | Some p ->
            printfn "ERROR: invalid path for grammar: %s" p
            exit 1

    logTimingInfo "Generating python grammar..."
    generatePython grammarOutputDirectoryPath config grammar
    logTimingInfo "Done generating python grammar."

    printfn "Workflow completed.  See %s for REST-ler grammar." grammarOutputDirectoryPath
