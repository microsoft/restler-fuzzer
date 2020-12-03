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
            let grammarOutputDirPath = @"c:\temp\restlertest" //ctx.testRootDirPath
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


        interface IClassFixture<Fixtures.TestSetupAndCleanup>
