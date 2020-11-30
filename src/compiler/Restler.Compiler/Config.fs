// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.Config

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

        UseQueryExamples : bool option

        UseBodyExamples : bool option

        /// When set to 'true', discovers examples and outputs them to a directory next to the grammar.
        /// If an existing directory exists, does not over-write it.
        DiscoverExamples : bool

        /// The directory where the compiler should look for examples.
        /// If 'discoverExamples' is true, this directory will contain the
        /// example files that have been discovered.
        /// If 'discoverExamples' is false, every time an example is used in the
        /// Swagger file, RESTler will first look for it in this directory.
        ExamplesDirectory : string

        /// Perform data fuzzing
        DataFuzzing : bool

        // When true, only fuzz the GET requests
        ReadOnlyFuzz : bool

        ResolveQueryDependencies: bool

        ResolveBodyDependencies: bool

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

    { config with
        SwaggerSpecFilePath = swaggerSpecFilePath
        CustomDictionaryFilePath = customDictionaryFilePath
        GrammarInputFilePath = grammarInputFilePath
        EngineSettingsFilePath = engineSettingsFilePath
        SwaggerSpecConfig = apiSpecs
        AnnotationFilePath = annotationsFilePath
    }


/// A sample config with all supported values initialized.
let SampleConfig =
    {
        SwaggerSpecConfig = None
        SwaggerSpecFilePath = None
        GrammarInputFilePath = None
        CustomDictionaryFilePath = None
        AnnotationFilePath = None
        GrammarOutputDirectoryPath = None
        IncludeOptionalParameters = true
        UseQueryExamples = None
        UseBodyExamples = None
        DiscoverExamples = false
        ExamplesDirectory = ""
        ResolveQueryDependencies = true
        ResolveBodyDependencies = false
        ReadOnlyFuzz = false
        UseRefreshableToken = Some true
        AllowGetProducers = false
        EngineSettingsFilePath = None
        DataFuzzing = false
        ApiNamingConvention = None
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
        GrammarOutputDirectoryPath = None
        IncludeOptionalParameters = true
        UseQueryExamples = Some true
        UseBodyExamples = Some true
        DiscoverExamples = false
        ExamplesDirectory = ""
        ResolveQueryDependencies = true
        ResolveBodyDependencies = true
        ReadOnlyFuzz = false
        UseRefreshableToken = Some true
        AllowGetProducers = false
        EngineSettingsFilePath = None
        DataFuzzing = false
        ApiNamingConvention = None
    }