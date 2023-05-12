// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

namespace Restler.Test
open System
open System.IO
open Xunit
open SwaggerSpecs
open Utilities

[<Trait("TestCategory", "GrammarJson")>]
module GrammarTests =
    type JsonGrammarTests(ctx:Fixtures.TestSetupAndCleanup, output:Xunit.Abstractions.ITestOutputHelper) =

        /// For a simple API with required and optional parameters,
        /// check that grammar.json matches what was declared in the specification
        /// Also, check that the grammar.py does not change when a parameter changes from
        /// optional to required (note: this will change in the future).
        [<Fact>]
        let ``required and optional properties correctly set`` () =
            let grammarOutputDirectoryPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             GrammarOutputDirectoryPath = Some grammarOutputDirectoryPath
                             ResolveBodyDependencies = false
                             UseBodyExamples = Some true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "grammarTests", "required_params.json"))]
                         }

            // Confirm the baselines match for grammar.json and grammar.py
            for includeOptionalParameters in [true ; false] do
                Restler.Workflow.generateRestlerGrammar { config with IncludeOptionalParameters = includeOptionalParameters }

                for extension in [".json"; ".py"] do
                    let actualGrammarFileName =
                        Path.GetFileNameWithoutExtension(Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
                    let expectedGrammarFileName =
                        if extension = ".json" || includeOptionalParameters then "required_params_grammar"
                        else "required_params_grammar_requiredonly"
                    let expectedGrammarFilePath = Path.Combine(Environment.CurrentDirectory,
                                                               "baselines", "grammarTests", sprintf "%s%s" expectedGrammarFileName extension)
                    let actualGrammarFilePath = Path.Combine(grammarOutputDirectoryPath,
                                                             actualGrammarFileName + extension)
                    let grammarDiff = getLineDifferences expectedGrammarFilePath actualGrammarFilePath
                    let grammarName = if extension = ".json" then "Json" else "Python"
                    let message = sprintf "%s grammar Does not match baseline.  First difference: %A" grammarName grammarDiff
                    Assert.True(grammarDiff.IsNone, message)




        interface IClassFixture<Fixtures.TestSetupAndCleanup>