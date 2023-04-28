// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.Config

open System
open System.IO

/// The 'type' of the resource is inferred based on the naming of its name and container as
/// well as conventions for the API method (e.g. PUT vs. POST).
/// A naming convention may be specified by the user, or it is inferred automatically
type NamingConvention =
    | CamelCase  // accountId
    | PascalCase // AccountId
    | HyphenSeparator  // account-id
    | UnderscoreSeparator // account_id

/// A configuration associated with a single API specification file (e.g. a Swagger .json spec)
type SwaggerSpecConfig =
    {
        /// Swagger spec file path
        SpecFilePath : string

        /// File path to the custom fuzzing dictionary
        DictionaryFilePath: string option

        /// Inline json for the fuzzing dictionary
        /// This can be specified if the user wants a new dictionary generated, but
        /// just wants to specify one property inline
        Dictionary: string option

        /// The RESTler annotations that should be used for this Swagger spec only
        /// Note: global annotations that should be applied to multiple specs must be
        /// specified at the top level of the config
        AnnotationFilePath: string option
    }

/// The configuration for the payload examples.
type ExampleFileConfig =
    {
        /// The path to the example configuration file that contains the examples associated with
        /// one or more request types from the spec.
        filePath : string

        // If 'true', copy these examples exactly, without substituting any parameter values from the dictionary
        // If 'false' (default), the examples are merged with the schema.  In particular, parameters with names
        // that do not match the schema are discarded.
        exactCopy : bool
    }

/// User-specified compiler configuration
type Config =
    {
        /// An API specification configuration that includes the Swagger specification and
        /// other artifacts (e.g., annotations to augment the information in the spec).
        SwaggerSpecConfig : SwaggerSpecConfig list option

        /// The Swagger specification specifying this API
        SwaggerSpecFilePath : string list option

        // If specified, use this as the input and generate the python grammar.
        GrammarInputFilePath : string option

        GrammarOutputDirectoryPath : string option

        CustomDictionaryFilePath : string option

        AnnotationFilePath: string option

        // If specified, update the engine settings with hints derived from the grammar.
        EngineSettingsFilePath : string option

        IncludeOptionalParameters : bool

        UseHeaderExamples : bool option

        UsePathExamples : bool option

        UseQueryExamples : bool option

        UseBodyExamples : bool option

        /// When specified, all example payloads are used - both the ones in the specification and the ones in the
        /// example config file.
        /// False by default - example config files override any other available payload examples
        UseAllExamplePayloads : bool option

        /// When set to 'true', discovers examples and outputs them to a directory next to the grammar.
        /// If an existing directory exists, does not over-write it.
        DiscoverExamples : bool

        /// The directory where the compiler should look for examples.
        /// If 'discoverExamples' is true, this directory will contain the
        /// example files that have been discovered.
        /// If 'discoverExamples' is false, every time an example is used in the
        /// Swagger file, RESTler will first look for it in this directory.
        ExamplesDirectory : string

        /// File path specifying the example config file
        ExampleConfigFilePath : string option

        /// Specifies the example config files.  If the example config file path
        /// is specified, both are used.
        ExampleConfigFiles : ExampleFileConfig list option

        /// Perform data fuzzing
        DataFuzzing : bool

        // When true, only fuzz the GET requests
        ReadOnlyFuzz : bool

        ResolveQueryDependencies: bool

        ResolveBodyDependencies: bool

        ResolveHeaderDependencies: bool

        UseRefreshableToken : bool option

        // When true, allow GET requests to be considered.
        // This option is present for debugging, and should be
        // set to 'false' by default.
        // In limited cases when GET is a valid producer, the user
        // should add an annotation for it.
        AllowGetProducers : bool

        // When specified, use only this naming convention to infer
        // producer-consumer dependencies.
        ApiNamingConvention : NamingConvention option

        // When this switch is on, the generated grammar will contain
        // parameter names for all fuzzable values.  For example:
        // restler_fuzzable_string("1", param_name="num_items")
        TrackFuzzedParameterNames : bool

        // The maximum depth for Json properties in the schema to test
        // Any properties exceeding this depth are removed.
        JsonPropertyMaxDepth : int option
    }

let convertToAbsPath (currentDirPath:string) (filePath:string) =
    if Path.IsPathFullyQualified(filePath) then filePath
    else
        Path.Combine(currentDirPath, filePath)

