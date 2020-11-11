// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

namespace Restler.Test
open System
open System.IO
open Xunit
open Restler.Test.Utilities

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
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\example_demo1.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, @"swagger\example_demo_dictionary.json"))
                         }
            Restler.Workflow.generateRestlerGrammar None config
            let grammarFilePath = Path.Combine(ctx.testRootDirPath, "grammar.py")
            let grammar = File.ReadAllText(grammarFilePath)

            // The grammar should not contain the fruit codes from the example
            Assert.False(grammar.Contains("999"))

            // The grammar should not contain the store codes from the example
            Assert.False(grammar.Contains("23456"))

            Assert.True(grammar.Contains("restler_fuzzable_datetime"))
            Assert.True(grammar.Contains("restler_fuzzable_object"))

        [<Fact>]
        let ``array example in grammar without dependencies`` () =

            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                             ResolveBodyDependencies = false
                             UseBodyExamples = Some true
                             UseQueryExamples = Some true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\array_example.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, @"swagger\example_demo_dictionary.json"))
                         }
            Restler.Workflow.generateRestlerGrammar None config

        [<Fact>]
        let ``object example in grammar without dependencies`` () =

            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                             ResolveBodyDependencies = false
                             UseBodyExamples = Some true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\object_example.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, @"swagger\example_demo_dictionary.json"))
                         }
            Restler.Workflow.generateRestlerGrammar None config

        [<Fact>]
        let ``allof property omitted in example`` () =

            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                             ResolveBodyDependencies = false
                             UseBodyExamples = Some true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\secgroup_example.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, @"swagger\dict_secgroup_example.json"))
                         }
            Restler.Workflow.generateRestlerGrammar None config

        [<Fact>]
        let ``empty array example in grammar without dependencies`` () =

            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                             ResolveBodyDependencies = false
                             UseBodyExamples = Some true
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\empty_array_example.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, @"swagger\example_demo_dictionary.json"))
                         }
            Restler.Workflow.generateRestlerGrammar None config

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
                                                                           sprintf @"swagger\example_demo1%s" extension))]
                                 CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, @"swagger\example_demo_dictionary.json"))
                             }
                Restler.Workflow.generateRestlerGrammar None config
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
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\example_demo1.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, @"swagger\example_demo_dictionary.json"))
                         }
            Restler.Workflow.generateRestlerGrammar None config
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
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\example_demo.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, @"swagger\example_demo_dictionary.json"))
                         }
            Restler.Workflow.generateRestlerGrammar None config
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
            let config = { Restler.Config.SampleConfig with
                            IncludeOptionalParameters = true
                            GrammarOutputDirectoryPath = Some ctx.testRootDirPath
                            ResolveBodyDependencies = true
                            ResolveQueryDependencies = true
                            UseBodyExamples = Some true
                            SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\dependencyTests\subnet_id.json"))]
                            CustomDictionaryFilePath = None
                         }
            Restler.Workflow.generateRestlerGrammar None config
            let grammarFilePath = Path.Combine(ctx.testRootDirPath, "grammar.py")
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
                            SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\dependencyTests\nested_objects_naming.json"))]
                            CustomDictionaryFilePath = None
                         }
            Restler.Workflow.generateRestlerGrammar None config
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
                            SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\dependencyTests\frontend_port_id.json"))]
                            CustomDictionaryFilePath = None
                         }
            Restler.Workflow.generateRestlerGrammar None config
            let grammarFilePath = Path.Combine(grammarOutputDirectoryPath, "grammar.py")
            let grammar = File.ReadAllText(grammarFilePath)

            // Make sure the grammar contains expected partial resource IDs (from the example)
            Assert.True(grammar.Contains("primitives.restler_static_string(\"/frontendPorts/\")"))
            Assert.True(grammar.Contains("primitives.restler_static_string(\"/frontendIPConfigurations/\")"))
            Assert.True(grammar.Contains("primitives.restler_custom_payload_uuid4_suffix(\"frontendPorts_name\")"))
            Assert.True(grammar.Contains("primitives.restler_custom_payload_uuid4_suffix(\"frontendIPConfigurations_name\")"))
            Assert.False(grammar.Contains("primitives.restler_custom_payload_uuid4_suffix(\"frontendPort_name\")"))
            Assert.False(grammar.Contains("primitives.restler_custom_payload_uuid4_suffix(\"frontendIPConfiguration_name\")"))

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
            let dictionary = Microsoft.FSharpLu.Json.Compact.tryDeserializeFile<Restler.Dictionary.MutationsDictionary> dictionaryFilePath
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
                            SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\DependencyTests\ip_configurations_get.json"))]
                            CustomDictionaryFilePath = None
                         }
            Restler.Workflow.generateRestlerGrammar None config
            let grammarFilePath = Path.Combine(ctx.testRootDirPath, "grammar.py")
            let grammar = File.ReadAllText(grammarFilePath)

            Assert.True(grammar.Contains("_networkInterfaces__networkInterfaceName__put_properties_ipConfigurations_0_name.reader()"))

        interface IClassFixture<Fixtures.TestSetupAndCleanup>
