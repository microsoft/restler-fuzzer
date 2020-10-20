// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

namespace Restler.Test
open System
open System.IO
open Xunit
open SwaggerSpecs
open Utilities

[<Trait("TestCategory", "RealWorld")>]
module RealWorldTests =
    type RealWorldTests(ctx:Fixtures.TestSetupAndCleanup, output:Xunit.Abstractions.ITestOutputHelper) =

        [<Fact>]
        let ``demo_server grammar sanity test`` () =
            Restler.Workflow.generateRestlerGrammar None
                { configs.["demo_server"] with
                      GrammarOutputDirectoryPath = Some ctx.testRootDirPath }
            Assert.True(true)

        interface IClassFixture<Fixtures.TestSetupAndCleanup>