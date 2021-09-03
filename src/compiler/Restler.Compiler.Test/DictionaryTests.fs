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
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\dictionaryTests\customPayloadSwagger.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, @"swagger\dictionaryTests\customPayloadDict.json"))
                         }
            Restler.Workflow.generateRestlerGrammar None config

            let expectedGrammarFilePath = Path.Combine(Environment.CurrentDirectory,
                                                       @"baselines\dictionaryTests\quoted_primitives_grammar.py")
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
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\dictionaryTests\multipleIdenticalUuidSuffix.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, @"swagger\dictionaryTests\multipleIdenticalUuidSuffixDict.json"))
                         }
            Restler.Workflow.generateRestlerGrammar None config

            let grammarFilePath = Path.Combine(grammarOutputDirPath,
                                               Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let grammar = File.ReadAllText(grammarFilePath)

            // The grammar should contain both of the custom payload uuid suffixes from the dictionary
            Assert.True(grammar.Contains("""primitives.restler_custom_payload_uuid4_suffix("resourceId"),"""))
            Assert.True(grammar.Contains("""primitives.restler_custom_payload_uuid4_suffix("/resource/id"),"""))

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
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\dictionaryTests\no_params.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, @"swagger\dictionaryTests\inject_custom_payloads_dict.json"))

                         }

            let configWithoutDictionary = { config with CustomDictionaryFilePath = None }
            Restler.Workflow.generateRestlerGrammar None configWithoutDictionary

            let grammarFilePath = Path.Combine(grammarOutputDirPath,
                                               Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let grammarLines = File.ReadAllLines(grammarFilePath)
            // Without the dictionary, there should be 4 fuzzable strings corresponding to the 4 spec parameters
            let numFuzzableStrings = grammarLines |> Seq.filter (fun s -> s.Contains("restler_fuzzable_string(")) |> Seq.length
            Assert.True((numFuzzableStrings = 4))

            // Now generate a grammar with the dictionary
            Restler.Workflow.generateRestlerGrammar None config

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
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\dictionaryTests\customPayloadSwagger.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, @"swagger\dictionaryTests\customPayloadRequestTypeDict.json"))
                         }
            Restler.Workflow.generateRestlerGrammar None config

            let grammarFilePath = Path.Combine(grammarOutputDirPath,
                                               Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let grammar = File.ReadAllText(grammarFilePath)

            Assert.True(grammar.Contains("""primitives.restler_static_string("Content-Type: "),"""))
            Assert.True(grammar.Contains("""primitives.restler_static_string("application/json"),"""))
            Assert.True(grammar.Contains("""primitives.restler_custom_payload("/stores/{storeId}/order/post/Content-Type", quoted=False),"""))

        interface IClassFixture<Fixtures.TestSetupAndCleanup>
