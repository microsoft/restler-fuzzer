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
        let ``no quotes in grammar for custom payloads`` () =
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                             ResolveBodyDependencies = false
                             UseBodyExamples = true
                             UseQueryExamples = true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\dictionaryTests\customPayloadSwagger.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, @"swagger\dictionaryTests\customPayloadDict.json"))
                         }

            Restler.Workflow.generateRestlerGrammar None config
            let grammarFilePath = Path.Combine(ctx.testRootDirPath, "grammar.py")
            let grammar = File.ReadAllText(grammarFilePath)

            // TODO: test that each string type is not quoted in the grammar
            // as a fuzzable or as a custom payload,
            // but is quoted as a constant (from the example)
            Assert.True(false)

        interface IClassFixture<Fixtures.TestSetupAndCleanup>