// When relative paths are specified in the config, they are expected to
// be relative to the config file directory.  This function converts all paths to
// absolute paths.
let convertRelativeToAbsPaths configFilePath config =

    // If relative paths are specified in the config, they are expected to
    // be relative to the config file directory.
    let configFileDirPath =
        let fullPath = Path.GetFullPath(configFilePath)
        Path.GetDirectoryName(fullPath)

    let swaggerSpecFilePath =
        match config.SwaggerSpecFilePath with
        | Some swaggerPaths ->
            swaggerPaths
            |> List.map (fun swaggerPath -> convertToAbsPath configFileDirPath swaggerPath)
            |> Some
        | None -> config.SwaggerSpecFilePath

    let apiSpecs =
        match config.SwaggerSpecConfig with
        | None -> None
        | Some apiSpecConfigList ->
            apiSpecConfigList
            |> List.map (fun apiSpecConfig ->
                                {
                                    AnnotationFilePath =
                                        match apiSpecConfig.AnnotationFilePath with
                                        | Some x -> convertToAbsPath configFileDirPath x |> Some
                                        | None -> None
                                    DictionaryFilePath =
                                        match apiSpecConfig.DictionaryFilePath with
                                        | Some x -> convertToAbsPath configFileDirPath x |> Some
                                        | None -> None
                                    SpecFilePath = convertToAbsPath configFileDirPath apiSpecConfig.SpecFilePath
                                    Dictionary = apiSpecConfig.Dictionary
                                })
            |> Some

    let customDictionaryFilePath =
        match config.CustomDictionaryFilePath with
        | Some p -> Some (convertToAbsPath configFileDirPath p)
        | None -> None

    let grammarInputFilePath =
        match config.GrammarInputFilePath with
        | Some p -> Some (convertToAbsPath configFileDirPath p)
        | None -> None

    let engineSettingsFilePath =
        match config.EngineSettingsFilePath with
        | Some p -> Some (convertToAbsPath configFileDirPath p)
        | None -> None

    let annotationsFilePath =
        match config.AnnotationFilePath with
        | Some p -> Some (convertToAbsPath configFileDirPath p)
        | None -> None

    let exampleConfigFilePath =
        match config.ExampleConfigFilePath with
        | Some p -> Some (convertToAbsPath configFileDirPath p)
        | None -> None

    let exampleConfigFiles =
        match config.ExampleConfigFiles with
        | Some ec ->
            Some (ec |> List.map (fun ecf ->
                                    { ecf with
                                         filePath = convertToAbsPath configFileDirPath ecf.filePath }))
        | None -> None

    { config with
        SwaggerSpecFilePath = swaggerSpecFilePath
        CustomDictionaryFilePath = customDictionaryFilePath
        GrammarInputFilePath = grammarInputFilePath
        EngineSettingsFilePath = engineSettingsFilePath
        SwaggerSpecConfig = apiSpecs
        AnnotationFilePath = annotationsFilePath
        ExampleConfigFilePath = exampleConfigFilePath
        ExampleConfigFiles = exampleConfigFiles
    }


/// A sample config with all supported values initialized.
let SampleConfig =
    {
        SwaggerSpecConfig = None
        SwaggerSpecFilePath = None
        GrammarInputFilePath = None
        CustomDictionaryFilePath = None
        AnnotationFilePath = None
        ExampleConfigFilePath = None
        ExampleConfigFiles = None
        GrammarOutputDirectoryPath = None
        IncludeOptionalParameters = true
        UsePathExamples = None
        UseQueryExamples = None
        UseBodyExamples = None
        UseHeaderExamples = None
        DiscoverExamples = false
        UseAllExamplePayloads = None
        ExamplesDirectory = ""
        ResolveQueryDependencies = true
        ResolveBodyDependencies = false
        ResolveHeaderDependencies = false
        ReadOnlyFuzz = false
        UseRefreshableToken = Some true
        AllowGetProducers = false
        EngineSettingsFilePath = None
        DataFuzzing = true
        ApiNamingConvention = None
        TrackFuzzedParameterNames = false
        JsonPropertyMaxDepth = None
    }

/// The default config used for unit tests.  Most of these should also be the defaults for
/// end users, and options should be explicitly changed by the caller (e.g. RESTler driver or
/// the user settings file).
let DefaultConfig =
    {
        SwaggerSpecConfig = None
        SwaggerSpecFilePath = None
        GrammarInputFilePath = None
        CustomDictionaryFilePath = None
        AnnotationFilePath = None
        ExampleConfigFilePath = None
        ExampleConfigFiles = None
        GrammarOutputDirectoryPath = None
        IncludeOptionalParameters = true
        UseQueryExamples = Some true
        UseHeaderExamples = Some true
        UseBodyExamples = Some true
        UsePathExamples = Some false
        UseAllExamplePayloads = Some false
        DiscoverExamples = false
        ExamplesDirectory = ""
        ResolveQueryDependencies = true
        ResolveBodyDependencies = true
        ResolveHeaderDependencies = false
        ReadOnlyFuzz = false
        UseRefreshableToken = Some true
        AllowGetProducers = false
        EngineSettingsFilePath = None
        DataFuzzing = false
        ApiNamingConvention = None
        TrackFuzzedParameterNames = false
        JsonPropertyMaxDepth = None
    }

// A helper function to override defaults with user-specified config values 
// when the user specifies only some of the properties
let mergeWithDefaultConfig (userConfigAsString:string) =
    let defaultConfig = Utilities.JsonSerialization.serialize DefaultConfig
    let newConfig = Restler.Utilities.JsonParse.mergeWithOverride defaultConfig userConfigAsString

    Utilities.JsonSerialization.deserialize<Config> newConfig

/// Determines which dictionary to use with each Swagger/OpenAPI spec and returns
/// a 'SwaggerSpecConfig' for each specification. 
let getSwaggerSpecConfigsFromCompilerConfig (config:Config) = 
    let swaggerDocs =
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
        | Some p ->
            printfn "ERROR: invalid path found in the list of Swagger specs given: %A" p
            raise (ArgumentException(sprintf "invalid API spec file path found: %A" p))

    let docsWithEmptyConfig =
        swaggerDocs
        |> List.map (fun x ->
                        {   SwaggerSpecConfig.SpecFilePath = x
                            DictionaryFilePath = None
                            Dictionary = None
                            AnnotationFilePath = None
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
            docsWithEmptyConfig @ configuredDocs
        | Some docs ->
            printfn "ERROR: invalid path found in the list of Swagger configurations given: %A" docs
            raise (ArgumentException(sprintf "invalid API spec file path found: %A" docs))

    configuredSwaggerDocs
