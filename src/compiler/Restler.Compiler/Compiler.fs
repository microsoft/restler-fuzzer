// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/// Generates the fuzzing grammar required for the main RESTler algorithm
/// Note: the grammar should be self-contained, i.e. using it should not require the Swagger
/// definition for further analysis or to generate code.
/// This module should not implement any code generation to the target language (currently python); code
/// generation logic should go into separate modules and take the grammar as a parameter.
module Restler.Compiler.Main

open System
open System.Collections.Generic
open System.Linq
open NSwag
open Restler.Grammar
open Restler.ApiResourceTypes
open Restler.DependencyAnalysisTypes
open Restler.Examples
open Restler.Dictionary
open Restler.Compiler.SwaggerVisitors
open Restler.Utilities.Logging
open Restler.Utilities.Operators
open Restler.XMsPaths

type UnsupportedParameterSerialization (msg:string) =
    inherit Exception(msg)

module Types =
    /// A configuration associated with a single Swagger document
    type ApiSpecFuzzingConfig =
        {
            swaggerDoc : OpenApiDocument

            dictionary: MutationsDictionary option

            globalAnnotations: ProducerConsumerAnnotation list option

            xMsPathsMapping : Map<string, string> option
        }

let validResponseCodes = [200 .. 206] |> List.map string

let readerMethods = [ OperationMethod.Get ; OperationMethod.Trace
                      OperationMethod.Head ; OperationMethod.Options ]

/// Configuration allowed on a per-request basis
type UserSpecifiedRequestConfig =
    {
        // Per-request dictionaries are only allowed to contain values in the custom payload section.
        dictionary: MutationsDictionary option
        annotations: ProducerConsumerAnnotation option
    }

let getWriterVariable (producer:Producer) (kind:DynamicObjectVariableKind) =
    match producer with
    | InputParameter (iop, _, _) ->
        {
            requestId = iop.id.RequestId
            accessPathParts = iop.getInputParameterAccessPath()
            primitiveType = iop.id.PrimitiveType
            kind = kind
        }
    | ResponseObject rp ->
        let accessPathParts =
            match rp.id.ResourceReference with
            | HeaderResource hr ->
                    { Restler.AccessPaths.AccessPath.path =
                        [|
                            hr
                            "header" // handle ambiguity with body
                        |] }
            | _ ->
                rp.id.AccessPathParts
        {
            requestId = rp.id.RequestId
            accessPathParts = accessPathParts
            primitiveType = rp.id.PrimitiveType
            kind = kind
        }
    | _ ->
        raise (invalidArg "producer" "only input parameter and response producers have an associated dynamic object")

let getResponseParsers (dependencies:seq<ProducerConsumerDependency>) (orderingConstraints:(RequestId * RequestId) list) =
    // Index the dependencies by request ID.
    let parsers = new Dictionary<RequestId, RequestDependencyData>()

   // Generate the parser for all the consumer variables (Note this means we need both producer
   // and consumer pairs.  A response parser is only generated if there is a consumer for one or more of the
   // response properties.)

    /// Make sure the grammar will be stable by sorting the variables.
    let getVariables variableMap variableKind =
        match variableMap |> Map.tryFind variableKind with
        | None -> []
        | Some x ->
            x |> Seq.toList
              |> List.sortBy (fun (writerVariable:DynamicObjectWriterVariable) ->
                                writerVariable.requestId.endpoint,
                                writerVariable.requestId.method,
                                writerVariable.accessPathParts.getJsonPointer().Value)

    let getOrderingConstraintVariables constraints =
        constraints
        |> List.distinct
        |> List.map (fun (source, target) ->
                        { OrderingConstraintVariable.sourceRequestId = source
                          targetRequestId = target })

    // First, add all of the requests for which an ordering constraint exists
    orderingConstraints
    |> Seq.fold (fun reqs (source,target) -> [source ; target] @ reqs) []
    |> Seq.distinct
    |> Seq.iter (fun requestId ->
                    let dependencyInfo =
                        {
                            responseParser = None
                            inputWriterVariables = []

                            orderingConstraintWriterVariables =
                                orderingConstraints |> List.filter (fun (source,_) -> requestId = source)
                                                    |> getOrderingConstraintVariables
                            orderingConstraintReaderVariables =
                                orderingConstraints |> List.filter (fun (_,target) -> requestId = target)
                                                    |> getOrderingConstraintVariables
                        }
                    parsers.Add(requestId, dependencyInfo))

    dependencies
    |> Seq.filter (fun dep -> dep.producer.IsSome)
    |> Seq.choose (fun dep ->
                    let writerVariableKind =
                        match dep.producer.Value with
                        | ResponseObject ro ->
                            match ro.id.ResourceReference with
                            | HeaderResource _ -> Some DynamicObjectVariableKind.Header
                            | _ -> Some DynamicObjectVariableKind.BodyResponseProperty
                        | InputParameter (_, _,_) ->
                            Some DynamicObjectVariableKind.InputParameter
                        | _ -> None
                    match writerVariableKind with
                    | Some v ->
                        getWriterVariable dep.producer.Value v
                        |> Some
                    | None -> None)
    // Remove duplicates
    // Producer may be linked to multiple consumers in separate dependency pairs
    |> Seq.distinct
    |> Seq.groupBy (fun writerVariable -> writerVariable.requestId)
    |> Map.ofSeq
    |> Map.iter (fun requestId allWriterVariables ->
                    let prevDependencyInfo =
                        match parsers.TryGetValue(requestId) with
                        | false, _ -> None
                        | true, di -> Some di

                    let groupedWriterVariables = allWriterVariables |> Seq.groupBy (fun x -> x.kind)
                                                 |> Map.ofSeq

                    let responseParser =
                        {
                            writerVariables = getVariables groupedWriterVariables DynamicObjectVariableKind.BodyResponseProperty
                            headerWriterVariables = getVariables groupedWriterVariables DynamicObjectVariableKind.Header
                        }
                    let dependencyInfo =
                        {
                            responseParser = Some responseParser
                            inputWriterVariables = getVariables groupedWriterVariables DynamicObjectVariableKind.InputParameter
                            orderingConstraintWriterVariables =
                                match prevDependencyInfo with
                                | Some d -> d.orderingConstraintWriterVariables
                                | None -> []
                            orderingConstraintReaderVariables =
                                match prevDependencyInfo with
                                | Some d -> d.orderingConstraintReaderVariables
                                | None -> []
                        }

                    if prevDependencyInfo.IsSome then
                        parsers.Remove(requestId) |> ignore

                    parsers.Add(requestId, dependencyInfo))
    parsers
    |> Seq.map (fun k -> (k.Key,k.Value))
    |> Map.ofSeq

