// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.Workflow

open System.IO
open Restler.Config
open Restler.Engine.Settings
open Restler.Utilities
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
    let CustomValueGeneratorTemplateFileName = "custom_value_gen_template.py"
    let DefaultAnnotationFileName = "annotations.json"
    let DefaultCompilerConfigName = "config.json"

let generatePython grammarOutputDirectoryPath config grammar =
    let codeFile = Path.Combine(grammarOutputDirectoryPath, Constants.DefaultRestlerGrammarFileName)
    use stream = System.IO.File.CreateText(codeFile)
    Restler.CodeGenerator.Python.generateCode grammar config.IncludeOptionalParameters stream.Write


let getSwaggerDataForDoc doc workingDirectory =
    let swaggerDoc, preprocessingResult = Restler.Swagger.getSwaggerDocument doc.SpecFilePath workingDirectory
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
        xMsPathsMapping = if preprocessingResult.IsSome then preprocessingResult.Value.xMsPathsMapping else None
    }


let generateGrammarFromSwagger grammarOutputDirectoryPath config =

    // Extract the Swagger documents and corresponding document-specific configuration, if any
    let swaggerSpecConfigs = getSwaggerSpecConfigsFromCompilerConfig config

    let configuredSwaggerDocs =
        swaggerSpecConfigs
        |> List.map (fun doc -> getSwaggerDataForDoc doc grammarOutputDirectoryPath)

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

    let userSpecifiedExamples =
        let getExampleConfigFile filePath exactCopy =
            match filePath with
            | None -> None
            | Some fp when File.Exists fp ->
                match Examples.tryDeserializeExampleConfigFile fp with
                | Some ef -> Some { ef with exactCopy = exactCopy }
                | None ->
                    printfn "ERROR: example file could not be deserialized: %A" fp
                    raise (ArgumentException("invalid example config file"))
            | Some fp ->
                printfn "ERROR: invalid file path for the example config file given: %A" fp
                raise (ArgumentException("invalid example config file path"))

        let exampleFileWithEmptyConfig = getExampleConfigFile config.ExampleConfigFilePath false
        let configuredExampleFiles =
            match config.ExampleConfigFiles with
            | None -> []
            | Some exampleConfigFiles ->
                exampleConfigFiles
                |> List.choose (fun ecf -> getExampleConfigFile (Some ecf.filePath) ecf.exactCopy)

        match exampleFileWithEmptyConfig with
        | None -> configuredExampleFiles
        | Some exampleFile -> exampleFile::configuredExampleFiles

    let grammar, dependencies, (newDictionary, perResourceDictionaries), examples =
        Restler.Compiler.Main.generateRequestGrammar
                        configuredSwaggerDocs
                        dictionary
                        { config with ExamplesDirectory = examplesDirectory }
                        globalExternalAnnotations
                        userSpecifiedExamples

    let grammarFilePath = Path.Combine(grammarOutputDirectoryPath, Constants.DefaultJsonGrammarFileName)
    Restler.Utilities.Stream.serializeToFile grammarFilePath grammar

    // The below statement is present as an assertion, to check for deserialization issues for
    // specific grammars.
#if TEST_GRAMMAR
    use f = System.IO.File.OpenRead(grammarFilePath)
    JsonSerialization.deserializeStream<GrammarDefinition> f
    |> ignore
#endif

    // If examples were discovered, create a new examples file
    if config.DiscoverExamples then
        let discoveredExamplesFilePath = Path.Combine(examplesDirectory, Constants.DefaultExampleMetadataFileName)
        Examples.serializeExampleConfigFile discoveredExamplesFilePath examples

    // A helper function to override defaults with user-specified dictionary values 
    // when the user specifies only some of the properties
    let mergeWithDefaultDictionary (newDictionaryAsString:string) =
        let defaultDict = JsonSerialization.serialize Dictionary.DefaultMutationsDictionary
        let newDict = Utilities.JsonParse.mergeWithOverride defaultDict newDictionaryAsString

        JsonSerialization.deserialize<Dictionary.MutationsDictionary> newDict

    // Write the updated dictionary.
    let writeDictionary dictionaryName newDict =
        let newDictionaryFilePath = System.IO.Path.Combine(grammarOutputDirectoryPath, dictionaryName)
        printfn "Writing new dictionary to %s" newDictionaryFilePath
        // Add any properties to the dictionary that are missing from the original dictionary
        // For example, the user may specify only custom payloads, and exclude fuzzable properties.
        let newDict = mergeWithDefaultDictionary (JsonSerialization.serialize newDict) 
        JsonSerialization.serializeToFile newDictionaryFilePath newDict

    writeDictionary Constants.NewDictionaryFileName newDictionary

    // Also generate a template for input value generator based on the dictionary.
    let newDictJson = JsonSerialization.serialize newDictionary
    let customValueGeneratorTemplateFilePath = System.IO.Path.Combine(grammarOutputDirectoryPath, Constants.CustomValueGeneratorTemplateFileName)
    let templateLines = Restler.CodeGenerator.Python.generateCustomValueGenTemplate newDictJson
    Microsoft.FSharpLu.File.writeLines customValueGeneratorTemplateFilePath templateLines

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

let generateRestlerGrammar (config:Config) =
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
            JsonSerialization.deserializeStream<GrammarDefinition> f
        | None ->
             logTimingInfo "Generating grammar..."
             generateGrammarFromSwagger grammarOutputDirectoryPath config
        | Some p ->
            printfn "ERROR: invalid path for grammar: %s" p
            exit 1

    logTimingInfo "Generating python grammar..."
    generatePython grammarOutputDirectoryPath config grammar
    logTimingInfo "Done generating python grammar."
    printfn "Workflow completed.  See %s for REST-ler grammar." grammarOutputDirectoryPath
