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

        [<Fact>]
        let ``required header is parsed successfully`` () =
            compileSpec @"swagger\schemaTests\requiredHeader.yml"


        interface IClassFixture<Fixtures.TestSetupAndCleanup>