module ResourceUriInferenceFromExample =
    let tryGetExamplePayload payload =
        match payload with
        | FuzzingPayload.Constant (PrimitiveType.String, c) -> Some (c.Trim())
        // TODO: when this supports fuzzable strings as a constant, add
        // FuzzingPayload.Fuzzable x -> Some x
        | _ -> None

    /// Note: this method is not currently used.  It is left here in case the URI format of resources
    /// turns out to be inconsistent and cannot be inferred via the general mechanism below.
    (* Usage:
    | Some exValue when exValue.StartsWith("/") && Uri.IsWellFormedUriString(exValue, UriKind.Relative) ->
        match tryGetUriIdPayloadFromExampleValue requestId exValue endpointPayload with
        | None -> defaultPayload
        | Some p -> p
    *)
    let tryGetUriIdPayloadFromExampleValue (requestId:RequestId) (exValue:string) endpointPayload =
        let consumerEndpointParts = requestId.endpoint.Split([|"/"|], StringSplitOptions.None) |> Array.toList
        let exampleParts = exValue.Split('/') |> Array.toList
        // Check that the id value (example parts) is a child of this (consumer) endpoint
        let rec isChild (parentPathParts:string list) (childPathParts:string list) =
            match parentPathParts,childPathParts with
            | p::pRest, c::cRest when (p.StartsWith("{") || p = c) ->
                // Found path parameter. Skip it.
                // or
                // Found matching part.  Move to next element.
                isChild pRest cRest
            | [], c -> (true, Some c)
            | _ -> false, None
        let isChild, cParts = isChild consumerEndpointParts exampleParts
        if isChild then
            // Re-assemble the remaining child path
            let childPayload = FuzzingPayload.Constant
                                 (PrimitiveType.String, sprintf "/%s" (cParts.Value |> String.concat "/"))
            // Add the endpoint (path) payload, with resolved dependencies
            let pp = endpointPayload
                      |> List.map (fun x -> [ FuzzingPayload.Constant (PrimitiveType.String, "/")
                                              x  ]
                                             )
                      |> List.concat
            Some (FuzzingPayload.PayloadParts (pp @ [childPayload]))
        else
            printfn "WARNING: found external resource id, this needs to be pre-provisioned: %s" exValue
            None

