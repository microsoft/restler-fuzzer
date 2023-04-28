// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

namespace Restler.Test
open System
open System.IO
open Xunit
open Restler.Test.Utilities
open Restler.Config

[<Trait("TestCategory", "Examples")>]
module Examples =
    type ExampleTests(ctx:Fixtures.TestSetupAndCleanup, output:Xunit.Abstractions.ITestOutputHelper) =

        [<Fact>]
        let ``no example in grammar with dependencies`` () =
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                             ResolveBodyDependencies = true
                             UseBodyExamples = Some false
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "example_demo1.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, "swagger", "example_demo_dictionary.json"))
                         }
            Restler.Workflow.generateRestlerGrammar config
            let grammarFilePath = Path.Combine(ctx.testRootDirPath, "grammar.py")
            let grammar = File.ReadAllText(grammarFilePath)

            // The grammar should not contain the fruit codes from the example
            Assert.False(grammar.Contains("999"))

            // The grammar should not contain the store codes from the example
            Assert.False(grammar.Contains("23456"))

            Assert.True(grammar.Contains("restler_fuzzable_datetime"))
            Assert.True(grammar.Contains("restler_fuzzable_object"))

        [<Fact>]
        let ``example config file test`` () =
            let exampleConfigFilePath = Path.Combine(Environment.CurrentDirectory, "swagger", "example_config_file.json")
            let x = Restler.Examples.tryDeserializeExampleConfigFile exampleConfigFilePath
            Assert.True(x.IsSome)
            Assert.True(x.Value.paths |> List.exists (fun x -> x.path = "/vm"))

        [<Fact>]
        /// Test that uses both body and query examples, and tests
        /// that the grammar is correct when (a) examples are referenced from the spec,
        /// and (b) an external example config file is used.
        let ``array example in grammar without dependencies`` () =
            let grammarDirectoryPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some grammarDirectoryPath
                             ResolveBodyDependencies = false
                             UseBodyExamples = Some true
                             UseQueryExamples = Some true
                             DataFuzzing = true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "array_example.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, "swagger", "example_demo_dictionary.json"))
                         }
            // Run the example test using the Swagger example and using the external example.
            let runTest testConfig =
                Restler.Workflow.generateRestlerGrammar testConfig
                // Read the baseline and make sure it matches the expected one
                //
                let expectedGrammarFilePath = Path.Combine(Environment.CurrentDirectory,
                                                           "baselines", "exampleTests", "array_example_grammar.py")
                let actualGrammarFilePath = Path.Combine(grammarDirectoryPath,
                                                         Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
                let grammarDiff = getLineDifferences expectedGrammarFilePath actualGrammarFilePath
                let message = sprintf "Grammar Does not match baseline.  First difference: %A" grammarDiff
                Assert.True(grammarDiff.IsNone, message)

            runTest config
            // Also test this scenario when 'DataFuzzing' is false.  This tests the case where
            // only examples are used for the schema.
            runTest { config with DataFuzzing = false }
            let exampleConfigFile = Path.Combine(Environment.CurrentDirectory, "swagger", "example_config_file.json")
            let config =
                 { config with
                        SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "array_example_external.json"))]
                        ExampleConfigFilePath = Some exampleConfigFile }
            runTest config

        [<Fact>]
        let ``array example where the array itself is a dynamic object`` () =
            let grammarDirectoryPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some grammarDirectoryPath
                             ResolveBodyDependencies = false
                             UseBodyExamples = Some true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "array_example.json"))]
                             AnnotationFilePath = Some (Path.Combine(Environment.CurrentDirectory, "swagger", "array_example_annotations.json"))
                         }
            Restler.Workflow.generateRestlerGrammar config
            let grammarFilePath = Path.Combine(grammarDirectoryPath,
                                               Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let grammar = File.ReadAllText(grammarFilePath)
            // Check that the grammar contains the array dependency (here, it is an input producer)
            // and the array item dependency
            Assert.True(grammar.Contains("primitives.restler_static_string(_stores__storeId__order_post_order_items.reader(), quoted=False),"))
            Assert.True(grammar.Contains("primitives.restler_static_string(_stores__storeId__order_post_order_items_0.reader(), quoted=False),"))

        [<Fact>]
        let ``object example in grammar without dependencies`` () =
            let grammarDirectoryPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some grammarDirectoryPath
                             ResolveBodyDependencies = false
                             UseBodyExamples = Some true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "object_example.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, "swagger", "example_demo_dictionary.json"))
                         }
            Restler.Workflow.generateRestlerGrammar config
            let grammarFilePath = Path.Combine(grammarDirectoryPath,
                                               Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let grammar = File.ReadAllText(grammarFilePath)
            // Check that the grammar contains the object example
            //examples=["{\"tag1\":\"value1\",\"tag2\":\"value2\"}"]
            Assert.True(grammar.Contains("\\\"tag1\\\":\\\"value1\\\"") && grammar.Contains("\\\"tag2\\\":\\\"value2\\\""))

        [<Fact>]
        let ``allof property omitted in example`` () =

            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                             ResolveBodyDependencies = false
                             UseBodyExamples = Some true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "secgroup_example.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, "swagger", "dict_secgroup_example.json"))
                         }
            Restler.Workflow.generateRestlerGrammar config

        [<Fact>]
        let ``empty array example in grammar`` () =
            let swaggerSpecConfig =
                  {
                      SpecFilePath =
                         (Path.Combine(Environment.CurrentDirectory, "swagger", "empty_array_example.json"))
                      Dictionary = None
                      DictionaryFilePath = None
                      AnnotationFilePath = None
                  }
            let config = { Restler.Config.SampleConfig with
                             SwaggerSpecConfig = Some [swaggerSpecConfig]
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                             ResolveBodyDependencies = false
                             UseBodyExamples = Some true
                         }

            let resolveDependencies = [true; false]
            resolveDependencies
            |> List.iter (fun x ->
                            Restler.Workflow.generateRestlerGrammar
                                { config with
                                    ResolveBodyDependencies = x
                                    ResolveQueryDependencies = x }
                            )
            // Also test that an empty array that is a custom payload works
            // This is a special case, because empty arrays are represented without a leaf node
            let customDictionary = Some "{ \"restler_custom_payload\": { \"item_descriptions\": [\"zzz\"] }}"

            Restler.Workflow.generateRestlerGrammar
                { config with
                    ResolveBodyDependencies = true
                    ResolveQueryDependencies = true
                    SwaggerSpecConfig = Some [{ swaggerSpecConfig with Dictionary = customDictionary }]
                }

        [<Fact>]
        let ``header example with and without dependencies`` () =
            let grammarOutputDirectoryPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some grammarOutputDirectoryPath
                             UseHeaderExamples = Some true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "headers.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, "swagger", "headers_dict.json"))
                         }
            Restler.Workflow.generateRestlerGrammar config
            let grammarFilePath = Path.Combine(grammarOutputDirectoryPath, "grammar.py")
            let grammar = File.ReadAllText(grammarFilePath)

            // The grammar should only contain the computer dimensions, because
            // computerName is missing from the example
            Assert.False(grammar.Contains("primitives.restler_static_string(\"computerName: \")"))
            Assert.True(grammar.Contains("primitives.restler_static_string(\"computerDimensions: \")"))
            // primitives.restler_fuzzable_string("fuzzstring", quoted=False, examples=["\"quotedString\""]),
            Assert.True(grammar.Contains("primitives.restler_fuzzable_string(\"fuzzstring\", quoted=False, examples=[\"\"\"\\\"quotedString\\\"\"\"\"])"))

            // The grammar should contain the array items from the example
            Assert.True(grammar.Contains("1.11"))
            Assert.True(grammar.Contains("2.22"))

            // The grammar contains the custom payload element
            Assert.True(grammar.Contains("primitives.restler_custom_payload_header(\"rating\"),"))
            Assert.True(grammar.Contains("primitives.restler_custom_payload_header(\"extra1\"),"))
            Assert.True(grammar.Contains("primitives.restler_custom_payload_header(\"extra2\"),"))

        [<Fact>]
        let ``example in grammar without dependencies`` () =

            // Make sure the same test works on yaml and json
            let extensions = [".json" ; ".yaml"]
            for extension in extensions do
                let config = { Restler.Config.SampleConfig with
                                 IncludeOptionalParameters = true
                                 GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                                 ResolveBodyDependencies = false
                                 UseBodyExamples = Some true
                                 SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory,
                                                                            "swagger", sprintf "example_demo1%s" extension))]
                                 CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, "swagger", "example_demo_dictionary.json"))
                             }
                Restler.Workflow.generateRestlerGrammar config
                let grammarFilePath = Path.Combine(ctx.testRootDirPath, "grammar.py")
                let grammar = File.ReadAllText(grammarFilePath)

                // The grammar should contain the fruit codes from the example
                Assert.True(grammar.Contains("999"))

                // The grammar should contain the store codes from the example
                Assert.True(grammar.Contains("78910"))

                // The grammar should contain the bag type from the example
                Assert.True(grammar.Contains("paperfestive"))

        [<Fact>]
        let ``example in grammar with dependencies`` () =
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                             ResolveBodyDependencies = true
                             UseBodyExamples = Some true
                             DiscoverExamples = true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "example_demo1.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, "swagger", "example_demo_dictionary.json"))
                         }
            Restler.Workflow.generateRestlerGrammar config
            let grammarFilePath = Path.Combine(ctx.testRootDirPath, "grammar.py")

            let grammar = File.ReadAllText(grammarFilePath)

            // The grammar should contain the fruit codes from the example (which do not have a dependency)
            Assert.True(grammar.Contains("999"))

            // The grammar should not contain the store code from the top level
            // in the example body - this should be a dynamic object
            Assert.False(grammar.Contains("23456"))

            // The grammar should not contain the bag type from the example, dictionary value should be used
            Assert.False(grammar.Contains("paperfestive"))

            Assert.True(grammar.Contains("restler_custom_payload(\"bagType\", quoted=True)"))

        [<Fact>]
        let ``Logic example in grammar with dependencies`` () =
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                             ResolveBodyDependencies = true
                             UseBodyExamples = Some true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "example_demo.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, "swagger", "example_demo_dictionary.json"))
                         }
            Restler.Workflow.generateRestlerGrammar config
            let grammarFilePath = Path.Combine(ctx.testRootDirPath, "grammar.py")

            let grammar = File.ReadAllText(grammarFilePath)

            // The grammar should contain the fruit codes from the example (which do not have a dependency)
            Assert.True(true)

        [<Fact>]
        /// Subnet ID example.
        /// This tests that:
        /// - for an object name (e.g. 'blogEntry') of an object that contains an 'id'
        ///      if there is a producer of 'id' whose endpoint ends with '/blogs' or /blogs/{blogName}, then
        ///      this producer is used.
        /// - the same works when 'blogEntries' is a list (i.e. when the parent 'blog' is a list property name,
        //     which contains a list of 'id's.
        /// This does not test the case where the producer container is in the body of another request, e.g.
        /// if there is a POST /item request that has a body with {"blog" : {"name": "x", ...<blog body>...}}
        /// This will be covered in a different test.
        let ``body dependency nested object can be inferred via parent`` () =
            let grammarOutputDirectoryPath =  ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                            IncludeOptionalParameters = true
                            GrammarOutputDirectoryPath = Some grammarOutputDirectoryPath
                            ResolveBodyDependencies = true
                            ResolveQueryDependencies = true
                            UseBodyExamples = Some true
                            DataFuzzing = true  // TODO: also test with false, dependencies here should work in both cases.
                            SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "dependencyTests", "subnet_id.json"))]
                            CustomDictionaryFilePath = None
                         }
            Restler.Workflow.generateRestlerGrammar config
            let grammarFilePath = Path.Combine(grammarOutputDirectoryPath, "grammar.py")
            let grammar = File.ReadAllText(grammarFilePath)

            // Note: the subnet name for creating a virtual network should not be a dynamic object (per usage of the API).
            // RESTler cannot tell whether the PUT /api/virtualNetworks creates a new subnet or requires plugging in values from
            // an existing subnet.
            let grammarDynamicObjects =
                [
                    "_subnets__subnetName__put_id.reader()"  // {"subnet" : { "id"}}
                    "_subnets__subnetName__put_name.reader()"  // {"subnets": [{"name": "..." , "properties": "..."}]}
                    // Note: 'properties' is not inferred because Subnet.Properties is not a leaf object
                    // "_subnets__subnetName__put_properties.reader()"
                ]

            grammarDynamicObjects |> Seq.iter (fun x -> Assert.True(grammar.Contains(x), sprintf "Grammar does not contain %s" x))

        [<Fact>]
        let ``nested objects naming sanity test``() =
            let grammarOutputDirPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                            IncludeOptionalParameters = true
                            GrammarOutputDirectoryPath = Some grammarOutputDirPath
                            ResolveBodyDependencies = true
                            ResolveQueryDependencies = true
                            UseBodyExamples = Some true
                            SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "dependencyTests", "nested_objects_naming.json"))]
                            CustomDictionaryFilePath = None
                         }
            Restler.Workflow.generateRestlerGrammar config
            let grammarFilePath = Path.Combine(grammarOutputDirPath, "grammar.py")
            let grammar = File.ReadAllText(grammarFilePath)

            // Note: the subnet name for creating a virtual network should not be a dynamic object (per usage of the API).
            // RESTler cannot tell whether the PUT /api/virtualNetworks creates a new subnet or requires plugging in values from
            // an existing subnet.
            let grammarDynamicObjects =
                [
                    "_publicIPAddresses__publicIpAddressName__put_id.reader()"
                    "_virtualNetworkTaps__tapName__put_id.reader()"
                ]

            grammarDynamicObjects
            |> Seq.iter (fun x -> Assert.True(grammar.Contains(x), sprintf "Grammar does not contain %s" x))

        [<Fact>]

        /// This tests the following real-world case:
        // Test frontendIpConfiguration.id and frontendPort.id examples from real-world Swagger spec ApplicationGateway.json
            // In the same payload, first:
            //"frontendIPConfigurations": [
            //  {
            //    "name": "appgwfip",
            //    "properties": {
            //      "publicIPAddress": {
            //        "id": "/subscriptions/subid/resourceGroups/rg1/providers/Microsoft.Network/publicIPAddresses/appgwpip"
            //      }
            //    }
            //  }
            //
            //"frontendPorts": [
            //  {
            //    "name": "appgwfp",
            //    "properties": {
            //      "port": 443
            //    }
            //  },
            //
            //then later:
            //"frontendIPConfiguration": {
            //  "id": "/subscriptions/subid/resourceGroups/rg1/providers/Microsoft.Network/applicationGateways/appgw/frontendIPConfigurations/appgwfip"
            //},
            //"frontendPort": {
            //  "id": "/subscriptions/subid/resourceGroups/rg1/providers/Microsoft.Network/applicationGateways/appgw/frontendPorts/appgwfp"
            //},
            // The response contains:
            //"frontendPorts": [
            //  {
            //    "name": "appgwfp",
            //    "id": "/subscriptions/subid/resourceGroups/rg1/providers/Microsoft.Network/applicationGateways/appgw/frontendPorts/appgwfp",
            //    "properties": {
            //      "provisioningState": "Succeeded",
            //      "port": 443
            //    }
            //  }],
        // Note: the example tested here is purposely testing both the cases where the example ID is correct and incorrect (the
        // latter means that the 'id' value does not match the path).
        // Having invalid IDs in the example tests that RESTler can model a producer-consumer in the same request
        // *without* the presence of an example path.
        let ``body payload contains both producer and consumer`` () =
            let grammarOutputDirectoryPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                            IncludeOptionalParameters = true
                            GrammarOutputDirectoryPath = Some grammarOutputDirectoryPath
                            ResolveBodyDependencies = true
                            ResolveQueryDependencies = true
                            UseBodyExamples = Some true
                            SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "dependencyTests", "frontend_port_id.json"))]
                            CustomDictionaryFilePath = None
                         }
            Restler.Workflow.generateRestlerGrammar config
            let grammarFilePath = Path.Combine(grammarOutputDirectoryPath, "grammar.py")
            let grammar = File.ReadAllText(grammarFilePath)

            // Make sure the grammar contains expected partial resource IDs (from the example)
            Assert.True(grammar.Contains("primitives.restler_static_string(\"/frontendPorts/\")"))
            Assert.True(grammar.Contains("primitives.restler_static_string(\"/frontendIPConfigurations/\")"))
            Assert.True(grammar.Contains("primitives.restler_custom_payload_uuid4_suffix(\"frontendPorts_name\", quoted=True)"))
            Assert.True(grammar.Contains("primitives.restler_custom_payload_uuid4_suffix(\"frontendIPConfigurations_name\", quoted=True)"))
            Assert.False(grammar.Contains("primitives.restler_custom_payload_uuid4_suffix(\"frontendPort_name\", quoted=True)"))
            Assert.False(grammar.Contains("primitives.restler_custom_payload_uuid4_suffix(\"frontendIPConfiguration_name\", quoted=True)"))

            Assert.True(grammar.Contains("appgwipc")) // This does not have a producer
            Assert.False(grammar.Contains("appgwfip"))
            Assert.False(grammar.Contains("appgwfp"))

            // Make sure the grammar does not contain the original example values.
            // This is a nearly duplicate check to the above, made to be absolutely sure the example values are not used.
            let exampleResourceIds = [
                "/subscriptions/subid/resourceGroups/rg1/providers/Microsoft.Network/applicationGateways/appgw/frontendPorts/appgwfp"
                "/subscriptions/subid/resourceGroups/rg1/providers/Microsoft.Network/applicationGateways/appgw/frontendIPConfigurations/appgwfip"
            ]
            exampleResourceIds |> Seq.iter (fun x -> Assert.False(grammar.Contains(x)))

            // A new dictionary should be produced with the above entries in 'restler_custom_payload_uuid_suffix'
            let dictionaryFilePath = Path.Combine(grammarOutputDirectoryPath, "dict.json")
            let dictionary = Restler.Utilities.JsonSerialization.tryDeserializeFile<Restler.Dictionary.MutationsDictionary> dictionaryFilePath
            match dictionary with
            | Choice2Of2 str -> Assert.True(false, sprintf "dictionary error: %s" str)
            | Choice1Of2 dict ->
                Assert.True(dict.restler_custom_payload_uuid4_suffix.Value.ContainsKey("frontendIPConfigurations_name"))
                Assert.True(dict.restler_custom_payload_uuid4_suffix.Value.ContainsKey("frontendPorts_name"))

        [<Fact>]
        /// When a PUT for /resourceA/{resourceAName} creates a child resource /resourceB/resourceBName via a payload in the body,
        /// test that a subsequent GET for the child resource is able to find the producer endpoint 'resourceA' and get 'resourceBName' from
        /// parsing the returned payload.
        /// Note: this test uses examples, but does not depend on examples.
        /// Note: taken from NRP API, 'ipConfigurations' produced with 'networkInterface'.
        let ``GET dependencies can be inferred from body payload `` () =
            let config = { Restler.Config.SampleConfig with
                            IncludeOptionalParameters = true
                            GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                            ResolveBodyDependencies = true
                            ResolveQueryDependencies = true
                            UseBodyExamples = Some true
                            SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "DependencyTests", "ip_configurations_get.json"))]
                            CustomDictionaryFilePath = None
                         }
            Restler.Workflow.generateRestlerGrammar config
            let grammarFilePath = Path.Combine(ctx.testRootDirPath, "grammar.py")
            let grammar = File.ReadAllText(grammarFilePath)

            Assert.True(grammar.Contains("_networkInterfaces__networkInterfaceName__put_properties_ipConfigurations_0_name.reader()"))

        [<Fact>]
        let ``inline examples are used instead of fuzzstring`` () =
            let grammarOutputDirectoryPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             // Make sure inline examples are used even if using examples is not specified
                             UseQueryExamples = None
                             UseBodyExamples = None
                             GrammarOutputDirectoryPath = Some grammarOutputDirectoryPath
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "inline_examples.json"))]
                             CustomDictionaryFilePath = None
                         }
            Restler.Workflow.generateRestlerGrammar config
            let grammarFilePath = Path.Combine(grammarOutputDirectoryPath, "grammar.py")
            let grammar = File.ReadAllText(grammarFilePath)

            Assert.True(grammar.Contains("primitives.restler_fuzzable_string(\"fuzzstring\", quoted=True, examples=[\"i5\"]),"))
            Assert.True(grammar.Contains("primitives.restler_fuzzable_int(\"1\", examples=[\"32\"]),"))

            Assert.True(grammar.Contains("primitives.restler_fuzzable_string(\"fuzzstring\", quoted=False, examples=[\"inline_example_value_laptop1\"]),"))

            Assert.True(grammar.Contains("primitives.restler_fuzzable_string(\"fuzzstring\", quoted=False, examples=[\"inline_ex_2\"]),"))
            Assert.True(grammar.Contains("primitives.restler_fuzzable_string(\"fuzzstring\", quoted=False, examples=[None]),"))

            Assert.True(grammar.Contains("primitives.restler_fuzzable_number(\"1.23\", examples=[\"1.67\"]),"))

        /// Test that 'exactCopy' does not add extra quotes
        [<Fact>]
        let ``exactCopy values are correct`` () =
            let grammarOutputDirectoryPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some grammarOutputDirectoryPath
                             ResolveBodyDependencies = false
                             UseBodyExamples = Some true
                             UseQueryExamples = Some true
                             DataFuzzing = true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "exactCopy", "array_example.json"))]
                         }

            let exampleConfigFile = {
                filePath = Path.Combine(Environment.CurrentDirectory, "swagger", "exactCopy", "examples.json")
                exactCopy = true
            }

            let exactCopyTestConfig = { config with ExampleConfigFiles = Some [ exampleConfigFile ] }
            Restler.Workflow.generateRestlerGrammar exactCopyTestConfig
            let grammarFilePath = Path.Combine(grammarOutputDirectoryPath, Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let grammar = File.ReadAllText(grammarFilePath)
            Assert.True(grammar.Contains("primitives.restler_static_string(\"2020-02-02\")"))

            let testConfig = { config with ExampleConfigFiles = Some [ {exampleConfigFile with exactCopy = false }] }
            Restler.Workflow.generateRestlerGrammar testConfig

            let grammarFilePath = Path.Combine(grammarOutputDirectoryPath, Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let grammar = File.ReadAllText(grammarFilePath)
            Assert.True(grammar.Contains("primitives.restler_fuzzable_string(\"fuzzstring\", quoted=False, examples=[\"2020-02-02\"])"))
            /// Also test to make sure that 'exactCopy : true' filters out the parameters that are not declared in the spec
            Assert.False(grammar.Contains("ddd"))


        /// Test that when optional parameters are excluded, they are still present if added with an example payload.
        [<Fact>]
        let ``examples with optional parameters`` () =
            let grammarOutputDirectoryPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = false
                             GrammarOutputDirectoryPath = Some grammarOutputDirectoryPath
                             ResolveBodyDependencies = false
                             UseQueryExamples = Some true
                             DataFuzzing = true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "exampleTests", "optional_params.json"))]
                         }

            let exampleConfigFile = {
                filePath = Path.Combine(Environment.CurrentDirectory, "swagger", "exampleTests", "optional_params_example.json")
                exactCopy = false
            }

            let testConfig = { config with ExampleConfigFiles = Some [ exampleConfigFile ] }
            Restler.Workflow.generateRestlerGrammar testConfig

            let grammarFilePath = Path.Combine(grammarOutputDirectoryPath, Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let grammar = File.ReadAllText(grammarFilePath)
            Assert.True(grammar.Contains("required-param"))
            Assert.True(grammar.Contains("optional-param"))


        /// Test that the grammar is correct when the entire body is replaced by an example payload.
        /// Both 'exactCopy' settings should be tested.
        [<Fact>]
        let ``replace entire body with example`` () =
            let grammarOutputDirectoryPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = false
                             GrammarOutputDirectoryPath = Some grammarOutputDirectoryPath
                             ResolveBodyDependencies = false
                             UseBodyExamples = Some true
                             UseQueryExamples = Some true
                             DataFuzzing = true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "exampleTests", "body_param.json"))]
                         }

            let exampleConfigFile = {
                filePath = Path.Combine(Environment.CurrentDirectory, "swagger", "exampleTests", "body_param_example.json")
                exactCopy = true
            }

            let testConfig = { config with ExampleConfigFiles = Some [ exampleConfigFile ] }
            Restler.Workflow.generateRestlerGrammar testConfig

            let expectedGrammarFilePath = Path.Combine(Environment.CurrentDirectory,
                                                        "baselines", "exampleTests", "body_param_exactCopy_grammar.py")
            let actualGrammarFilePath = Path.Combine(grammarOutputDirectoryPath,
                                                     Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
            let grammarDiff = getLineDifferences expectedGrammarFilePath actualGrammarFilePath
            let message = sprintf "Grammar Does not match baseline.  First difference: %A" grammarDiff
            Assert.True(grammarDiff.IsNone, message)

        [<Fact>]
        let ``int64 format example with OpenAPI3 regression test`` () =
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                             ResolveBodyDependencies = true
                             UseBodyExamples = Some false
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger", "exampleTests", "example_int_openapi3.yml"))]
                             CustomDictionaryFilePath = None
                         }
            Restler.Workflow.generateRestlerGrammar config
            let grammarFilePath = Path.Combine(ctx.testRootDirPath, "grammar.py")
            let grammar = File.ReadAllText(grammarFilePath)

            // The grammar should contain the example integer without quotes
            Assert.True(grammar.Contains("examples=[\"1010101\"]"))

            // Test that objects are still correctly generated
            Assert.True(grammar.Contains("{\\\"cloudy_test_scenario\\\":{\\\"label\\\":\\\"cloudy\\\",\\\"duration\\\":60,"))
            Assert.True(grammar.Contains("\\\"is_negative\\\":true}}"))

        ///// Test that the grammar is correct when the entire body is replaced by an example payload.
        ///// Both 'exactCopy' settings should be tested.
        //[<Fact>]
        //let ``replace entire body with example`` () =
        //    let grammarOutputDirectoryPath = ctx.testRootDirPath

        //    let customDictionaryText = "{ \"restler_custom_payload\":\
        //                                        { \"/subnets/{subnetName}/get/__body__\": [\"abc\"] } }\
        //                               "
        //    // TODO: passing in the dictionary directly via 'SwaggerSpecConfig' is not working.
        //    // Write out the dictionary until the but is fixed
        //    //
        //    let dictionaryFilePath =
        //        Path.Combine(grammarOutputDirectoryPath,
        //                     "input_dict.json")
        //    File.WriteAllText(dictionaryFilePath, customDictionaryText)

        //    let config = { Restler.Config.SampleConfig with
        //                     IncludeOptionalParameters = true
        //                     GrammarOutputDirectoryPath = Some grammarOutputDirectoryPath
        //                     ResolveBodyDependencies = true
        //                     UseBodyExamples = Some true
        //                     SwaggerSpecFilePath = Some [Path.Combine(Environment.CurrentDirectory, @"swagger\dependencyTests\subnet_id.json")]
        //                     AllowGetProducers = true
        //                     CustomDictionaryFilePath = Some dictionaryFilePath
        //                 }

        //    Restler.Workflow.generateRestlerGrammar config

        //    let grammarFilePath = Path.Combine(grammarOutputDirectoryPath,
        //                                       Restler.Workflow.Constants.DefaultRestlerGrammarFileName)
        //    let grammar = File.ReadAllText(grammarFilePath)

        //    Assert.True(grammar.Contains("""restler_custom_payload("/subnets/{subnetName}/get/__body__", quoted=False)"""))


        interface IClassFixture<Fixtures.TestSetupAndCleanup>
