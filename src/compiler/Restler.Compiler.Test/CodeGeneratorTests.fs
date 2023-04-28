// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

namespace Restler.Test

open System.IO
open Xunit
open System
open Restler.Grammar
open Restler.CodeGenerator.Python.Types
open Tree
open SwaggerSpecs
open Restler.Config
open Restler.Utilities.Operators
open Restler.Test.Utilities

[<Trait("TestCategory", "CodeGenerator")>]
module CodeGenerator =
    type CodeGeneratorTests(ctx:Fixtures.TestSetupAndCleanup, output:Xunit.Abstractions.ITestOutputHelper) =

        [<Fact>]
        /// Test that after a grammar is produced (e.g. from a Swagger spec), the json grammar
        /// can be modified manually to re-generate the Python grammar.
        /// This is useful because the grammar json is validated
        /// when deserialized by the RESTler compiler, avoiding typos made directly in python.
        /// This also sanity checks that the grammar generation is deterministic.
        let ``generate code from modified grammar`` () =

            let grammarOutputDirectory1 = ctx.testRootDirPath
            Restler.Workflow.generateRestlerGrammar 
                                    { configs.["demo_server"] with
                                       GrammarOutputDirectoryPath = Some grammarOutputDirectory1 }
            let grammar1 = Restler.Utilities.JsonSerialization.deserializeFile<GrammarDefinition>
                                (Path.Combine(grammarOutputDirectory1, Restler.Workflow.Constants.DefaultJsonGrammarFileName))
            let pythonGrammar1 = File.ReadAllText (Path.Combine(grammarOutputDirectory1, Restler.Workflow.Constants.DefaultRestlerGrammarFileName))

            use sw = new System.IO.StringWriter()

            Restler.CodeGenerator.Python.generateCode
                grammar1 configs.["demo_server"].IncludeOptionalParameters sw.Write

            Assert.True((pythonGrammar1 = sw.GetStringBuilder().ToString()), "grammars are not equal")


        [<Fact>]
        let ``python grammar request sanity test`` () =
            let q1 = LeafNode { LeafProperty.name = "page"; payload = Constant (Int, "1") ;isRequired = true ; isReadOnly = false }
            let q2 = LeafNode { LeafProperty.name = "page"; payload = Constant (Int, "1") ;isRequired = true ; isReadOnly = false }
            let b1 = LeafNode { LeafProperty.name = "payload"; payload = Constant (PrimitiveType.String, "hello") ;
                                    isRequired = true ; isReadOnly = false}
            let pathPayload =
                [ (Constant (PrimitiveType.String, "api"))
                  (Constant (PrimitiveType.String, "accounts"))
                  (DynamicObject { primitiveType = PrimitiveType.Int ; variableName = "accountId"; isWriter = false }) ]
            let requestElements =
                [
                    Method OperationMethod.Get
                    Path pathPayload
                    QueryParameters (ParameterPayloadSource.Schema,
                                     ParameterList [{ name = "page" ; payload = q1 ; serialization = None }
                                                    { name = "payload"; payload = q2; serialization = None} ])
                    Body (ParameterPayloadSource.Schema,(ParameterList  [{ name = "theBody" ; payload = b1 ; serialization = None}]))
                    RequestElement.HttpVersion "1.1"
                    HeaderParameters (ParameterPayloadSource.Schema,ParameterList [])
                    Headers [("Accept", "application/json")
                             ("Host", "fromSwagger")
                             ("Content-Type", "application/json")]
                    Token ("SpringfieldToken: 12345")
                ]
            let request:Request =
                {
                    id = { endpoint = "/api/accounts/{accountId}" ; method = OperationMethod.Put ; xMsPath = None }

                    method = OperationMethod.Get
                    path = pathPayload
                    basePath = ""
                    queryParameters = [(ParameterPayloadSource.Examples, ParameterList [{ name = "page"; payload = q1; serialization = None}
                                                                                        { name = "payload"; payload = q2; serialization = None}])]
                    bodyParameters =  [ParameterPayloadSource.Examples, (ParameterList [{ name = "thebody"; payload = b1; serialization = None}]) ]
                    headerParameters =  [ParameterPayloadSource.Schema, (ParameterList []) ]
                    httpVersion = "1.1"
                    headers = [("Accept", "application/json")
                               ("Host", "fromSwagger")
                               ("Content-Type", "application/json")]
                    token = (TokenKind.Static "SpringfieldToken: 12345")
                    dependencyData = None
                    requestMetadata = { isLongRunningOperation = false }
                }
            let elements = Restler.CodeGenerator.Python.getRequests [request] true

            Assert.True(elements |> Seq.length > 0)

        [<Fact>]
        let ``python grammar parameter sanity test`` () =
            let p1 = { LeafProperty.name = "region"; payload = Constant (PrimitiveType.String, "WestUS");
                        isRequired = true ; isReadOnly = false}
            let p2 = { LeafProperty.name = "maxResources"; payload = Constant (Int, "10") ;
                        isRequired = true ; isReadOnly = false}
            let r = { InnerProperty.name = "subscription"; payload = None
                      propertyType = Object;
                      isRequired = true ; isReadOnly = false}

            let l1 = LeafNode p1
            let l2 = LeafNode p2
            let par = InternalNode (r, [l1 ; l2])

            let result = Restler.CodeGenerator.Python.generatePythonParameter true ParameterPayloadSource.Schema ParameterKind.Body { name = "theBody"; payload = par; serialization = None }

            let hasRegion = result |> Seq.tryFind (fun s -> s = (Restler_static_string_constant "\"region\":"))
            Assert.True(hasRegion.IsSome, "region not found")

            let hasSub = result |> Seq.tryFind (fun s -> s = (Restler_static_string_constant "\"subscription\":"))
            Assert.True(hasSub.IsSome, "subscription not found")

            let hasResources = result |> Seq.tryFind (fun s -> s = (Restler_static_string_constant "\"maxResources\":"))
            Assert.True(hasResources.IsSome, "resources not found")

        // Test that the generated python and json grammars for tracked parameters are correct
        [<Fact>]
        let ``tracked parameters tests`` () =
            let grammarDirectoryPath = ctx.testRootDirPath
            let config = { Restler.Config.SampleConfig with
                             IncludeOptionalParameters = true
                             GrammarOutputDirectoryPath = Some grammarDirectoryPath
                             ResolveBodyDependencies = true
                             UseBodyExamples = Some false
                             SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, "swagger" , "example_demo1.json"))]
                             CustomDictionaryFilePath = Some (Path.Combine(Environment.CurrentDirectory, "swagger", "example_demo_dictionary.json"))
                         }
            Restler.Workflow.generateRestlerGrammar config
            let grammarFilePath = Path.Combine(grammarDirectoryPath, "grammar.py")
            let grammar = File.ReadAllText(grammarFilePath)

            // The grammar should not contain gracked parameters by default
            Assert.False(grammar.Contains("param_name="))

            // Now turn on parameter tracking
            let config = { config with TrackFuzzedParameterNames = true }
            Restler.Workflow.generateRestlerGrammar config
            let grammarFilePath = Path.Combine(grammarDirectoryPath, "grammar.py")
            let grammar = File.ReadAllText(grammarFilePath)

            Assert.True(grammar.Contains("param_name=\"storeId\""))
            Assert.True(grammar.Contains("param_name=\"bannedBrands\""))
            Assert.True(grammar.Contains("param_name=\"groceryItemTags\""))

        interface IClassFixture<Fixtures.TestSetupAndCleanup>