module private Parameters =
    open Newtonsoft.Json.Linq
    open System.Linq
    open Tree

    let getParameterSerialization (p:OpenApiParameter) =
         match p.Style with
         | OpenApiParameterStyle.Form ->
            Some { style = StyleKind.Form ; explode = p.Explode }
         | OpenApiParameterStyle.Simple ->
            Some { style = StyleKind.Simple ; explode = p.Explode }
         | OpenApiParameterStyle.Undefined ->
            None
         | _ ->
            raise (UnsupportedParameterSerialization(sprintf "%A" p.Style))

    /// Determine whether a parameter is declared as 'readOnly'
    /// 'isReadOnly' is not exposed in NJsonSchema.  Instead, it appears
    /// in ExtensionData
    let parameterIsReadOnly (parameter:OpenApiParameter) =
        match SchemaUtilities.getExtensionDataBooleanPropertyValue parameter.ExtensionData "readOnly" with
        | None -> false
        | Some v -> v

    let getPathParameterPayload (payload:ParameterPayload) =
        match payload with
        | LeafNode ln ->
            ln.payload
        | _ -> raise (UnsupportedType "Complex path parameters are not supported")

    /// Given an example payload, go through the list of declared parameters and only retain the
    /// ones that are declared in the example.
    /// At the end, print some diagnostic information about which parameters in the example were
    /// not found in the specification.
    let private getParametersFromExample (examplePayload:ExampleRequestPayload)
                                         (parameterList:seq<OpenApiParameter>)
                                         (trackParameters:bool) =
        // If the declared parameter is the body, then also look for the special keyword denoting
        // a body parameter in examples
        let bodyName = "__body__"

        let exampleParametersFromSpec =
            parameterList
            |> Seq.choose
                (fun declaredParameter ->
                        // If the declared parameter isn't in the example, skip it.  Here, the example is used to
                        // select which parameters must be passed to the API.
                        let foundParameter =
                            match examplePayload.parameterExamples
                                    |> List.tryFind (fun r -> r.parameterName = declaredParameter.Name) with
                            | Some p -> Some p
                            | None when declaredParameter.Kind = OpenApiParameterKind.Body ->
                                examplePayload.parameterExamples
                                |> List.tryFind (fun r -> r.parameterName = bodyName)
                            | None -> None

                        match foundParameter with
                        | None -> None
                        | Some found ->
                            match found.payload with
                            | PayloadFormat.JToken payloadValue ->
                                if examplePayload.exactCopy then
                                    let payload =
                                        let primitiveType =
                                            // If the example is for the body, it should
                                            // be treated as an object.  This covers cases when
                                            // the example is for a content type other than json, so it
                                            // needs to be provided as a string in the example file.
                                            if declaredParameter.Kind = OpenApiParameterKind.Body then
                                                PrimitiveType.Object
                                            else
                                                match payloadValue.Type with
                                                | JTokenType.Array
                                                | JTokenType.Object ->
                                                    PrimitiveType.Object
                                                | _ ->
                                                    PrimitiveType.String
                                        let formattedPayloadValue = GenerateGrammarElements.formatJTokenProperty primitiveType payloadValue
                                        Constant (primitiveType, formattedPayloadValue)

                                    Some { name = declaredParameter.Name
                                           payload = LeafNode { LeafProperty.name = ""
                                                                payload = payload
                                                                isReadOnly = (parameterIsReadOnly declaredParameter)
                                                                isRequired = declaredParameter.IsRequired }
                                           serialization = None }
                                else
                                    let parameterGrammarElement =
                                        generateGrammarElementForSchema declaredParameter.ActualSchema
                                                                        (Some payloadValue, true)
                                                                        (trackParameters, None)
                                                                        (declaredParameter.IsRequired, (parameterIsReadOnly declaredParameter))
                                                                        []
                                                                        (SchemaCache())
                                                                        id
                                    Some { name = declaredParameter.Name
                                           payload = parameterGrammarElement
                                           serialization = getParameterSerialization declaredParameter }
                )
            |> Seq.toList

        exampleParametersFromSpec

    // Gets the first example found from the open API parameter:
    // The priority is:
    // - first, check the 'Example' property
    // - then, check the 'Examples' property
    // - then, check the schema for the 'Example' or 'Examples' property
    // TODO: support getting multiple examples, so RESTler can use all available examples
    let getExamplesFromParameter (p:OpenApiParameter) =
        let getSchemaExample() =
            if isNull p.Schema then None
            else
                SchemaUtilities.tryGetSchemaExampleAsJToken p.Schema

        let getParameterExample() =
            // Get the example from p.Example
            match SchemaUtilities.tryGetSchemaExampleAsJToken (p :> NJsonSchema.JsonSchema) with
            | Some ext -> Some ext
            | None when not (isNull p.Examples) ->
                // Get the value from p.Examples
                if p.Examples.Count > 0 then
                    let firstExample = p.Examples.First()
                    let v = firstExample.Value.Value.ToString()
                    v |> SchemaUtilities.formatExampleValue |> SchemaUtilities.tryParseJToken
                else
                    None
            | _ -> None

        match getParameterExample() with
        | Some parameterExample ->
            Some parameterExample
        | None ->
            getSchemaExample()

    let getSpecParameters (swaggerMethodDefinition:OpenApiOperation)
                          (parameterKind:NSwag.OpenApiParameterKind) =
        let getSharedParameters (parameters:seq<OpenApiParameter>) parameterKind =
            if isNull parameters then Seq.empty
            else
                parameters
                |> Seq.filter (fun p -> p.Kind = parameterKind)

        let localParameters = swaggerMethodDefinition.ActualParameters
                              |> Seq.filter (fun p -> p.Kind = parameterKind)
        // add shared parameters for the endpoint, if any
        let declaredSharedParameters =
            getSharedParameters swaggerMethodDefinition.Parent.Parameters parameterKind

        // For path parameters, add global parameters in case the path parameters are declared there.
        // This is a workaround for specs that do not declare path parameters explicitly.
        let declaredGlobalParameters =
            if parameterKind <> OpenApiParameterKind.Path then
                Seq.empty
            else if isNull swaggerMethodDefinition.Parent.Parent ||
                    isNull swaggerMethodDefinition.Parent.Parent.Parameters then
                Seq.empty
            else
                let globalParameterCollection =
                    swaggerMethodDefinition.Parent.Parent.Parameters
                    |> Seq.map (fun kvp -> kvp.Value)
                    |> Seq.filter (fun kvp -> kvp.IsRequired)
                getSharedParameters globalParameterCollection parameterKind

        let allParameters =
            [ localParameters
              // In some cases, 'ActualParameters' above contains all parameters already.
              // The additional filter below removes this duplication.
              declaredSharedParameters
              declaredGlobalParameters
            ]
            |> Seq.concat
            |> Seq.distinctBy (fun dp -> dp.Name)
        allParameters

    let pathParameters (swaggerMethodDefinition:OpenApiOperation) (endpoint:string)
                       (exampleConfig: ExampleRequestPayload list option)
                       (trackParameters:bool)
                       (jsonPropertyMaxDepth:int option) =
        let allDeclaredPathParameters = getSpecParameters swaggerMethodDefinition OpenApiParameterKind.Path
        let path = Paths.getPathFromString endpoint false
        let parameterList =
            allDeclaredPathParameters
            |> Seq.filter (fun p -> path.containsParameter p.Name)
            // By default, all path parameters are fuzzable (unless a producer or custom value is found for them later)
            |> Seq.choose (fun parameter ->
                                let serialization = getParameterSerialization parameter
                                let schema = parameter.ActualSchema
                                // Check for path examples in the Swagger specification
                                // External path examples are not currently supported
                                let parameterValueFromExample =
                                    match exampleConfig with
                                    | None
                                    | Some [] ->
                                        None
                                    | Some (firstExample::remainingExamples) ->
                                        // Use the first example specified to determine the parameter value.
                                        getParametersFromExample firstExample (parameter |> stn) trackParameters
                                        |> Seq.tryHead

                                if parameterValueFromExample.IsSome then
                                    parameterValueFromExample
                                else
                                    let leafProperty =
                                        if schema.IsArray then
                                            raise (Exception("Arrays in path examples are not supported yet."))
                                        else
                                            let specExampleValue = getExamplesFromParameter parameter
                                            let propertyPayload =
                                                generateGrammarElementForSchema
                                                        schema
                                                        (specExampleValue, true)
                                                        (trackParameters, jsonPropertyMaxDepth)
                                                        (true (*isRequired*), false (*isReadOnly*))
                                                        []
                                                        (SchemaCache())
                                                        id
                                            match propertyPayload with
                                            | LeafNode leafProperty ->
                                                let leafNodePayload =

                                                    match leafProperty.payload with
                                                    | Fuzzable fp ->
                                                        match fp.primitiveType with
                                                        | Enum(propertyName, propertyType, values, defaultValue) ->
                                                            let primitiveType = PrimitiveType.Enum(parameter.Name, propertyType, values, defaultValue)
                                                            Fuzzable { fp with primitiveType = primitiveType }
                                                        | _ ->
                                                            Fuzzable {fp with
                                                                        parameterName = if trackParameters then Some parameter.Name else None }
                                                    | _ -> leafProperty.payload
                                                { leafProperty with payload = leafNodePayload }
                                            | InternalNode (internalNode, children) ->
                                                // The parameter payload is not expected to be nested
                                                failwith "Path parameters with nested object types are not supported"

                                    Some { name = parameter.Name
                                           payload = LeafNode leafProperty
                                           serialization = serialization }
                )
        ParameterList parameterList

    let private getParameters (parameterList:seq<OpenApiParameter>)
                              (exampleConfig:ExampleRequestPayload list option)
                              (dataFuzzing:bool)
                              (trackParameters:bool)
                              (jsonPropertyMaxDepth:int option) =

        // When data fuzzing is specified, both the full schema and examples should be available for analysis.
        // Otherwise, use the first example if it exists, or the schema, and return a single schema.
        let examplePayloads =
            match exampleConfig with
            | None -> None
            | Some [] -> None
            | Some (firstExample::remainingExamples) ->
                // Use the first example specified to determine the parameter schema and values.
                let firstPayload = getParametersFromExample firstExample parameterList trackParameters
                let restOfPayloads =
                    remainingExamples |> List.map (fun e -> getParametersFromExample e parameterList trackParameters)
                Some (firstPayload::restOfPayloads)

        let schemaPayload =
            if dataFuzzing || examplePayloads.IsNone then
                Some (parameterList
                      |> Seq.map (fun p ->
                                    let specExampleValue =
                                         getExamplesFromParameter p

                                    let parameterPayload = generateGrammarElementForSchema
                                                                p.ActualSchema
                                                                (specExampleValue, true)
                                                                (trackParameters, jsonPropertyMaxDepth)
                                                                (p.IsRequired, (parameterIsReadOnly p))
                                                                []
                                                                (SchemaCache())
                                                                id

                                    // Add the name to the parameter payload
                                    let parameterPayload =
                                        match parameterPayload with
                                        | LeafNode leafProperty ->
                                            let leafNodePayload =

                                                match leafProperty.payload with
                                                | Fuzzable fp ->
                                                    match fp.primitiveType with
                                                    | Enum(propertyName, propertyType, values, defaultValue) ->
                                                        let primitiveType = PrimitiveType.Enum(p.Name, propertyType, values, defaultValue)
                                                        Fuzzable { fp with primitiveType = primitiveType }
                                                    | _ ->
                                                        Fuzzable {fp with
                                                                    parameterName = if trackParameters then Some p.Name else None }
                                                | _ -> leafProperty.payload
                                            LeafNode { leafProperty with payload = leafNodePayload }
                                        | InternalNode (internalNode, children) ->
                                            // TODO: need enum test to see if body enum is fine.
                                            parameterPayload
                                    {
                                        name = p.Name
                                        payload = parameterPayload
                                        serialization = getParameterSerialization p
                                    }))
            else None

        match examplePayloads, schemaPayload with
        | Some epv, Some spv ->
            let examplePayloadsList = epv |> List.map (fun x -> ParameterPayloadSource.Examples, (ParameterList x))
            let schemaPayloadValue = ParameterPayloadSource.Schema, ParameterList spv
            examplePayloadsList @ [schemaPayloadValue]
        | Some epv, None ->
            // All example payloads are included in the grammar, and dependency analysis will be performed
            // separately on all of them.  TODO: for performance reasons, we may want to improve this later by first
            // checking if the producer-consumer dependency already exists (see Dependencies.fs).
            epv |> List.map (fun x -> ParameterPayloadSource.Examples, (ParameterList x))
        | None, Some spv ->
            let schemaPayloadValue = ParameterPayloadSource.Schema, ParameterList spv
            [schemaPayloadValue]
        | _ -> raise (invalidOp("invalid combination"))

    let getAllParameters (swaggerMethodDefinition:OpenApiOperation)
                         (parameterKind:NSwag.OpenApiParameterKind)
                         exampleConfig dataFuzzing
                         trackParameters
                         jsonPropertyMaxDepth =
        let allParameters = getSpecParameters swaggerMethodDefinition parameterKind
        getParameters allParameters exampleConfig dataFuzzing trackParameters jsonPropertyMaxDepth

    let getBody (swaggerMethodDefinition:OpenApiOperation)
                exampleConfig dataFuzzing
                trackParameters
                jsonPropertyMaxDepth =
        let bodyName = "__body__"

        let bodyName, bodySchema =
            if not (isNull swaggerMethodDefinition.RequestBody) &&
                not (isNull swaggerMethodDefinition.RequestBody.Content) then
                let content =
                    swaggerMethodDefinition.RequestBody.Content |> Seq.tryFind (fun x -> x.Key = "application/json" || x.Key = "*/*")
                // If the schema is null, issue a warning.
                match content with
                | Some c ->
                    let bodyName =
                        if not (String.IsNullOrEmpty(swaggerMethodDefinition.RequestBody.Name)) then
                            swaggerMethodDefinition.RequestBody.Name
                        else
                            bodyName
                    if isNull c.Value.Schema then
                        printfn "Error: found body (%s) with null schema.  This may be due to an invalid OpenAPI spec." bodyName
                        bodyName, None
                    else
                        bodyName, Some c.Value.Schema.ActualSchema
                | None -> bodyName, None
            else
                let parameter = getSpecParameters swaggerMethodDefinition OpenApiParameterKind.Body |> Seq.tryHead
                match parameter with
                | None -> bodyName, None
                | Some p -> p.Name, Some p.ActualSchema

        if bodySchema.IsSome then
            let openApiParameter = OpenApiParameter()
            openApiParameter.Name <- bodyName
            openApiParameter.Schema <- bodySchema.Value
            openApiParameter.Kind <- OpenApiParameterKind.Body
            openApiParameter.IsRequired <- true
            getParameters (openApiParameter |> stn) exampleConfig dataFuzzing trackParameters jsonPropertyMaxDepth
        else
            // No body
            getParameters Seq.empty exampleConfig dataFuzzing trackParameters jsonPropertyMaxDepth

