// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

namespace Restler.Test
open System
open System.IO
open Xunit
open Restler.Test.Utilities
open Restler.Config
open Microsoft.FSharpLu.File

/// This test suite contains coverage for corner cases / regression tests in how
/// RESTler handles the API specification schema.
[<Trait("TestCategory", "ApiSpecSchema")>]
module ApiSpecSchema =
    type SchemaTests(ctx:Fixtures.TestSetupAndCleanup, output:Xunit.Abstractions.ITestOutputHelper) =

        let compileSpec specFileName =
            let filePath = Path.Combine(Environment.CurrentDirectory, specFileName)
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                             ResolveBodyDependencies = true
                             UseBodyExamples = Some false
                             SwaggerSpecFilePath = Some [filePath]
                             CustomDictionaryFilePath = None
                         }
            Restler.Workflow.generateRestlerGrammar None config
            let grammarOutputFilePath =
                config.GrammarOutputDirectoryPath.Value ++ Restler.Workflow.Constants.DefaultRestlerGrammarFileName


            Assert.True(File.Exists(grammarOutputFilePath))
            let grammar = File.ReadAllText(grammarOutputFilePath)
            // Make sure the grammar contains at least one request
            Assert.True(grammar.Contains("req_collection.add_request(request)"))

        [<Fact>]
        let ``required header is parsed successfully`` () =
            compileSpec @"swagger\schemaTests\requiredHeader.yml"

        [<Fact>]
        let ``spec with x-ms-paths is parsed successfully`` () =
            let specFilePath = Path.Combine(Environment.CurrentDirectory, @"swagger\schemaTests\xMsPaths.json")
            let dictionaryFilePath = Path.Combine(Environment.CurrentDirectory, @"swagger\schemaTests\xMsPaths_dict.json")
            let annotationsFilePath = Path.Combine(Environment.CurrentDirectory, @"swagger\schemaTests\xMsPaths_annotations.json")
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                             ResolveBodyDependencies = true
                             ResolveQueryDependencies = true
                             SwaggerSpecFilePath = Some [specFilePath]
                             CustomDictionaryFilePath = Some dictionaryFilePath
                             AnnotationFilePath = Some annotationsFilePath
                         }
            Restler.Workflow.generateRestlerGrammar None config

            let grammarDiff =
                getLineDifferences
                    (config.GrammarOutputDirectoryPath.Value ++ Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
                    (Path.Combine(Environment.CurrentDirectory, @"baselines\schemaTests\xMsPaths_grammar.py"))
            let message = sprintf "grammar.py does not match baseline.  First difference: %A" grammarDiff
            Assert.True(grammarDiff.IsNone, message)

            let grammarDiff =
                getLineDifferences
                    (config.GrammarOutputDirectoryPath.Value ++ Restler.Workflow.Constants.DefaultJsonGrammarFileName)
                    (Path.Combine(Environment.CurrentDirectory, @"baselines\schemaTests\xMsPaths_grammar.json"))
            let message = sprintf "grammar.json does not match baseline.  First difference: %A" grammarDiff
            Assert.True(grammarDiff.IsNone, message)

        [<Fact>]
        let ``path parameter is read from the global parameters`` () =
            let specFilePath = Path.Combine(Environment.CurrentDirectory, @"swagger\schemaTests\global_path_parameters.json")
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                             ResolveBodyDependencies = true
                             ResolveQueryDependencies = true
                             SwaggerSpecFilePath = Some [specFilePath]
                         }
            Restler.Workflow.generateRestlerGrammar None config
            let grammarOutputFilePath = config.GrammarOutputDirectoryPath.Value ++ Restler.Workflow.Constants.DefaultRestlerGrammarFileName
            let grammar = File.ReadAllText(grammarOutputFilePath)
            Assert.True(grammar.Contains("restler_custom_payload_uuid4_suffix(\"customerId\")"))


        interface IClassFixture<Fixtures.TestSetupAndCleanup>
