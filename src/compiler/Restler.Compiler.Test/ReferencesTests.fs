// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

namespace Restler.Test
open System
open System.IO
open Xunit
open Restler.Test.Utilities
open Restler.Config

/// This test suite contains coverage for tricky references in Swagger files.
/// It primarily serves as a regression suite for the framework used to parse Swagger files.
[<Trait("TestCategory", "References")>]
module References =
    type ReferencesTests(ctx:Fixtures.TestSetupAndCleanup, output:Xunit.Abstractions.ITestOutputHelper) =

        let testReferenceTypes specFileName =
            let filePath = Path.Combine(Environment.CurrentDirectory, sprintf @"swagger\referencesTests\%s" specFileName)
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                             ResolveBodyDependencies = true
                             UseBodyExamples = Some false
                             SwaggerSpecFilePath = Some [filePath]
                             CustomDictionaryFilePath = None
                         }
            Restler.Workflow.generateRestlerGrammar None config

            // TODO: check that all 4 types are present.
            Assert.True(true)
            //let grammarFilePath = Path.Combine(defaultGrammarOutputDirectoryPath, "grammar.py")
            //let grammar = File.ReadAllText(grammarFilePath)

            //// The grammar should not contain any fuzzable resources.
            //Assert.False(grammar.Contains("fuzzable"))

        [<Fact>]
        let ``external refs multiple visits per file - first`` () =
            /// Tests the case where file2 is parsed, it has references to file1, then back to file2.
            /// Depending on the ordering, this was not handled correctly in NSwag (V10 and earlier).
            /// Both parsing first or second as the main Swagger file should work.
            testReferenceTypes "first.json"


        [<Fact>]
        let ``external refs multiple visits per file - second`` () =
            /// Tests the case where file2 is parsed, it has references to file1, then back to file2.
            /// Depending on the ordering, this was not handled correctly in NSwag (V10 and earlier).
            /// Both parsing first or second as the main Swagger file should work.
            testReferenceTypes "second.json"

        interface IClassFixture<Fixtures.TestSetupAndCleanup>