/// Functionality related to x-ms-paths support.  For more information, see:
/// https://github.com/stankovski/AutoRest/blob/master/Documentation/swagger-extensions.md#x-ms-paths
module private XMsPaths =
    /// For a request with an endpoint in x-ms-path format that was mapped to a different endpoint,
    /// re-construct the path payload in x-ms-path format.
    let replaceWithOriginalPaths (req:Request) =
        let xMsPath = req.id.xMsPath.Value
        let xMsPathEndpoint = xMsPath.getEndpoint()

        // Re-construct the path payload in x-ms-paths format
        let queryPartSplit =
            xMsPath.queryPart.Split([|'='; '&'|], StringSplitOptions.RemoveEmptyEntries)

        let pathPartLength = req.path.Length - (queryPartSplit.Length * 2) // multiply by 2 because 'req.path' contains path delimiters
        let pathPart = req.path |> List.take pathPartLength
        let queryPart = req.path |> List.skip pathPartLength

        let pathParametersInQueryPart =
            queryPartSplit
            |> Array.mapi (fun idx p -> idx * 2 + 1, p) // Adjust for 'req.path' containing path delimiters
            |> Array.filter (fun (idx,part) -> Paths.isPathParameter part)

        let queryParamPayloads =
            pathParametersInQueryPart
            |> Seq.fold (fun (queryPartPayload:(FuzzingPayload * string) list) (paramIndex, paramName) ->
                            let _, remainingQueryPart = queryPartPayload |> List.last

                            let paramIndexInQuery = remainingQueryPart.IndexOf(paramName)
                            let constantPayload = remainingQueryPart.Substring(0, paramIndexInQuery)
                            let paramPayload = queryPart.[paramIndex]
                            let newRemainingQueryPart =
                                remainingQueryPart.Substring(paramIndexInQuery + paramName.Length)

                            [ Constant(PrimitiveType.String, constantPayload), ""
                              paramPayload, newRemainingQueryPart ])
                        [ Constant(PrimitiveType.String, ""), xMsPath.queryPart ]


        let xMsPathQueryPayload =
            [
              [ Constant(PrimitiveType.String, "?") ]
              queryParamPayloads |> List.map fst
              [ Constant (PrimitiveType.String, (queryParamPayloads |> List.last |> snd))]
            ]
            |> Seq.concat
            |> Seq.toList

        { req with
            id = { endpoint = xMsPathEndpoint ; method = req.id.method ; xMsPath = req.id.xMsPath }
            path = pathPart @ xMsPathQueryPayload }

    /// Given a list of all query parameters and an endpoint that contains query parameters,
    /// returns the subset of query parameters excluding the ones that are in the path.
    /// The excluded parameters will be processed as path parameters instead, to handle cases
    /// when the query parameter declared in the x-ms-paths endpoint is a variable
    /// (e.g. /X&op={opName} ).
    let filterXMsPathQueryParameters (allQueryParameters:(ParameterPayloadSource * RequestParametersPayload) list)
                                     (endpointQueryPart:string) =
        // Filter any query parameters that are part of a path
        // declared in x-ms-paths
        // param1=customer&param2={id}
        // Note: some specifications declare 'param1' and 'param2' in query parameters, while others declare 'id'.
        // The code below filters out all of them, so they do not appear twice in the grammar.
        let endpointQueryParameterNames =
            endpointQueryPart.Split("&")
            |> Array.choose (fun x ->
                                 let splitParam = x.Split("=", StringSplitOptions.RemoveEmptyEntries)
                                 match splitParam with
                                 | [|name ; paramValue|] ->
                                    if Paths.isPathParameter paramValue then
                                        Paths.tryGetPathParameterName paramValue
                                    else
                                        Some name
                                 | [|name|] ->
                                    Some name
                                 | _ -> None
                             )

        let queryParametersFiltered =
            allQueryParameters
            |> List.map (fun (payloadSource, requestParameterPayload) ->
                            match requestParameterPayload with
                            | ParameterList pList when payloadSource = ParameterPayloadSource.Schema ->
                                let queryParametersNotInPath =
                                    pList
                                    |> Seq.filter (fun requestParameter ->
                                                        not (endpointQueryParameterNames|> Seq.contains requestParameter.name))
                                (payloadSource, ParameterList queryParametersNotInPath)
                            | ParameterList _ ->
                                (payloadSource, requestParameterPayload)
                            | Example e ->
                                // Example query parameters for x-ms-paths query parameters are not supported.
                                // Output a warning and return the example
                                printfn "Warning: example found with x-ms-paths query parameters."
                                (payloadSource, requestParameterPayload))
        queryParametersFiltered


