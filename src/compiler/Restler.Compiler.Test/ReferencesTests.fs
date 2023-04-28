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

        let testReferenceTypes specFileName (expectedGrammarLines: string list) =
            let filePath = Path.Combine(Environment.CurrentDirectory, "swagger", "referencesTests", sprintf "%s" specFileName)
            let grammarOutputDirectoryPath = Some ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = grammarOutputDirectoryPath
                             ResolveBodyDependencies = true
                             UseBodyExamples = Some false
                             SwaggerSpecFilePath = Some [filePath]
                             CustomDictionaryFilePath = None
                         }
            Restler.Workflow.generateRestlerGrammar config

            let grammarFilePath = Path.Combine(grammarOutputDirectoryPath.Value, "grammar.py")
            let grammarText = File.ReadAllText(grammarFilePath)

            for line in expectedGrammarLines do
                Assert.True (grammarText.Contains(line))

        [<Fact>]
        let ``external refs multiple visits per file - first`` () =
            /// Tests the case where file2 is parsed, it has references to file1, then back to file2.
            /// Depending on the ordering, this was not handled correctly in NSwag (V10 and earlier).
            /// Both parsing first or second as the main Swagger file should work.
            testReferenceTypes "first.json" []

        [<Fact>]
        let ``external refs multiple visits per file - second`` () =
            /// Tests the case where file2 is parsed, it has references to file1, then back to file2.
            /// Depending on the ordering, this was not handled correctly in NSwag (V10 and earlier).
            /// Both parsing first or second as the main Swagger file should work.
            testReferenceTypes "second.json" []


        [<Fact>]
        let ``array circular reference test`` () =
            testReferenceTypes "circular_array.json" []

        [<Fact>]
        let ``cached circular references - infinite recursion regression test`` () =
            testReferenceTypes "multiple_circular_paths.json" []

        [<Fact>]
        let ``cached circular references - missing properties regression test`` () =
            testReferenceTypes "circular_path.json" ["_customer_post_properties_name.reader()"]


        interface IClassFixture<Fixtures.TestSetupAndCleanup>
