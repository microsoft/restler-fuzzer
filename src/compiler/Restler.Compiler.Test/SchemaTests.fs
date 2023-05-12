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
            Restler.Workflow.generateRestlerGrammar config
            let grammarOutputFilePath =
                config.GrammarOutputDirectoryPath.Value ++ Restler.Workflow.Constants.DefaultRestlerGrammarFileName


            Assert.True(File.Exists(grammarOutputFilePath))
            let grammar = File.ReadAllText(grammarOutputFilePath)
            // Make sure the grammar contains at least one request
            Assert.True(grammar.Contains("req_collection.add_request(request)"))

        let diffGrammarOutputFiles config pyGrammarBaselineFilePath jsonGrammarBaselineFilePath = 
            let grammarDiff =
                getLineDifferences
                    (config.GrammarOutputDirectoryPath.Value ++ Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
                    pyGrammarBaselineFilePath
            let message = sprintf "grammar.py does not match baseline.  First difference: %A" grammarDiff
            Assert.True(grammarDiff.IsNone, message)

            let grammarDiff =
                getLineDifferences
                    (config.GrammarOutputDirectoryPath.Value ++ Restler.Workflow.Constants.DefaultJsonGrammarFileName)
                    jsonGrammarBaselineFilePath
            let message = sprintf "grammar.json does not match baseline.  First difference: %A" grammarDiff
            Assert.True(grammarDiff.IsNone, message)


        [<Fact>]
        let ``required header is parsed successfully`` () =
            compileSpec (Path.Combine("swagger", "schemaTests", "requiredHeader.yml"))

        [<Fact>]
        let ``spec with x-ms-paths is parsed successfully`` () =
            let specFilePath = Path.Combine(Environment.CurrentDirectory, "swagger", "schemaTests", "xMsPaths.json")
            let dictionaryFilePath = Path.Combine(Environment.CurrentDirectory, "swagger", "schemaTests", "xMsPaths_dict.json")
            let annotationsFilePath = Path.Combine(Environment.CurrentDirectory, "swagger", "schemaTests", "xMsPaths_annotations.json")
            let exampleConfigFilePath = Path.Combine(Environment.CurrentDirectory, "swagger", "schemaTests", "xMsPaths_examples.json")
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                             ResolveBodyDependencies = true
                             ResolveQueryDependencies = true
                             SwaggerSpecFilePath = Some [specFilePath]
                             CustomDictionaryFilePath = Some dictionaryFilePath
                             AnnotationFilePath = Some annotationsFilePath
                             ExampleConfigFilePath = Some exampleConfigFilePath
                             UseHeaderExamples = Some true
                         }
            Restler.Workflow.generateRestlerGrammar config

            diffGrammarOutputFiles config 
                                   (Path.Combine(Environment.CurrentDirectory, "baselines", "schemaTests", "xMsPaths_grammar.py"))
                                   (Path.Combine(Environment.CurrentDirectory, "baselines", "schemaTests", "xMsPaths_grammar.json"))

        [<Fact>]
        let ``path parameter is read from the global parameters`` () =
            let specFilePath = Path.Combine(Environment.CurrentDirectory, "swagger", "schemaTests", "global_path_parameters.json")
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                             ResolveBodyDependencies = true
                             ResolveQueryDependencies = true
                             SwaggerSpecFilePath = Some [specFilePath]
                         }
            Restler.Workflow.generateRestlerGrammar config
            let grammarOutputFilePath = config.GrammarOutputDirectoryPath.Value ++ Restler.Workflow.Constants.DefaultRestlerGrammarFileName
            let grammar = File.ReadAllText(grammarOutputFilePath)
            Assert.True(grammar.Contains("restler_custom_payload_uuid4_suffix(\"customerId\", quoted=False)"))

        [<Fact>]
        let ``swagger escape characters is parsed successfully`` () =
            let specFilePath = Path.Combine(Environment.CurrentDirectory, "swagger", "schemaTests", "swagger_escape_characters.json")
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                             ResolveBodyDependencies = true
                             ResolveQueryDependencies = true
                             SwaggerSpecFilePath = Some [specFilePath]
                         }
            Restler.Workflow.generateRestlerGrammar config
            let grammarOutputFilePath = config.GrammarOutputDirectoryPath.Value ++ Restler.Workflow.Constants.DefaultRestlerGrammarFileName
            let grammar = File.ReadAllText(grammarOutputFilePath)
            Assert.True(grammar.Contains("\"escape\""))
            Assert.True(grammar.Contains("\"escape_characters1\""))
            Assert.True(grammar.Contains("\"escape_characters2\""))
            Assert.True(grammar.Contains("\"query_param=\""))

        [<Fact>]
        let ``openapi3 requestBody`` () =
            let specFilePath = Path.Combine(Environment.CurrentDirectory, "swagger", "schemaTests", "openapi3_requestbody.json")
            let config = { Restler.Config.SampleConfig with
                                IncludeOptionalParameters = true
                                GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                                ResolveBodyDependencies = true
                                ResolveQueryDependencies = true
                                SwaggerSpecFilePath = Some [specFilePath]
                            }
            Restler.Workflow.generateRestlerGrammar config
            let grammarOutputFilePath = config.GrammarOutputDirectoryPath.Value ++ Restler.Workflow.Constants.DefaultRestlerGrammarFileName
            let grammar = File.ReadAllText(grammarOutputFilePath)
            Assert.True(grammar.Contains("\"treeId\":"))
            Assert.True(grammar.Contains("\"beachId\":"))
            Assert.True(grammar.Contains("_bananas_post_results_id.reader()"))


        [<Fact>]
        let ``json depth limit test`` () =
            let specFilePath = Path.Combine(Environment.CurrentDirectory, "swagger", "schemaTests", "large_json_body.json")
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                             ResolveBodyDependencies = true
                             ResolveQueryDependencies = true
                             SwaggerSpecFilePath = Some [specFilePath]
                         }

            Restler.Workflow.generateRestlerGrammar config
            let grammarOutputFilePath = config.GrammarOutputDirectoryPath.Value ++ Restler.Workflow.Constants.DefaultRestlerGrammarFileName
            let noDepthLimitGrammar = File.ReadAllText(grammarOutputFilePath)

            let upperLimit = 6
            let lowerLimit = 0
            for depthLimit in lowerLimit..upperLimit do
                let objectName = sprintf "object_level_%d" depthLimit
                let nextObjectName = sprintf "object_level_%d" (depthLimit + 1)
                Restler.Workflow.generateRestlerGrammar { config with JsonPropertyMaxDepth = Some depthLimit }
                let grammarOutputFilePath = config.GrammarOutputDirectoryPath.Value ++ Restler.Workflow.Constants.DefaultRestlerGrammarFileName
                let grammar = File.ReadAllText(grammarOutputFilePath)
                if depthLimit < upperLimit then
                    Assert.True(grammar <> noDepthLimitGrammar)
                // Make sure the object for this level is present, and the one for the next level is not
                if depthLimit > lowerLimit then
                    Assert.True(grammar.Contains(objectName))
                    Assert.False(grammar.Contains(nextObjectName))

        [<Fact>]
        let ``additionalProperties schema`` () =
            let specFilePath = Path.Combine(Environment.CurrentDirectory, "swagger", "schemaTests", "additionalProperties.yml")
            let config = { Restler.Config.SampleConfig with
                                IncludeOptionalParameters = true
                                GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                                ResolveBodyDependencies = true
                                ResolveQueryDependencies = true
                                SwaggerSpecFilePath = Some [specFilePath]
                         }
            Restler.Workflow.generateRestlerGrammar config
            let grammarOutputFilePath = config.GrammarOutputDirectoryPath.Value ++ Restler.Workflow.Constants.DefaultRestlerGrammarFileName
            let grammar = File.ReadAllText(grammarOutputFilePath)
            let expectedProperties = ["supiRanges"; "groupId"; "start"; "end"]
            for ep in expectedProperties do
                Assert.True(grammar.Contains(sprintf "\"%s\":" ep))

        [<Fact>]
        let ``openapi3 examples`` () =
            let specFilePath = Path.Combine(Environment.CurrentDirectory, "swagger", "schemaTests", "openapi3_examples.json")
            let config = { Restler.Config.SampleConfig with
                                IncludeOptionalParameters = true
                                GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                                ResolveBodyDependencies = true
                                ResolveQueryDependencies = true
                                SwaggerSpecFilePath = Some [specFilePath]
                            }
            Restler.Workflow.generateRestlerGrammar config
            let grammarOutputFilePath = config.GrammarOutputDirectoryPath.Value ++ Restler.Workflow.Constants.DefaultRestlerGrammarFileName
            let grammar = File.ReadAllText(grammarOutputFilePath)
            
            Assert.True(grammar.Contains("9.9999"))
            Assert.True(grammar.Contains("examples=[\"string_param_example999\"]"))
            Assert.True(grammar.Contains("examples=[\"string_schema_example888\"]"))
            Assert.True(grammar.Contains("examples=[\"id_string_example_12345\"]"))
            // the below are body example properties
            Assert.True(grammar.Contains("examples=[\"50000\"]"))
            Assert.True(grammar.Contains("examples=[\"10000000\"]"))
            Assert.True(grammar.Contains("examples=[\"48\"]"))
            Assert.False(grammar.Contains("schema_example_9574638"))
            Assert.True(grammar.Contains("\\\"completed\\\":true"))



        [<Fact>]
        let ``path parameter substrings`` () =
            let specFilePath = Path.Combine(Environment.CurrentDirectory, "swagger", "schemaTests", "path_param_substrings.json")
            let config = { Restler.Config.SampleConfig with
                                IncludeOptionalParameters = true
                                GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                                ResolveBodyDependencies = true
                                ResolveQueryDependencies = true
                                SwaggerSpecFilePath = Some [specFilePath]
                         }
            Restler.Workflow.generateRestlerGrammar config
            diffGrammarOutputFiles config 
                                   (Path.Combine(Environment.CurrentDirectory, "baselines", "schemaTests", "path_param_substrings_grammar.py"))
                                   (Path.Combine(Environment.CurrentDirectory, "baselines", "schemaTests", "path_param_substrings_grammar.json"))

        interface IClassFixture<Fixtures.TestSetupAndCleanup>