/// Given a list of the parameters found in the spec and the dictionary,
/// determines which additional injected parameters are specified in the dictionary
/// and creates the corresponding payloads.
let private getInjectedCustomPayloadParameters (dictionary:MutationsDictionary) customPayloadType parametersFoundInSpec =
    let parameterNames =
        let parameterNamesSpecifiedAsCustomPayloads =
            match customPayloadType with
            | CustomPayloadType.Header ->
                dictionary.getCustomPayloadHeaderParameterNames()
            | CustomPayloadType.Query ->
                dictionary.getCustomPayloadQueryParameterNames()
            | _ ->
                raise (invalidArg "customPayloadType" (sprintf "%A is not supported in this context." customPayloadType))
        parameterNamesSpecifiedAsCustomPayloads
        |> Seq.filter (fun name -> not (parametersFoundInSpec |> List.contains name))

    parameterNames
        |> Seq.map (fun headerName ->
                        let newParameter =
                            {
                                RequestParameter.name = headerName
                                serialization = None
                                payload =
                                    Tree.LeafNode
                                        {
                                            LeafProperty.name = ""
                                            LeafProperty.payload =
                                                FuzzingPayload.Custom
                                                    {
                                                        payloadType = customPayloadType
                                                        primitiveType = PrimitiveType.String
                                                        payloadValue = headerName
                                                        isObject = false
                                                        dynamicObject = None
                                                    }
                                            LeafProperty.isRequired = true
                                            LeafProperty.isReadOnly = false
                                        }}
                        newParameter)
            |> Seq.toList

let private getContentLengthCustomPayload() =
    let headerName = "Content-Length"
    let newParameter =
        {
            RequestParameter.name = headerName
            serialization = None
            payload =
                Tree.LeafNode
                    {
                        LeafProperty.name = ""
                        LeafProperty.payload =
                            FuzzingPayload.Custom
                                {
                                    payloadType = CustomPayloadType.String
                                    primitiveType = PrimitiveType.String
                                    payloadValue = headerName
                                    isObject = false
                                    dynamicObject = None
                                }
                        LeafProperty.isRequired = true
                        LeafProperty.isReadOnly = false
                    }}
    newParameter


