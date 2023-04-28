// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

namespace Restler.Test
open System
open System.IO
open Xunit
open Restler.Test.Utilities

[<Trait("TestCategory", "Examples")>]
module Dictionary =
    type DictionaryTests(ctx:Fixtures.TestSetupAndCleanup, output:Xunit.Abstractions.ITestOutputHelper) =
        [<Fact>]
        /// Baseline test for all types in the grammar supported by RESTler.
        let ``quoting is correct in the grammar`` () =
            let grammarOutputDirPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some grammarOutputDirPath
                             ResolveBodyDependencies = true
                             ResolveQueryDependencies = true
                             UseBodyExamples = Some false
                             UseQueryExamples = Some false
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "dictionaryTests", "customPayloadSwagger.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, "swagger", "dictionaryTests", "customPayloadDict.json"))
                         }
            Restler.Workflow.generateRestlerGrammar config

            let expectedGrammarFilePath = Path.Combine(Environment.CurrentDirectory,
                                                       "baselines", "dictionaryTests", "quoted_primitives_grammar.py")
            let actualGrammarFilePath = Path.Combine(grammarOutputDirPath,
                                                     Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let grammarDiff = getLineDifferences expectedGrammarFilePath actualGrammarFilePath
            let message = sprintf "Grammar Does not match baseline.  First difference: %A" grammarDiff
            Assert.True(grammarDiff.IsNone, message)

        [<Fact>]
        /// Test for custom payload uuid suffix
        let ``path and body parameter set to the same uuid suffix payload`` () =
            let grammarOutputDirPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some grammarOutputDirPath
                             ResolveBodyDependencies = true
                             ResolveQueryDependencies = true
                             UseBodyExamples = Some false
                             UseQueryExamples = Some false
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "dictionaryTests", "multipleIdenticalUuidSuffix.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, "swagger", "dictionaryTests", "multipleIdenticalUuidSuffixDict.json"))
                         }
            Restler.Workflow.generateRestlerGrammar config

            let grammarFilePath = Path.Combine(grammarOutputDirPath,
                                               Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let grammar = File.ReadAllText(grammarFilePath)

            // The grammar should contain both of the custom payload uuid suffixes from the dictionary
            Assert.True(grammar.Contains("""primitives.restler_custom_payload_uuid4_suffix("resourceId", quoted=False)"""))

            // TODO: the generated grammar currently contains a known bug - the resoruce ID is an integer and is being
            // assigned a uuid suffix, which currently only supports strings.  The 'quoted' value is correctly 'False'
            // because ID is an integer type, but
            // in the future this should be a different primitive, e.g. 'custom_payload_unique_integer' 
            Assert.True(grammar.Contains("""primitives.restler_custom_payload_uuid4_suffix("/resource/id", quoted=False)"""))

        [<Fact>]
        /// Test that when a custom payload query (resp. header) is specified in the dictionary, it is injected.
        let ``custom payload query and header is correctly injected`` () =
            let grammarOutputDirPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some grammarOutputDirPath
                             ResolveBodyDependencies = true
                             ResolveQueryDependencies = true
                             UseBodyExamples = Some false
                             UseQueryExamples = Some false
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "dictionaryTests", "no_params.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, "swagger", "dictionaryTests", "inject_custom_payloads_dict.json"))

                         }

            let configWithoutDictionary = { config with CustomDictionaryFilePath = None }
            Restler.Workflow.generateRestlerGrammar configWithoutDictionary

            let grammarFilePath = Path.Combine(grammarOutputDirPath,
                                               Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let grammarLines = File.ReadAllLines(grammarFilePath)
            // Without the dictionary, there should be 4 fuzzable strings corresponding to the 4 spec parameters
            let numFuzzableStrings = grammarLines |> Seq.filter (fun s -> s.Contains("restler_fuzzable_string(")) |> Seq.length
            Assert.True((numFuzzableStrings = 4))

            // Now generate a grammar with the dictionary
            Restler.Workflow.generateRestlerGrammar config

            let grammarFilePath = Path.Combine(grammarOutputDirPath,
                                               Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let grammar = File.ReadAllText(grammarFilePath)

            // The header 'spec_header1' is declared in the spec and in the 'custom_payload_header' section.
            // There should be a custom_payload_header("spec_header1"),  in the grammar.
            Assert.True(grammar.Contains("""restler_custom_payload_header("spec_header1")"""))

            // The query parameter 'spec_query1' is declared in the spec and in the 'custom_payload_query' section.
            // There should be a custom_payload_query("spec_header1"),  in the grammar.
            Assert.True(grammar.Contains("""restler_custom_payload_query("spec_query1")"""))

            // The query and header parameters 'spec_query2' and 'spec_header2' are
            // declared in the spec and in the 'custom_payload_query' section.
            // The query should be substituted with the dictionary values (legacy behavior; this may
            // be updated in the future to require restler_custom_payload_query)
            // The header should not be substituted with the dictionary values (restler_custom_payload_header
            // should be used instead).
            Assert.False(grammar.Contains("""restler_custom_payload("spec_header2")"""))
            Assert.True(grammar.Contains("""restler_custom_payload("spec_query2","""))

            // The injected query and headers should be present
            Assert.True(grammar.Contains("""restler_custom_payload_header("extra_header1")"""))
            Assert.True(grammar.Contains("""restler_custom_payload_header("extra_header2")"""))
            Assert.True(grammar.Contains("""restler_custom_payload_query("extra_query1")"""))
            Assert.True(grammar.Contains("""restler_custom_payload_query("extra_query2")"""))

            // There should be just one fuzzable string
            let grammarLines2 = grammar.Split("\n")
            // Without the dictionary, there should be 4 fuzzable strings corresponding to the 4 spec parameters
            let numFuzzableStrings2 = grammarLines2 |> Seq.filter (fun s -> s.Contains("restler_fuzzable_string(")) |> Seq.length
            Assert.True((numFuzzableStrings2 = 1))

        [<Fact>]
        /// Test that you can replace the content type of the request payload
        let ``content type can be modified via custom_payload_header`` () =
            let grammarOutputDirPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some grammarOutputDirPath
                             ResolveBodyDependencies = true
                             ResolveQueryDependencies = true
                             UseBodyExamples = Some false
                             UseQueryExamples = Some false
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "dictionaryTests", "customPayloadSwagger.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, "swagger", "dictionaryTests", "customPayloadRequestTypeDict.json"))
                         }
            Restler.Workflow.generateRestlerGrammar config

            let grammarFilePath = Path.Combine(grammarOutputDirPath,
                                               Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let grammar = File.ReadAllText(grammarFilePath)

            Assert.True(grammar.Contains("""primitives.restler_static_string("Content-Type: "),"""))
            Assert.True(grammar.Contains("""primitives.restler_static_string("application/json"),"""))
            Assert.True(grammar.Contains("""primitives.restler_custom_payload("/stores/{storeId}/order/post/Content-Type", quoted=False),"""))

        [<Fact>]
        /// Baseline test for the dynamic value generators template
        let ``generated custom value generator template is correct`` () =
            let grammarOutputDirPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some grammarOutputDirPath
                             ResolveBodyDependencies = true
                             ResolveQueryDependencies = true
                             UseBodyExamples = Some false
                             UseQueryExamples = Some false
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "dictionaryTests", "customPayloadSwagger.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, "swagger", "dictionaryTests", "customPayloadDict.json"))
                         }
            Restler.Workflow.generateRestlerGrammar config

            let expectedValueGenTemplatePath = Path.Combine(Environment.CurrentDirectory,
                                                            @"baselines", "dictionaryTests", "customPayloadDict_ValueGeneratorTemplate.py")
            let actualValueGenTemplatePath = Path.Combine(grammarOutputDirPath,
                                                          Restler.Workflow.Constants.CustomValueGeneratorTemplateFileName)
            let valueGenDiff = getLineDifferences expectedValueGenTemplatePath actualValueGenTemplatePath
            let message = sprintf "Template value generator does not match baseline.  First difference: %A" valueGenDiff
            Assert.True(valueGenDiff.IsNone, message)

        [<Fact>]
        /// Test that dates are deserialized and serialized in the same format as
        /// specified by the user
        let ``date format is preserved after deserialization and serialization`` () =
            let dictionaryFilePath = 
                Path.Combine(Environment.CurrentDirectory, "swagger", "dictionaryTests", "serializationTestDict.json")

            let deserialized = Restler.Utilities.JsonSerialization.deserializeFile<Restler.Dictionary.MutationsDictionary> dictionaryFilePath
            let custom_payload = 
                deserialized.restler_custom_payload.Value
            let fuzzable_date = deserialized.restler_fuzzable_datetime.Value
            let serialized = Restler.Utilities.JsonSerialization.serialize deserialized

            Assert.Equal("03/13/2023 10:36:56 ", 
                         custom_payload.["custom_date2"][0])
            Assert.Equal("2023-03-13T10:36:56.0000000Z", 
                         custom_payload.["custom_date1"][0])
            Assert.Equal("2023-03-13T10:36:56.0000000Z", 
                         fuzzable_date[0])

            Assert.True(serialized.Contains("2023-03-13T10:36:56.0000000Z"))
            Assert.True(serialized.Contains("03/13/2023 10:36:56 "))

            // Compile and check that the output dictionary contains the
            // ISO date
            let grammarOutputDirPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some grammarOutputDirPath
                             ResolveBodyDependencies = true
                             ResolveQueryDependencies = true
                             UseBodyExamples = Some false
                             UseQueryExamples = Some false
                             // The spec is arbitrary, since the test is only checking the output
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "dictionaryTests", "customPayloadSwagger.json"))]
                             CustomDictionaryFilePath = Some dictionaryFilePath
                         }
            let inputDictionaryString = 
                File.ReadAllText(dictionaryFilePath)

            Restler.Workflow.generateRestlerGrammar config
            let outputDictPath = Path.Combine(grammarOutputDirPath,
                                              Restler.Workflow.Constants.NewDictionaryFileName)
            let dictionaryString = 
                File.ReadAllText(outputDictPath)

            Assert.True(dictionaryString.Contains("2023-03-13T10:36:56.0000000Z"))
            Assert.True(dictionaryString.Contains("03/13/2023 10:36:56 "))

        interface IClassFixture<Fixtures.TestSetupAndCleanup>
