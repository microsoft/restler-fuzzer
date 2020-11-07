// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

namespace Restler.Test
open System
open System.IO
open Xunit

open Restler.Grammar
open Restler.Config
open SwaggerSpecs
open Utilities

[<Trait("TestCategory", "Config")>]
module Config =
    type ConfigTests(ctx:Fixtures.TestSetupAndCleanup, output:Xunit.Abstractions.ITestOutputHelper) =

        [<Fact>]
        /// Combines two API definitions and validates the correct engine settings for per-endpoint dictionaries.
        let ``Swagger config custom dictionary sanity test`` () =
            let grammarOutputDirectoryPath = ctx.testRootDirPath
            if Directory.Exists(grammarOutputDirectoryPath) then Directory.Delete(grammarOutputDirectoryPath, true)

            let multiDictConfig =
                {   Restler.Config.SampleConfig with
                        SwaggerSpecFilePath = None
                        CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, @"swagger\configTests\maindict.json"))
                        UseBodyExamples = Some false
                        ResolveBodyDependencies = true
                        SwaggerSpecConfig =
                            Some [
                                {
                                    SpecFilePath = (Path.Combine(Environment.CurrentDirectory, @"swagger\configTests\swagger1.json"))
                                    DictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, @"swagger\configTests\dict1.json"))
                                    Dictionary = None
                                    AnnotationFilePath = None
                                }
                                {
                                    SpecFilePath = (Path.Combine(Environment.CurrentDirectory, @"swagger\configTests\swagger2.json"))
                                    DictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, @"swagger\configTests\dict2.json"))
                                    Dictionary = None
                                    AnnotationFilePath = None
                                }
                                {
                                    SpecFilePath = (Path.Combine(Environment.CurrentDirectory, @"swagger\configTests\swagger3.json"))
                                    DictionaryFilePath = None
                                    Dictionary = None
                                    AnnotationFilePath = None
                                }
                            ]
                        EngineSettingsFilePath = Some (Path.Combine(Environment.CurrentDirectory, @"swagger\configTests\restlerEngineSettings.json"))
                        GrammarOutputDirectoryPath = Some grammarOutputDirectoryPath
                }

            let newSettingsFilePath = Path.Combine(grammarOutputDirectoryPath, Restler.Workflow.Constants.DefaultEngineSettingsFileName)

            Restler.Workflow.generateRestlerGrammar None multiDictConfig

            match Restler.Engine.Settings.getEngineSettings newSettingsFilePath with
            | Ok perResourceSettings ->
                let getDictionary dictFilePath =
                    match Restler.Dictionary.getDictionary dictFilePath with
                    | Ok d -> Some d
                    | Error _ -> None
                let spec1Dictionary =
                    match perResourceSettings.getPerResourceDictionary "/first" with
                    | Some dFile ->
                        getDictionary (Path.Combine(grammarOutputDirectoryPath, dFile))
                    | None -> None
                let spec2Dictionary =
                    match perResourceSettings.getPerResourceDictionary "/second" with
                    | Some dFile ->
                        getDictionary (Path.Combine(grammarOutputDirectoryPath, dFile))
                    | None -> None
                let spec3Dictionary = perResourceSettings.getPerResourceDictionary "/third"
                let payloadContains (dictionary:Restler.Dictionary.MutationsDictionary option) (payloadName, payload) (isUuidSuffix:bool) =
                    match dictionary with
                    | None -> false
                    | Some d ->
                        let entry =
                            if isUuidSuffix then
                                match d.restler_custom_payload_uuid4_suffix.Value |> Map.tryFind payloadName with
                                | None -> None
                                | Some x -> Some [x]
                            else
                                d.restler_custom_payload.Value |> Map.tryFind payloadName
                        match entry with
                        | None -> false
                        | Some e -> e |> List.contains payload

                // Check that each dictionary contains the custom payload from the source dictionary.
                Assert.True(payloadContains spec1Dictionary ("banana", "banana_1") false, "incorrect output dictionary from spec1, expected to find 'banana_1'")
                Assert.True(payloadContains spec2Dictionary ("apple", "apple_2") false, "incorrect output dictionary from spec2, expected to find 'apple_2'")
                Assert.True(spec3Dictionary.IsNone, "the third spec should not have a dictionary")

                // Check that the main output dictionary has all of the expected "custom_payload_uuid_suffix" values.
                let outputDictionaryFilePath = Path.Combine(grammarOutputDirectoryPath, Restler.Workflow.Constants.NewDictionaryFileName)
                let outputDictionary = getDictionary outputDictionaryFilePath
                Assert.True(payloadContains outputDictionary ("orderId", "orderid") true)
            | Error msg ->
                Assert.True(false, sprintf "Engine settings error: %s" msg)

            // Check that if an engine settings file is not specified, then a default new one is generated.
            Restler.Workflow.generateRestlerGrammar None { multiDictConfig with EngineSettingsFilePath = None }
            match Restler.Engine.Settings.getEngineSettings newSettingsFilePath with
            | Ok _ -> ()
            | Error msg ->
                Assert.True(false, sprintf "Engine settings error when the compiler should have generated the settings: %s" msg)

            // TODO Check that the grammar contains references to the custom payload and uuid suffix.
            let grammarFilePath = Path.Combine(grammarOutputDirectoryPath, Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let grammar = File.ReadAllLines(grammarFilePath)
            let appleCustomPayloadCount = grammar |> Seq.filter (fun line -> line.Contains("primitives.restler_custom_payload(\"apple\", quoted=True),")) |> Seq.length
            let bananaCustomPayloadCount = grammar |> Seq.filter (fun line -> line.Contains("primitives.restler_custom_payload(\"banana\", quoted=True),")) |> Seq.length
            if appleCustomPayloadCount <> 1 then
                Assert.True(false, sprintf "apple custom payload count should be 1, found %d" appleCustomPayloadCount)
            if bananaCustomPayloadCount <> 1 then
                Assert.True(false, sprintf "banana custom payload count should be 1, found %d" bananaCustomPayloadCount)

        [<Fact>]
        let ``Swagger config custom annotations sanity test`` () =
            let grammarOutputDirectoryPath = ctx.testRootDirPath

            // Test that the global annotations produce identical results when added
            // to the Swagger file and externally via a config.
            let config = { Restler.Config.SampleConfig with
                             GrammarOutputDirectoryPath = Some grammarOutputDirectoryPath
                             ResolveBodyDependencies = true
                             UseBodyExamples = Some false
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\annotationTests\pathAnnotation.json"))]
                             CustomDictionaryFilePath = None
                         }
            let externalConfig =
                {   config with
                        SwaggerSpecFilePath = None
                        SwaggerSpecConfig =
                            Some [
                                {
                                    SpecFilePath = (Path.Combine(Environment.CurrentDirectory, @"swagger\annotationTests\pathAnnotationInSeparateFile.json"))
                                    DictionaryFilePath = None
                                    Dictionary = None
                                    AnnotationFilePath = Some (Path.Combine(Environment.CurrentDirectory, @"swagger\annotationTests\globalAnnotations.json"))
                                }
                            ]
                }
            let noAnnotationsConfig =
                {   config with
                        SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\annotationTests\pathAnnotationInSeparateFile.json"))]
                }

            let grammarFilePath = Path.Combine(grammarOutputDirectoryPath, Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let grammarInlineFilePath = Path.Combine(grammarOutputDirectoryPath, "grammarInline.py")
            let grammarExternalFilePath = Path.Combine(grammarOutputDirectoryPath, "grammarExternal.py")
            let grammarNoAnnotationsFilePath = Path.Combine(grammarOutputDirectoryPath, "grammarNoAnnotations.py")

            Restler.Workflow.generateRestlerGrammar None config

            File.Copy(grammarFilePath, grammarInlineFilePath)
            // Delete the grammar file to make sure it gets re-generated
            File.Delete(grammarFilePath)

            // As a test sanity check, make sure the config without global annotations does not  the grammar to make sure it gets re-generated
            Restler.Workflow.generateRestlerGrammar None noAnnotationsConfig
            File.Copy(grammarFilePath, grammarNoAnnotationsFilePath)
            // Delete the grammar file to make sure it gets re-generated
            File.Delete(grammarFilePath)

            let grammarsDiffAfterRemovingAnnotations = getLineDifferences grammarInlineFilePath grammarNoAnnotationsFilePath
            let message = "Test Bug: Found no differences after removing annotations."

            Assert.True(grammarsDiffAfterRemovingAnnotations.IsSome, message)

            Restler.Workflow.generateRestlerGrammar None externalConfig
            File.Copy(grammarFilePath, grammarExternalFilePath)
            // Delete the grammar file to make sure it gets re-generated
            File.Delete(grammarFilePath)

            let grammarsWithAnnotationsDiff = getLineDifferences grammarInlineFilePath grammarExternalFilePath
            let message = sprintf "Found differences, expected none: %A" grammarsWithAnnotationsDiff
            Assert.True(grammarsWithAnnotationsDiff.IsNone, message)

        interface IClassFixture<Fixtures.TestSetupAndCleanup>