let generateRequestPrimitives (requestId:RequestId)
                               (dependencyData:RequestDependencyData option)
                               (requestParameters:RequestParameters)
                               (dependencies:Dictionary<string, List<ProducerConsumerDependency>>)
                               (basePath:string)
                               (host:string)
                               (resolveQueryDependencies:bool)
                               (resolveBodyDependencies:bool)
                               (resolveHeaderDependencies:bool)
                               (dictionary:MutationsDictionary)
                               (requestMetadata:RequestMetadata) =
    let method = requestId.method

    let pathParameters =
        match requestParameters.path with
        | ParameterList parameterList ->
            parameterList
            |> Seq.map (fun p -> p.name, p)
            |> Map.ofSeq
        | _ -> raise (UnsupportedType "Only a list of path parameters is supported.")
    let queryParameters =
        let queryParameterList =
            match requestParameters.query |> List.tryFind (fun (s, t) -> s = ParameterPayloadSource.Schema) with
            | Some schemaParameters -> schemaParameters
            | None -> requestParameters.query |> List.head
        match queryParameterList |> snd with
        | ParameterList parameterList ->
            parameterList
            |> Seq.map (fun p -> p.name, p)
            |> Map.ofSeq
        | _ -> raise (UnsupportedType "Only a list of query parameters is supported.")

    let path =
        let splitPath = Paths.getPathFromString requestId.endpoint true (*includeSeparators*)
        splitPath.path
        |> List.map (fun p ->
                        match p with
                        | Paths.PathPart.Parameter name ->
                            let declaredParameter =
                                match pathParameters |> Seq.tryFind (fun p -> Paths.parameterNamesEqual p.Key name) with
                                | Some dp -> Some dp.Value
                                | None when requestId.xMsPath.IsSome ->
                                    // This is a query parameter that appears in the path that is in x-ms-path format
                                    // Check the query parameters
                                    match queryParameters |> Seq.tryFind (fun p -> Paths.parameterNamesEqual p.Key name) with
                                    | Some dp -> Some dp.Value
                                    | None -> None
                                | None ->
                                    // Swagger bug: parameter is not declared
                                    // Avoid failing to compile, since other requests may still be fuzzed successfully
                                    None

                            match declaredParameter with
                            | Some rp ->
                                let newRequestParameter, _ =
                                    Restler.Dependencies.DependencyLookup.getDependencyPayload
                                                dependencies
                                                None
                                                requestId
                                                rp
                                                dictionary
                                Parameters.getPathParameterPayload newRequestParameter.payload
                            | None ->
                                // Add the parameter to the grammar in braces, to highlight that there is an issue with the spec
                                Constant (PrimitiveType.String, Paths.formatPathParameter name)
                        | Paths.PathPart.Constant s -> Constant (PrimitiveType.String, s)
                        | Paths.PathPart.Separator -> Constant (PrimitiveType.String, "/")
                        )

    let replaceCustomPayloads customPayloadType customPayloadParameterNames (requestParameter:RequestParameter) =
        if customPayloadParameterNames |> Seq.contains requestParameter.name then
            let isRequired, isReadOnly =
                match requestParameter.payload with
                | Tree.LeafNode lp -> lp.isRequired, lp.isReadOnly
                | Tree.InternalNode (ip,c) -> ip.isRequired, ip.isReadOnly
            let newParameter =
                { requestParameter with
                    payload =
                        Tree.LeafNode
                            {
                                LeafProperty.name = ""
                                LeafProperty.payload =
                                    FuzzingPayload.Custom
                                        {
                                            payloadType = customPayloadType
                                            primitiveType = PrimitiveType.String
                                            payloadValue = requestParameter.name
                                            isObject = false
                                            dynamicObject = None
                                        }
                                LeafProperty.isRequired = isRequired
                                LeafProperty.isReadOnly = isReadOnly
                            }}
            newParameter, true
        else
            requestParameter, false

    // Generate header parameters.
    // Do not compute dependencies for header parameters unless resolveHeaderDependencies (from config) is true.
    let requestHeaderParameters =
        let headersSpecifiedAsCustomPayloads = dictionary.getCustomPayloadHeaderParameterNames()
        match requestParameters.header with
        | [] ->
            // Filter out Content-Type, because this is handled separately below
            let injectedCustomPayloadHeaderParameters = getInjectedCustomPayloadParameters dictionary CustomPayloadType.Header ["Content-Type"]
            [(ParameterPayloadSource.DictionaryCustomPayload, ParameterList (injectedCustomPayloadHeaderParameters |> seq))]
        | _ ->
            requestParameters.header
            |> List.map
                (fun (payloadSource, requestHeaders) ->
                        let parameterList =
                            match requestHeaders with
                            | ParameterList parameterList ->
                                if resolveHeaderDependencies then
                                    parameterList
                                    |> Seq.map (fun p ->
                                                    let newPayload, _ =
                                                        Restler.Dependencies.DependencyLookup.getDependencyPayload
                                                                            dependencies
                                                                            None
                                                                            requestId
                                                                            p
                                                                            dictionary
                                                    newPayload)
                                else parameterList
                            | _ -> raise (UnsupportedType "Only a list of header parameters is supported.")

                        let addContentLengthCustomPayload =
                            let isContentLengthParam name =
                                name = "Content-Length"

                            let specContainsContentLength = parameterList |> Seq.exists (fun p -> isContentLengthParam p.name)
                            let dictionaryContainsContentLength =
                                dictionary.getCustomPayloadNames()
                                |> Seq.exists (fun name -> isContentLengthParam name)
                            specContainsContentLength && dictionaryContainsContentLength

                        let parameterList =
                            parameterList
                            // Filter out the 'Content-Length' parameter if it is specified in the spec.
                            // This parameter must be computed by the engine, and should not be fuzzed.
                            |> Seq.filter (fun rp -> rp.name <> "Content-Length")
                            |> Seq.map (fun requestParameter ->
                                            replaceCustomPayloads CustomPayloadType.Header headersSpecifiedAsCustomPayloads requestParameter
                                            |> fst )

                        let specHeaderParameterNames =
                            parameterList
                            |> Seq.map (fun p -> p.name)
                            |> Seq.toList

                        // Get the additional custom payload header parameters that should be injected
                        let injectedCustomPayloadHeaderParameters = getInjectedCustomPayloadParameters dictionary CustomPayloadType.Header specHeaderParameterNames

                        let allHeaderParameters =
                            [
                                parameterList
                                injectedCustomPayloadHeaderParameters |> seq
                                if addContentLengthCustomPayload then getContentLengthCustomPayload() |> stn else Seq.empty
                            ] |> Seq.concat
                        payloadSource, ParameterList allHeaderParameters)

    // Special case for endpoints in x-ms-paths:
    // handle query parameters present in the path. This must be done after the path payload has been determined above,
    // so payloads for the query parameters declared in the path are correctly assigned.
    let requestQueryParameters =
        match requestId.xMsPath with
        | None -> requestParameters.query
        | Some xMsPath ->
            XMsPaths.filterXMsPathQueryParameters requestParameters.query xMsPath.queryPart

    // Assign dynamic objects to query parameters if they have dependencies.
    // When there is more than one parameter set, the dictionary must be the one for the schema.
    //
    let requestQueryParameters =
        match requestQueryParameters with
        | [] ->
            let injectedCustomPayloadQueryParameters = getInjectedCustomPayloadParameters dictionary CustomPayloadType.Query []
            [(ParameterPayloadSource.DictionaryCustomPayload, ParameterList (injectedCustomPayloadQueryParameters |> seq))]
        | _ ->
            requestQueryParameters
            |> List.map (fun (payloadSource, requestQuery) ->
                            let parameterList =
                                match requestQuery with
                                | ParameterList parameterList ->
                                    if resolveQueryDependencies then
                                        parameterList
                                        |> Seq.map (fun p ->
                                                        let newPayload, _ =
                                                            Restler.Dependencies.DependencyLookup.getDependencyPayload
                                                                                dependencies
                                                                                None
                                                                                requestId
                                                                                p
                                                                                dictionary
                                                        newPayload)
                                    else parameterList
                                | _ -> raise (UnsupportedType "Only a list of query parameters is supported.")

                            let specQueryParameterNames =
                                parameterList
                                |> Seq.map (fun p -> p.name)
                                |> Seq.toList

                            // Get the additional custom payload query parameters that should be injected
                            let injectedCustomPayloadQueryParameters = getInjectedCustomPayloadParameters dictionary CustomPayloadType.Query specQueryParameterNames
                            let allQueryParameters = [ parameterList ; injectedCustomPayloadQueryParameters |> seq ] |> Seq.concat
                            payloadSource, ParameterList allQueryParameters)

    let bodyParameters, newDictionary =
        // Check if the body is being replaced by a custom payload
        let endpoint =
            match requestId.xMsPath with
            | None -> requestId.endpoint
            | Some xMsPath -> xMsPath.getEndpoint()

        match dictionary.findBodyCustomPayload endpoint (requestId.method.ToString()) with
        | Some entry ->
            let bodyPayload =
                FuzzingPayload.Custom
                    {
                        payloadType = CustomPayloadType.String
                        primitiveType = PrimitiveType.String
                        payloadValue = entry
                        isObject = true  // Do not quote the body
                        dynamicObject = None
                    }
            [ ParameterPayloadSource.DictionaryCustomPayload, Example bodyPayload ],
            dictionary
        | None ->
            requestParameters.body
            |> List.mapFold (fun (parameterSetDictionary:MutationsDictionary) (payloadSource, requestBody) ->
                                let result, newParameterSetDict =
                                    match requestBody with
                                    | ParameterList parameterList ->
                                        let newParameterList, newDict =
                                            if resolveBodyDependencies then
                                                parameterList
                                                |> Seq.mapFold
                                                    (fun currentDict p ->
                                                            let result, resultDict =
                                                                Restler.Dependencies.DependencyLookup.getDependencyPayload
                                                                    dependencies
                                                                    (Some path)
                                                                    requestId
                                                                    p
                                                                    currentDict
                                                            // Merge the custom payloads of the dictionaries
                                                            let mergedDict = currentDict.combineCustomPayloadSuffix resultDict
                                                            result, mergedDict
                                                    ) parameterSetDictionary
                                            else parameterList, parameterSetDictionary
                                        (payloadSource, ParameterList newParameterList), newDict
                                    | _ ->
                                        (payloadSource, requestBody), parameterSetDictionary
                                result, newParameterSetDict)
                          dictionary

    let contentTypeHeader =
        let requestHasBody = match (requestParameters.body |> Seq.head |> snd) with
                             | ParameterList p -> p |> Seq.length > 0
                             | Example (FuzzingPayload.Constant (PrimitiveType.String, str)) ->
                                not (String.IsNullOrWhiteSpace str)
                             | _ -> raise (UnsupportedType "unsupported body parameter type")
        if requestHasBody then
            // Check if the custom dictionary overrides the content type for this request body
            // If so, construct a payload
            let ContentTypeHeaderName = "Content-Type"
            // Check if the body is being replaced by a custom payload
            let endpoint =
                match requestId.xMsPath with
                | None -> requestId.endpoint
                | Some xMsPath -> xMsPath.getEndpoint()

            let contentType =
                match dictionary.findRequestTypeCustomPayload endpoint (requestId.method.ToString()) ContentTypeHeaderName with
                | Some x ->
                    let leafNode =
                        Tree.LeafNode
                            {
                                LeafProperty.name = ""
                                LeafProperty.payload =
                                    FuzzingPayload.Custom
                                        {
                                            payloadType = CustomPayloadType.String
                                            primitiveType = PrimitiveType.String
                                            payloadValue = x
                                            isObject = false
                                            dynamicObject = None
                                        }
                                LeafProperty.isRequired = true
                                LeafProperty.isReadOnly = false
                            }
                    {
                        name = ContentTypeHeaderName
                        payload =  leafNode
                        serialization = None
                    }
                | None ->
                    let leafNode =
                        Tree.LeafNode
                            {
                                LeafProperty.name = ""
                                LeafProperty.payload =
                                    FuzzingPayload.Constant (PrimitiveType.String, "application/json")
                                LeafProperty.isRequired = true
                                LeafProperty.isReadOnly = false
                            }
                    {
                        name = ContentTypeHeaderName
                        payload =  leafNode
                        serialization = None
                    }

            [ contentType ]
        else []

    let headers =
        ([ ("Accept", "application/json")
           ("Host", host)])
    {
        id = requestId
        Request.method = method
        Request.basePath = basePath
        Request.path = path
        queryParameters = requestQueryParameters
        headerParameters = requestHeaderParameters @
                                [(ParameterPayloadSource.DictionaryCustomPayload,
                                  RequestParametersPayload.ParameterList contentTypeHeader)]
        httpVersion = "1.1"
        headers = headers
        token = TokenKind.Refreshable
        bodyParameters = bodyParameters
        dependencyData = dependencyData
        requestMetadata = requestMetadata
    },
    newDictionary

