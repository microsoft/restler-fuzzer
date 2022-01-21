// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

namespace Restler.Test
open System
open System.IO
open Xunit

open Restler.Grammar
open Restler.ApiResourceTypes
open Restler.Config
open SwaggerSpecs
open Utilities

[<Trait("TestCategory", "Dependencies")>]
module Dependencies =
    type DependencyTests(ctx:Fixtures.TestSetupAndCleanup, output:Xunit.Abstractions.ITestOutputHelper) =

        let dependenciesResolvedWithoutAnnotations config =
            let swaggerDoc,_ =
                Restler.Swagger.getSwaggerDocument config.SwaggerSpecFilePath.Value.[0] ctx.testRootDirPath
            let dictionary =
                match config.CustomDictionaryFilePath with
                | Some customDictionaryPath when File.Exists customDictionaryPath ->
                    let d = Microsoft.FSharpLu.Json.Compact.deserializeFile<Restler.Dictionary.MutationsDictionary> customDictionaryPath
                    { d with restler_custom_payload_uuid4_suffix = Some (Map.empty<string, string>) }
                | _ -> Restler.Dictionary.DefaultMutationsDictionary

            let grammar,dependencies, _, _ =
                Restler.Compiler.Main.generateRequestGrammar
                                    [{ swaggerDoc = swaggerDoc ; dictionary = None ; globalAnnotations = None;
                                       xMsPathsMapping = None}]
                                    dictionary
                                    config
                                    List.empty
                                    []
            let unresolvedPathDeps =
                dependencies
                |> List.filter (fun d -> d.producer.IsNone)
                |> List.filter (fun d -> d.consumer.parameterKind = ParameterKind.Path)

            dependencies, unresolvedPathDeps


        [<Fact>]
        let ``demo_server path dependencies resolved without annotations`` () =
            let config = configs.["demo_server"]

            let deps, unresolved = dependenciesResolvedWithoutAnnotations config

            let consumerRequests =
                deps
                |> List.filter (fun d -> d.consumer.parameterKind = ParameterKind.Path)
                |> List.map (fun d -> d.consumer.id.RequestId, d.consumer.id.ResourceName)
                |> List.distinct
            // Check the expected number of consumers was extracted
            Assert.True(3 = consumerRequests.Length,
                        sprintf "wrong number of consumers found: %d %A"
                                consumerRequests.Length consumerRequests)
            Assert.True(unresolved |> List.isEmpty,
                        sprintf "found unresolved path dependencies: %A" unresolved)

        [<Fact>]
        let ``inferred put producer`` () =
            let grammarOutputDirectoryPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some grammarOutputDirectoryPath
                             ResolveBodyDependencies = true
                             UseBodyExamples = Some false
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\put_createorupdate.json"))]
                             CustomDictionaryFilePath = None
                         }
            Restler.Workflow.generateRestlerGrammar None config
            let grammarFilePath = Path.Combine(grammarOutputDirectoryPath, "grammar.py")
            let grammar = File.ReadAllText(grammarFilePath)

            // The grammar should not contain any fuzzable resources.
            Assert.False(grammar.Contains("fuzzable"), "Grammar should not contain any fuzzables, everything should be resolved")

            // A new dictionary should be produced with two entries in 'restler_custom_payload_uuid_suffix'
            let dictionaryFilePath = Path.Combine(grammarOutputDirectoryPath, "dict.json")
            let dictionary = Microsoft.FSharpLu.Json.Compact.tryDeserializeFile<Restler.Dictionary.MutationsDictionary> dictionaryFilePath
            match dictionary with
            | Choice2Of2 str -> Assert.True(false, sprintf "dictionary error: %s" str)
            | Choice1Of2 dict ->
                Assert.True(dict.restler_custom_payload_uuid4_suffix.Value.ContainsKey("orderId"))
                Assert.True(dict.restler_custom_payload_uuid4_suffix.Value.ContainsKey("storeId"))

            // Compiling with this dictionary should result in the same grammar.
            let config2 = { config with CustomDictionaryFilePath = Some dictionaryFilePath }
            Restler.Workflow.generateRestlerGrammar None config2
            let grammar2 = File.ReadAllText(grammarFilePath)
            Assert.True((grammar = grammar2))


        [<Fact>]
        let ``GET dependency for path parameter`` () =
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                             ResolveBodyDependencies = true
                             UseBodyExamples = Some true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\get_path_dependencies.json"))]
                             CustomDictionaryFilePath = None
                             AllowGetProducers = true
                         }
            Restler.Workflow.generateRestlerGrammar None config

            // TODO: check that dynamic objects are present when 'allowGetProducers' is true, but not when it's false.
            //
            Assert.True(true)

        /// Test that a full path annotation only to a specified body parameter works.
        [<Fact>]
        let ``path annotation to body parameter`` () =
            let grammarOutputDirectoryPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some grammarOutputDirectoryPath
                             ResolveBodyDependencies = true
                             UseBodyExamples = Some true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\annotationTests\pathAnnotation.json"))]
                             CustomDictionaryFilePath = None
                             AllowGetProducers = true
                         }
            Restler.Workflow.generateRestlerGrammar None config

            // Read the baseline and make sure it matches the expected one
            //
            let expectedGrammarFilePath = Path.Combine(Environment.CurrentDirectory,
                                                       @"baselines\dependencyTests\path_annotation_grammar.py")
            let actualGrammarFilePath = Path.Combine(grammarOutputDirectoryPath,
                                                     Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let grammarDiff = getLineDifferences expectedGrammarFilePath actualGrammarFilePath
            let message = sprintf "Grammar Does not match baseline.  First difference: %A" grammarDiff
            Assert.True(grammarDiff.IsNone, message)

        /// Test that a full path annotation only to a specified body parameter works.
        [<Fact>]
        let ``full path to body parameter in dictionary custom_payload`` () =
            let grammarOutputDirPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some grammarOutputDirPath
                             ResolveBodyDependencies = true
                             UseBodyExamples = Some true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\dictionaryTests\pathDictionaryPayload.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, @"swagger\dictionaryTests\dict.json"))
                             AllowGetProducers = true
                         }
            Restler.Workflow.generateRestlerGrammar None config

            // Read the baseline and make sure it matches the expected one
            //
            let expectedGrammarFilePath = Path.Combine(Environment.CurrentDirectory,
                                                       @"baselines\dependencyTests\path_in_dictionary_payload_grammar.py")
            let actualGrammarFilePath = Path.Combine(grammarOutputDirPath,
                                                     Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let grammarDiff = getLineDifferences expectedGrammarFilePath actualGrammarFilePath
            let message = sprintf "Grammar Does not match baseline.  First difference: %A" grammarDiff
            Assert.True(grammarDiff.IsNone, message)

        /// Regression test for cycles created from body dependencies
        [<Fact>]
        let ``no dependencies when the same body is used in unrelated requests`` () =
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                             ResolveBodyDependencies = true
                             UseBodyExamples = Some true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\dependencyTests\body_dependency_cycles.json"))]
                             CustomDictionaryFilePath = None
                             AllowGetProducers = true
                         }
            Restler.Workflow.generateRestlerGrammar None config

            // Read the dependencies.json and check that there are 3 producer-consumer dependencies.
            let dependencies =
                let dependenciesJsonFilePath = Path.Combine(ctx.testRootDirPath,
                                                            Restler.Workflow.Constants.DependenciesDebugFileName)

                Microsoft.FSharpLu.Json.Compact.deserializeFile<ProducerConsumerDependency list> dependenciesJsonFilePath
            let resolvedDependencies =
                dependencies
                |> Seq.filter (fun dep -> dep.producer.IsSome)

            Assert.True(resolvedDependencies |> Seq.length = 0, "dependencies should not have been inferred.")

        /// Regression test for all-lowercase path dependencies
        [<Fact>]
        let ``dependencies inferred for lowercase container and object`` () =
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                             ResolveBodyDependencies = true
                             UseBodyExamples = Some true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\dependencyTests\lowercase_paths.json"))]
                             CustomDictionaryFilePath = None
                             AllowGetProducers = true
                         }
            Restler.Workflow.generateRestlerGrammar None config

            //// Read the dependencies and check that there are 3 producer-consumer dependencies.
            let dependencies =
                let dependenciesJsonFilePath = Path.Combine(ctx.testRootDirPath,
                                                            Restler.Workflow.Constants.DependenciesDebugFileName)

                Microsoft.FSharpLu.Json.Compact.deserializeFile<ProducerConsumerDependency list> dependenciesJsonFilePath
            let resolvedDependencies =
                dependencies
                |> Seq.filter (fun dep -> dep.producer.IsSome)

            let expectedCount = 3
            let actualCount = resolvedDependencies |> Seq.length
            let message = sprintf "The number of dependencies is not correct (%d <> %d)" expectedCount actualCount
            Assert.True((expectedCount = actualCount), message)


        /// Regression test for workaround implemented in RESTler to infer dependencies when
        /// there are case differences in path names, up to the resource name.
        /// This workaround only applies for the path up to the resource name, i.e. 'name' below
        /// must still be properly camel cased.
        /// This workaround is only applicable to paths, not queries or bodies.
        /// For example:
        ///   Producer: PUT /dataItem/dataItemName
        ///   Consumer: PUT /dataItem/dataITeMName/dataPoint
        [<Fact>]
        let ``inconsistent camel case is fixed by RESTler`` () =
            let config = { Restler.Config.SampleConfig with
                             GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\dependencyTests\inconsistent_casing_paths.json"))]
                             CustomDictionaryFilePath = None
                         }
            Restler.Workflow.generateRestlerGrammar None config

            // Read the dependencies.json and check that there are 3 producer-consumer dependencies.
            let dependencies =
                let dependenciesJsonFilePath = Path.Combine(ctx.testRootDirPath,
                                                            Restler.Workflow.Constants.DependenciesDebugFileName)

                Microsoft.FSharpLu.Json.Compact.deserializeFile<ProducerConsumerDependency list> dependenciesJsonFilePath
            let resolvedDependencies =
                dependencies
                |> Seq.filter (fun dep -> dep.producer.IsSome)
                |> Seq.map (fun dep -> dep.consumer, dep.producer.Value)

            let expectedCount = 8
            let actualCount = resolvedDependencies |> Seq.length
            let message = sprintf "The number of dependencies is not correct (%d <> %d)" expectedCount actualCount
            Assert.True((expectedCount = actualCount), message)

        /// Test that a full path annotation only to a specified body parameter works.
        [<Fact>]
        let ``patch request body parameter producers from post`` () =
            let grammarOutputDirPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some grammarOutputDirPath
                             ResolveBodyDependencies = true
                             UseBodyExamples = Some true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\dependencyTests\post_patch_dependency.json"))]
                             AllowGetProducers = true
                         }
            Restler.Workflow.generateRestlerGrammar None config

            // Make sure there are three dynamic objects.
            //
            let grammarFilePath = Path.Combine(grammarOutputDirPath,
                                               Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let grammar = File.ReadAllText(grammarFilePath)
            let grammarDynamicObjects =
                [
                    "_system_environments_post_id.reader()"
                    "_system_environments_post_url.reader()"
                    "_system_environments_post_name.reader()"
                ]
            grammarDynamicObjects
            |> Seq.iter (fun x -> Assert.True(grammar.Contains(x),
                                              sprintf "Grammar does not contain %s" x))

        [<Fact>]
        let ``array dependencies with multiple array items`` () =
            // A custom dictionary payload is considered a dependency payload.
            let customDictionary = Some ("{ \"restler_custom_payload\":\
                                            { \"item_descriptions\": [\"[zzz, yyy]\"], \
                                              \"callback_parameters\": [\"{\\\"data1\\\": 5}\"] } }\
                                         ")
            let grammarOutputDirPath = ctx.testRootDirPath

            let config = { Restler.Config.SampleConfig with
                             SwaggerSpecConfig =
                                Some
                                  [{
                                      SpecFilePath =
                                         Path.Combine(Environment.CurrentDirectory, @"swagger\dependencyTests\array_dep_multiple_items.json")
                                      Dictionary = customDictionary
                                      DictionaryFilePath = None
                                      AnnotationFilePath = None
                                  }]
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some grammarOutputDirPath
                             ResolveBodyDependencies = true
                             ResolveQueryDependencies = true
                             UseBodyExamples = None
                         }

            Restler.Workflow.generateRestlerGrammar None config
            // Make sure the grammar file exists and there is just one dynamic object for the array, regardless of how
            // many elements it had before.
            let grammarFilePath = Path.Combine(grammarOutputDirPath,
                                               Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let grammar = File.ReadAllLines(grammarFilePath)
            let grammarDynamicObject = "primitives.restler_custom_payload(\"item_descriptions\", quoted=False),"
            let numberOfDynamicObjects = grammar |> Seq.filter (fun x -> x.Contains(grammarDynamicObject)) |> Seq.length
            Assert.Equal( 1, numberOfDynamicObjects)

        [<Fact>]
        let ``input producers work with annotations`` () =
            let grammarOutputDirPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some grammarOutputDirPath
                             ResolveBodyDependencies = true
                             UseBodyExamples = Some true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\dependencyTests\input_producer_spec.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, @"swagger\dependencyTests\input_producer_dict.json"))
                             AnnotationFilePath = Some (Path.Combine(Environment.CurrentDirectory, @"swagger\dependencyTests\input_producer_annotations.json"))
                             AllowGetProducers = true
                         }
            Restler.Workflow.generateRestlerGrammar None config

            let grammarFilePath = Path.Combine(grammarOutputDirPath,
                                               Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let grammar = File.ReadAllText(grammarFilePath)

            Assert.True(grammar.Contains("""restler_custom_payload_uuid4_suffix("fileId", writer=_file__fileId__post_fileId_path.writer())"""))
            Assert.True(grammar.Contains("""restler_static_string(_file__fileId__post_fileId_path.reader(), quoted=False)"""))

            // Validate (tag, label) annotation.  tag - body producer (jsonpath), label: path parameter.
            Assert.True(grammar.Contains("""primitives.restler_custom_payload("tag", quoted=True, writer=_archive_post_tag.writer())"""))
            Assert.True(grammar.Contains("""restler_static_string(_archive_post_tag.reader(), quoted=True)"""))

            // Validate (name, name) annotation.  name - body producer (POST) and consumer (PUT).
            Assert.True(grammar.Contains("""primitives.restler_fuzzable_object("{ \"fuzz\": false }", writer=_archive_post_name.writer())"""))
            Assert.True(grammar.Contains("""primitives.restler_static_string(_archive_post_name.reader(), quoted=False)"""))

            // Validate (hash, sig) annotation.  hash - header producer (POST), sig - header consumer (PUT)
            Assert.True(grammar.Contains("""primitives.restler_custom_payload_query("hash", writer=_archive_post_hash_query.writer())"""))
            Assert.True(grammar.Contains("""primitives.restler_static_string(_archive_post_hash_query.reader(), quoted=False)"""))




        /// Test that the entire body should be able to be replaced with a custom payload
        /// from the dictionary
        [<Fact>]
        let ``replace entire body with custom payload`` () =
            let grammarOutputDirectoryPath = ctx.testRootDirPath

            let customDictionaryText = "{ \"restler_custom_payload\":\
                                                { \"/subnets/{subnetName}/get/__body__\": [\"abc\"] } }\
                                       "
            // TODO: passing in the dictionary directly via 'SwaggerSpecConfig' is not working.
            // Write out the dictionary until the but is fixed
            //
            let dictionaryFilePath =
                Path.Combine(grammarOutputDirectoryPath,
                             "input_dict.json")
            File.WriteAllText(dictionaryFilePath, customDictionaryText)

            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some grammarOutputDirectoryPath
                             ResolveBodyDependencies = true
                             UseBodyExamples = Some true
                             SwaggerSpecFilePath = Some [Path.Combine(Environment.CurrentDirectory, @"swagger\dependencyTests\subnet_id.json")]
                             AllowGetProducers = true
                             CustomDictionaryFilePath = Some dictionaryFilePath
                         }

            Restler.Workflow.generateRestlerGrammar None config

            let grammarFilePath = Path.Combine(grammarOutputDirectoryPath,
                                               Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let grammar = File.ReadAllText(grammarFilePath)

            Assert.True(grammar.Contains("""restler_custom_payload("/subnets/{subnetName}/get/__body__", quoted=False)"""))

        [<Fact>]
        let ``response headers can be used as producers`` () =
            let grammarOutputDirPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some grammarOutputDirPath
                             ResolveBodyDependencies = true
                             UseBodyExamples = Some true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\dependencyTests\response_headers.json"))]
                             CustomDictionaryFilePath = None
                             AnnotationFilePath = None
                             AllowGetProducers = true
                         }
            Restler.Workflow.generateRestlerGrammar None config

            let grammarFilePath = Path.Combine(grammarOutputDirPath,
                                               Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let grammar = File.ReadAllText(grammarFilePath)

            let expectedGrammarFilePath = Path.Combine(Environment.CurrentDirectory,
                                                       @"baselines\dependencyTests\header_response_writer_grammar.py")
            let actualGrammarFilePath = Path.Combine(grammarOutputDirPath,
                                                     Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let grammarDiff = getLineDifferences expectedGrammarFilePath actualGrammarFilePath
            let message = sprintf "Grammar (test without annotations) does not match baseline.  First difference: %A" grammarDiff
            Assert.True(grammarDiff.IsNone, message)

            // Confirm the same works with annotations
            let configWithAnnotations = { config with
                                            AnnotationFilePath = Some (Path.Combine(Environment.CurrentDirectory, @"swagger\dependencyTests\response_headers_annotations.json"))}
            Restler.Workflow.generateRestlerGrammar None configWithAnnotations

            let expectedGrammarFilePath = Path.Combine(Environment.CurrentDirectory,
                                                       @"baselines\dependencyTests\header_response_writer_annotation_grammar.py")
            let grammarDiff = getLineDifferences expectedGrammarFilePath actualGrammarFilePath
            let message = sprintf "Grammar (test with annotations) does not match baseline.  First difference: %A" grammarDiff
            Assert.True(grammarDiff.IsNone, message)

        [<Fact>]
        let ``headers in request and responses`` () =
            let grammarOutputDirPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some grammarOutputDirPath
                             ResolveBodyDependencies = true
                             ResolveHeaderDependencies = true
                             UseBodyExamples = Some true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\dependencyTests\header_deps.json"))]
                             CustomDictionaryFilePath = None
                             AnnotationFilePath = None
                             AllowGetProducers = true
                         }
            Restler.Workflow.generateRestlerGrammar None config

            let actualGrammarFilePath = Path.Combine(grammarOutputDirPath,
                                                     Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let expectedGrammarFilePath = Path.Combine(Environment.CurrentDirectory,
                                                       @"baselines\dependencyTests\header_deps_grammar.py")

            // This scenario should work with annotations only.
            let configWithAnnotations = { config with
                                            AnnotationFilePath = Some (Path.Combine(Environment.CurrentDirectory, @"swagger\dependencyTests\header_deps_annotations.json"))}
            Restler.Workflow.generateRestlerGrammar None configWithAnnotations

            let grammarDiff = getLineDifferences expectedGrammarFilePath actualGrammarFilePath
            let message = sprintf "Grammar (test with annotations) does not match baseline.  First difference: %A" grammarDiff
            Assert.True(grammarDiff.IsNone, message)

            Restler.Workflow.generateRestlerGrammar None config
            let grammarDiff = getLineDifferences expectedGrammarFilePath actualGrammarFilePath
            let message = "Grammar (test without annotations) matches the baseline, this is not expected"
            Assert.True(grammarDiff.IsSome, message)


        /// Test that with annotations there are new dependencies added in the grammar, both for requests without any dependencies
        /// and with requests that already contain regular request-response dependencies
        [<Fact>]
        let ``ordering constraints`` () =
            /// This test uses a baseline grammar.py to make sure variables appear in the correct locations.
            let grammarOutputDirPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some grammarOutputDirPath
                             ResolveBodyDependencies = true
                             ResolveHeaderDependencies = true
                             UseBodyExamples = Some true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\dependencyTests\ordering_test.json"))]
                             CustomDictionaryFilePath = None
                             AnnotationFilePath = None
                             AllowGetProducers = true
                         }
            Restler.Workflow.generateRestlerGrammar None config

            let actualGrammarFilePath = Path.Combine(grammarOutputDirPath,
                                                     Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let expectedGrammarFilePath = Path.Combine(Environment.CurrentDirectory,
                                                       @"baselines\dependencyTests\ordering_test_grammar.py")

            let configWithAnnotations = { config with
                                            AnnotationFilePath = Some (Path.Combine(Environment.CurrentDirectory, @"swagger\dependencyTests\ordering_test_annotations.json"))}
            Restler.Workflow.generateRestlerGrammar None configWithAnnotations

            let grammarDiff = getLineDifferences expectedGrammarFilePath actualGrammarFilePath
            let message = sprintf "Grammar (test with annotations) does not match baseline.  First difference: %A" grammarDiff
            Assert.True(grammarDiff.IsNone, message)

        interface IClassFixture<Fixtures.TestSetupAndCleanup>