/// Generates the requests, dynamic objects, and response parsers required for the main RESTler algorithm
let generateRequestGrammar (swaggerDocs:Types.ApiSpecFuzzingConfig list)
                           (dictionary:MutationsDictionary)
                           (config:Restler.Config.Config)
                           (globalExternalAnnotations: ProducerConsumerAnnotation list)
                           (userSpecifiedExamples:ExampleConfigFile list) =

    let getRequestData (swaggerDoc:OpenApiDocument) (xMsPathsMapping:Map<string,string> option) =
        let schemaCache = SchemaCache()
        let requestDataSeq = seq {
            for path in swaggerDoc.Paths do
                let ep = path.Key.TrimEnd([|'/'|])
                let xMsPath =
                    match xMsPathsMapping with
                    | None -> None
                    | Some m when m |> Map.containsKey ep ->
                        let xMsPath = getXMsPath m.[ep]
                        if xMsPath.IsNone then
                            raise (invalidOp "getXMsPath should have returned a value")
                        xMsPath
                    | Some _ -> None
                for m in path.Value do

                    let requestId = { RequestId.endpoint = ep;
                                      RequestId.method = getOperationMethodFromString m.Key
                                      RequestId.xMsPath = xMsPath }

                    // If there are examples for this endpoint+method, extract the example file using the example options.
                    let exampleConfig =
                        let useBodyExamples =
                            config.UseBodyExamples |> Option.defaultValue false
                        let useQueryExamples =
                            config.UseQueryExamples |> Option.defaultValue false
                        let useHeaderExamples =
                            config.UseHeaderExamples |> Option.defaultValue false
                        let usePathExamples =
                            config.UsePathExamples |> Option.defaultValue false
                        let useExamples =
                            usePathExamples || useBodyExamples || useQueryExamples || useHeaderExamples
                        if useExamples || config.DiscoverExamples then
                            // The original endpoint must be used to find the example
                            let exampleConfigEndpoint =
                                match xMsPath with
                                | None -> ep
                                | Some xMsPath -> xMsPath.getEndpoint()
                            let exampleRequestPayloads = getExampleConfig (exampleConfigEndpoint,m.Key)
                                                                          m.Value
                                                                          config.DiscoverExamples
                                                                          config.ExamplesDirectory
                                                                          userSpecifiedExamples
                                                                          (config.UseAllExamplePayloads |> Option.defaultValue false)
                            // If 'discoverExamples' is specified, create a local copy in the specified examples directory for
                            // all the examples found.
                            if config.DiscoverExamples then
                                exampleRequestPayloads
                                |> List.iteri (fun count reqPayload ->
                                                    if reqPayload.exampleFilePath.IsSome then
                                                        let sourceFilePath = reqPayload.exampleFilePath.Value
                                                        let fileName = System.IO.Path.GetFileNameWithoutExtension(sourceFilePath)
                                                        let ext = System.IO.Path.GetExtension(sourceFilePath)
                                                        // Append a suffix in case there are collisions
                                                        let localExampleFileName =
                                                            sprintf "%s%d%s" fileName count ext
                                                        let targetFilePath = System.IO.Path.Combine(config.ExamplesDirectory, localExampleFileName)
                                                        try
                                                            System.IO.File.Copy(sourceFilePath, targetFilePath)
                                                        with e ->
                                                            printfn "ERROR copying example file (%s) to target directory (%s): %A" sourceFilePath config.ExamplesDirectory e
                                              )
                            Some exampleRequestPayloads
                        else None

                    // If examples are being discovered, output them in the 'Examples' directory
                    if not config.ReadOnlyFuzz || readerMethods |> List.contains requestId.method then
                        let allQueryParameters =
                            let useQueryExamples =
                                config.UseQueryExamples |> Option.defaultValue false

                            Parameters.getAllParameters
                                m.Value
                                OpenApiParameterKind.Query
                                (if useQueryExamples then exampleConfig else None)
                                config.DataFuzzing
                                config.TrackFuzzedParameterNames
                                config.JsonPropertyMaxDepth

                        let pathParameters =
                            let usePathExamples =
                                config.UsePathExamples |> Option.defaultValue false
                            Parameters.pathParameters
                                    m.Value ep
                                    (if usePathExamples then exampleConfig else None)
                                    config.TrackFuzzedParameterNames
                                    config.JsonPropertyMaxDepth
                        let body =
                            let useBodyExamples =
                                config.UseBodyExamples |> Option.defaultValue false
                            Parameters.getBody
                                m.Value
                                (if useBodyExamples then exampleConfig else None)
                                config.DataFuzzing
                                config.TrackFuzzedParameterNames
                                config.JsonPropertyMaxDepth

                        let requestParameters =
                            {
                                RequestParameters.path = pathParameters

                                RequestParameters.header =
                                    let useHeaderExamples =
                                        config.UseHeaderExamples |> Option.defaultValue false
                                    Parameters.getAllParameters
                                        m.Value
                                        OpenApiParameterKind.Header
                                        (if useHeaderExamples then exampleConfig else None)
                                        config.DataFuzzing
                                        config.TrackFuzzedParameterNames
                                        config.JsonPropertyMaxDepth
                                RequestParameters.query = allQueryParameters
                                RequestParameters.body = body
                            }

                        let allResponses = seq {
                            let responses = m.Value.Responses
                                            |> Seq.filter (fun r -> validResponseCodes |> List.contains r.Key)
                                            |> Seq.sortBy (fun r ->
                                                                let hasResponseBody = if isNull r.Value.ActualResponse.Schema then 1 else 0
                                                                let hasResponseHeaders = if r.Value.Headers |> Seq.isEmpty then 1 else 0
                                                                // Prefer the responses that have a response schema defined.
                                                                hasResponseBody, hasResponseHeaders, r.Key)
                            for r in responses do
                                let headerResponseSchema =
                                    r.Value.Headers
                                    |> Seq.map (fun h -> let headerSchema =
                                                             generateGrammarElementForSchema h.Value (None, false)
                                                                                             (false, config.JsonPropertyMaxDepth)
                                                                                             (true (*isRequired*), false (*isReadOnly*)) []
                                                                                             schemaCache
                                                                                             id
                                                         h.Key, headerSchema)
                                    |> Seq.toList

                                let bodyResponseSchema =
                                    if isNull r.Value.ActualResponse.Schema then None
                                    else
                                        generateGrammarElementForSchema r.Value.ActualResponse.Schema (None, false)
                                                                        (false, config.JsonPropertyMaxDepth)
                                                                        (true (*isRequired*), false (*isReadOnly*)) []
                                                                        schemaCache
                                                                        id
                                        |> Some

                                // Convert links in the response to annotations
                                let linkAnnotations =
                                    if isNull r.Value.ActualResponse.Links then Seq.empty
                                    else
                                        Restler.Annotations.getAnnotationsFromOpenapiLinks requestId r.Value.ActualResponse.Links swaggerDoc

                                {| bodyResponse = bodyResponseSchema
                                   headerResponse = headerResponseSchema
                                   linkAnnotations = linkAnnotations |}
                        }

                        // 'allResponseProperties' contains the schemas of all possible responses
                        // Pick just the first one for now
                        // TODO: capture all of them and generate cases for each one in the response parser
                        let response = allResponses |> Seq.tryHead

                        let localAnnotations = Restler.Annotations.getAnnotationsFromExtensionData m.Value.ExtensionData "x-restler-annotations"

                        let requestMetadata =
                            {
                                isLongRunningOperation =
                                    match SchemaUtilities.getExtensionDataBooleanPropertyValue m.Value.ExtensionData "x-ms-long-running-operation" with
                                    | None -> false
                                    | Some v -> v
                            }

                        yield (requestId, { RequestData.requestParameters = requestParameters
                                            localAnnotations = localAnnotations
                                            linkAnnotations =
                                                match response with
                                                | None -> Seq.empty
                                                | Some r -> r.linkAnnotations
                                            responseProperties =
                                                match response with
                                                | None -> None
                                                | Some r -> r.bodyResponse
                                            responseHeaders =
                                                match response with
                                                | None -> []
                                                | Some r -> r.headerResponse
                                            requestMetadata = requestMetadata
                                            exampleConfig = exampleConfig })
        }
        requestDataSeq

    logTimingInfo "Getting requests..."

    // When multiple Swagger files are used, the request data is the union of all requests.
    let requestData, perResourceDictionaries =
        let orderedSwaggerDocs =
            swaggerDocs |> List.mapi (fun i sd -> (i, sd))
        let processed =
            orderedSwaggerDocs.AsParallel()
                              .AsOrdered()
                              .Select(fun (i, sd) ->
                                         let r = getRequestData sd.swaggerDoc sd.xMsPathsMapping
                                         r, i, sd.dictionary)
                              .ToList()
        let perResourceDictionariesSeq =
            processed
            |> Seq.map (fun (reqList, i, dictionary) ->
                            match dictionary with
                            | None -> Seq.empty
                            | Some d ->
                                let dictionaryName = sprintf "dict_%d" i
                                reqList |> Seq.map (fun (reqId, _) ->
                                                        reqId.endpoint, (dictionaryName, d)))
            |> Seq.concat
            |> Seq.distinctBy (fun (endpoint, (dictName, _)) -> endpoint, dictName)

        // Fail if there are multiple instances of the same endpoint across Swagger files
        // This detects when two different dictionaries are requested for the same endpoint.
        let multipleEndpoints =
            perResourceDictionariesSeq
            |> Seq.countBy fst
            |> Seq.filter (fun (_, count) -> count > 1)

        if multipleEndpoints |> Seq.length > 0 then
            let errorMessage = sprintf "Endpoints were specified twice in two different Swagger files: %A" multipleEndpoints
            raise (ArgumentException(errorMessage))

        let perResourceDictionaries =
            perResourceDictionariesSeq |> Map.ofSeq

        let requestData = processed |> Seq.map (fun (x,_,_) -> x) |> Seq.concat
                          |> Seq.toArray

        requestData, perResourceDictionaries

    // When multiple Swagger files are used, global annotations are applied across all Swagger files.
    let globalAnnotations =
        let perSwaggerAnnotations =
            swaggerDocs
            |> List.map (fun sd ->
                            let inlineAnnotations =
                                Restler.Annotations.getAnnotationsFromExtensionData sd.swaggerDoc.ExtensionData "x-restler-global-annotations"
                                |> Seq.toList
                            let externalAnnotations =
                                match sd.globalAnnotations with
                                | None -> List.empty
                                | Some g -> g
                            [inlineAnnotations ; externalAnnotations ]
                            |> List.concat
                         )
            |> List.concat
        [perSwaggerAnnotations ; globalExternalAnnotations]
        |> List.concat


    logTimingInfo "Getting dependencies..."
    let dependenciesIndex, orderingConstraints, newDictionary =
        Restler.Dependencies.extractDependencies
                requestData
                globalAnnotations
                dictionary
                config.ResolveQueryDependencies
                config.ResolveBodyDependencies
                config.ResolveHeaderDependencies
                config.AllowGetProducers
                config.DataFuzzing
                perResourceDictionaries
                config.ApiNamingConvention

    logTimingInfo "Generating request primitives..."


    // The dependencies above are analyzed on a per-request basis.
    // This can lead to missing dependencies (for example, an input producer writer
    // may be missing because the same parameter already refers to a reader).
    // As a workaround, the function below handles such issues by finding and fixing up the
    // problematic cases.
    let dependenciesIndex, orderingConstraints = Restler.Dependencies.mergeDynamicObjects dependenciesIndex orderingConstraints

    let dependencies =
        dependenciesIndex
        |> Seq.map (fun kvp -> kvp.Value)
        |> Seq.concat
        |> Seq.toList

    let dependencyInfo = getResponseParsers dependencies orderingConstraints

    let basePath =
        // Remove the ending slash if present, since a static slash will
        // be inserted in the grammar
        // Note: this code is not sufficient, and the same logic must be added in the engine,
        // since the user may specify their own base path through a custom payload.
        // However, this is included here as well so reading the grammar is not confusing and for any
        // other tools that may process the grammar separately from the engine.
        let bp = swaggerDocs.[0].swaggerDoc.BasePath
        if String.IsNullOrEmpty bp then ""
        elif bp.EndsWith("/") then
            bp.[0..bp.Length-2]
        else
            bp
    let host = swaggerDocs.[0].swaggerDoc.Host

    // Get the request primitives for each request
    let requests, newDictionary =
        requestData
        |> Seq.mapFold ( fun currentDict (requestId, rd) ->
                            generateRequestPrimitives
                                requestId
                                (dependencyInfo |> Map.tryFind requestId)
                                rd.requestParameters
                                dependenciesIndex
                                basePath
                                host
                                config.ResolveQueryDependencies
                                config.ResolveBodyDependencies
                                config.ResolveHeaderDependencies
                                currentDict
                                rd.requestMetadata
                        ) newDictionary

    // If discoverExamples was specified, return the newly discovered examples
    let examples =
        requestData
        |> Seq.choose ( fun (requestId, rd) ->
                            match rd.exampleConfig with
                            | None -> None
                            | Some [] -> None
                            | Some ep ->
                                let examplePayloads =
                                    ep
                                    |> List.choose (fun x -> x.exampleFilePath)
                                    |> List.mapi (fun i fp ->
                                                    { ExamplePayload.name = i.ToString()
                                                      filePathOrInlinedPayload = ExamplePayloadKind.FilePath fp
                                                    })
                                let method =
                                    { ExampleMethod.name = requestId.method.ToString()
                                      examplePayloads = examplePayloads }

                                Some (requestId.endpoint, method))
        |> Seq.groupBy (fun (endpoint, _) -> endpoint)
        |> Seq.map (fun (endpoint, methods) ->
                        { ExamplePath.path = endpoint
                          ExamplePath.methods = methods |> Seq.map snd |> Seq.toList })

    let requests =
        requests |> Seq.map (fun req ->
                                match req.id.xMsPath with
                                | None -> req
                                | Some xMsPath -> XMsPaths.replaceWithOriginalPaths req)
                 |> Seq.toList

    { Requests = requests },
    dependencies,
    (newDictionary, perResourceDictionaries),
    examples
