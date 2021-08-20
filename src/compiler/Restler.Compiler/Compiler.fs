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

exception UnsupportedParameterSerialization of string

module Types =
    /// A configuration associated with a single Swagger document
    type ApiSpecFuzzingConfig =
        {
            swaggerDoc : OpenApiDocument

            dictionary: MutationsDictionary option

            globalAnnotations: ProducerConsumerAnnotation list option
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

let getWriterVariable (producer:Producer) =

    match producer with
    | InputParameter (iop, _) ->
        {
            requestId = iop.id.RequestId
            accessPathParts = iop.getInputParameterAccessPath()
        }
    | ResponseObject rp ->
        {
            requestId = rp.id.RequestId
            accessPathParts = rp.id.AccessPathParts
        }
    | _ ->
        raise (invalidArg "producer" "only input parameter and response producers have an associated dynamic object")

let getResponseParsers (dependencies:seq<ProducerConsumerDependency>) =
    // Index the dependencies by request ID.
    let parsers = new Dictionary<RequestId, ResponseParser>()

   // Generate the parser for all the consumer variables (Note this means we need both producer
    // and consumer pairs.  A response parser is only generated if there is a consumer for one or more of the
    // response properties.)
    dependencies
    |> Seq.choose (fun dep ->

                        match dep.producer with
                        | Some (ResponseObject _) ->
                            let writerVariable = getWriterVariable dep.producer.Value
                            Some (writerVariable, true)
                        | Some (InputParameter (_, _)) ->
                            let writerVariable = getWriterVariable dep.producer.Value
                            Some (writerVariable, false)
                        | _ -> None)
    // Remove duplicates
    // Producer may be linked to multiple consumers in separate dependency pairs
    |> Seq.distinct
    |> Seq.groupBy (fun (writerVariable, _) -> writerVariable.requestId)
    |> Map.ofSeq
    |> Map.iter (fun requestId writerVariables ->
                    let writerVariables, inputWriterVariables =
                        writerVariables
                        |> Seq.fold
                            (fun  (writerVariables, inputWriterVariables)
                                    (writerVariable, isResponseObject) ->
                                    if isResponseObject then
                                        (writerVariable::writerVariables, inputWriterVariables)
                                    else
                                        (writerVariables, writerVariable::inputWriterVariables)) ([], [])
                    let parser =
                        {
                            writerVariables = writerVariables
                            inputWriterVariables = inputWriterVariables
                        }

                    parsers.Add(requestId, parser))
    parsers

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

    let isPathParameter (p:string) = p.StartsWith "{"

    let getPathParameterName(p:string) = p.[1 .. p.Length-2]

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
        let exampleParameters =
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
                                    let parameterGrammarElement =
                                        generateGrammarElementForSchema declaredParameter.ActualSchema
                                                                        (Some payloadValue, false) trackParameters
                                                                        (declaredParameter.IsRequired, (parameterIsReadOnly declaredParameter))
                                                                        [] id
                                    Some { name = declaredParameter.Name
                                           payload = parameterGrammarElement
                                           serialization = getParameterSerialization declaredParameter }
                )

        examplePayload.parameterExamples
        |> List.filter (fun exampleParameter ->
                            exampleParameter.parameterName <> bodyName &&
                            parameterList |> Seq.tryFind (fun dp -> dp.Name = exampleParameter.parameterName) = None)
        |> List.iter (fun p -> printfn "Warning: example parameter not found in spec: %s" p.parameterName)
        exampleParameters

    // Gets the first example found from the open API parameter:
    // The priority is:
    // - first, check the 'Example' property
    // - then, check the 'Examples' property
    let getExamplesFromParameter (p:OpenApiParameter) =
        let schemaExample =
            if isNull p.Schema then None
            else
                SchemaUtilities.tryGetSchemaExampleAsString p.Schema
        match schemaExample with
        | Some e ->
            Some e
        | None ->
            if not (isNull p.Examples) then
                if p.Examples.Count > 0 then
                    let firstExample = p.Examples.First()
                    let exValue =
                        let v = firstExample.Value.Value.ToString()
                        if p.Type = NJsonSchema.JsonObjectType.Array ||
                            p.Type = NJsonSchema.JsonObjectType.Object then
                            v
                        else
                            sprintf "\"%s\"" v
                    Some exValue
                else
                    None
            else
                None

    let pathParameters (swaggerMethodDefinition:OpenApiOperation) (endpoint:string)
                       (exampleConfig: ExampleRequestPayload list option)
                       (trackParameters:bool) =
        let declaredPathParameters = swaggerMethodDefinition.ActualParameters
                                     |> Seq.filter (fun p -> p.Kind = NSwag.OpenApiParameterKind.Path)

        // add shared parameters for the endpoint, if any
        let declaredSharedPathParameters =
            if isNull swaggerMethodDefinition.Parent.Parameters then Seq.empty
            else
                swaggerMethodDefinition.Parent.Parameters
                |> Seq.filter (fun p -> p.Kind = NSwag.OpenApiParameterKind.Path)

        let allDeclaredPathParameters =
            [declaredPathParameters ; declaredSharedPathParameters ] |> Seq.concat

        let parameterList =
            endpoint.Split([|'/'|], StringSplitOptions.RemoveEmptyEntries)
            |> Array.filter (fun p -> isPathParameter p)
            // By default, all path parameters are fuzzable (unless a producer or custom value is found for them later)
            |> Seq.choose (fun part -> let parameterName = getPathParameterName part
                                       let declaredParameter = allDeclaredPathParameters |> Seq.tryFind (fun p -> p.Name = parameterName)

                                       match declaredParameter with
                                       | None ->
                                           printfn "Error: path parameter not found for parameter name: %s.  This usually indicates an invalid Swagger file." parameterName
                                           None
                                       | Some parameter ->
                                            let serialization = getParameterSerialization parameter
                                            let schema = parameter.ActualSchema
                                           // Check for path examples in the Swagger specification
                                           // External path examples are not currently supported
                                            match exampleConfig with
                                            | None
                                            | Some [] ->
                                                let leafProperty =
                                                     if schema.IsArray then
                                                         raise (Exception("Arrays in path examples are not supported yet."))
                                                     else
                                                        let specExampleValue = getExamplesFromParameter parameter
                                                        getFuzzableValueForProperty ""
                                                                                     schema
                                                                                     true (*IsRequired*)
                                                                                     false (*IsReadOnly*)
                                                                                     (tryGetEnumeration schema)
                                                                                     (tryGetDefault schema)
                                                                                     specExampleValue
                                                                                     trackParameters
                                                Some { name = parameterName
                                                       payload = LeafNode leafProperty
                                                       serialization = serialization }
                                            | Some (firstExample::remainingExamples) ->
                                                // Use the first example specified to determine the parameter value.
                                                getParametersFromExample firstExample (parameter |> stn) trackParameters
                                                |> Seq.head
                                                |> Some
                            )
        ParameterList parameterList

    let private getParameters (parameterList:seq<OpenApiParameter>)
                              (exampleConfig:ExampleRequestPayload list option)
                              (dataFuzzing:bool)
                              (trackParameters:bool) =

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
                                        match getExamplesFromParameter p with
                                        | None -> None
                                        | Some exValue ->
                                            SchemaUtilities.tryParseJToken exValue

                                    let parameterPayload = generateGrammarElementForSchema
                                                                p.ActualSchema
                                                                (specExampleValue, true)
                                                                trackParameters
                                                                (p.IsRequired, (parameterIsReadOnly p))
                                                                [] id
                                    // Add the name to the parameter payload
                                    let parameterPayload =
                                        match parameterPayload with
                                        | LeafNode leafProperty ->
                                            let leafNodePayload =
                                                match leafProperty.payload with
                                                | Fuzzable (Enum(propertyName, propertyType, values, defaultValue), x, y, z) ->
                                                    Fuzzable (Enum(p.Name, propertyType, values, defaultValue), x, y, z)
                                                | Fuzzable (a, b, c, _) ->
                                                    Fuzzable (a, b, c, if trackParameters then Some p.Name else None)
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

    let getSharedParameters (parameters:ICollection<OpenApiParameter>) parameterKind =
        if isNull parameters then Seq.empty
        else
            parameters
            |> Seq.filter (fun p -> p.Kind = parameterKind)

    let getAllParameters (swaggerMethodDefinition:OpenApiOperation)
                         (parameterKind:NSwag.OpenApiParameterKind)
                         exampleConfig dataFuzzing
                         trackParameters =
        let localParameters = swaggerMethodDefinition.ActualParameters
                              |> Seq.filter (fun p -> p.Kind = parameterKind)
        // add shared parameters for the endpoint, if any
        let declaredSharedParameters =
            getSharedParameters swaggerMethodDefinition.Parent.Parameters parameterKind

        let allParameters =
            [localParameters ; declaredSharedParameters ] |> Seq.concat
        getParameters allParameters exampleConfig dataFuzzing trackParameters

let generateRequestPrimitives (requestId:RequestId)
                               (responseParser:ResponseParser option)
                               (requestParameters:RequestParameters)
                               (dependencies:Dictionary<string, List<ProducerConsumerDependency>>)
                               basePath
                               (host:string)
                               (resolveQueryDependencies:bool)
                               (resolveBodyDependencies:bool)
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

    let path =
        (basePath + requestId.endpoint).Split([|'/'|], StringSplitOptions.RemoveEmptyEntries)
        |> Array.choose (fun p ->
                          if Parameters.isPathParameter p then
                            let consumerResourceName = Parameters.getPathParameterName p
                            match pathParameters |> Map.tryFind consumerResourceName with
                            | Some rp ->
                                let newRequestParameter, _ =
                                    Restler.Dependencies.DependencyLookup.getDependencyPayload
                                                dependencies
                                                None
                                                requestId
                                                rp
                                                dictionary
                                Some (Parameters.getPathParameterPayload newRequestParameter.payload)
                            | None ->
                                // Parameter not found in parameter list.  This error was previously reported.
                                None
                          else
                            Some (Constant (PrimitiveType.String, p))
                      )
        |> Array.toList

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
    // Do not compute dependencies for header parameters.
    let headerParameters, replacedCustomPayloadHeaders =
        let headersSpecifiedAsCustomPayloads = dictionary.getCustomPayloadHeaderParameterNames()
        requestParameters.header
        |> List.mapFold (fun newReplacedPayloadHeaders (payloadSource, requestHeaders) ->
                            let newParameterList =
                                // The grammar should always have examples, if they exist here,
                                // which implies that 'useExamples' was specified by the user.
                                match requestHeaders with
                                | ParameterList parameterList ->
                                    // Filter out the headers specified as custom payloads.
                                    // They will be added separately.
                                    parameterList
                                    // Filter out the 'Content-Length' parameter if it is specified in the spec.
                                    // This parameter must be computed by the engine, and should not be fuzzed.
                                    |> Seq.filter (fun rp -> rp.name <> "Content-Length")
                                    |> Seq.map (fun requestParameter ->
                                                    replaceCustomPayloads CustomPayloadType.Header headersSpecifiedAsCustomPayloads requestParameter)
                                | _ -> raise (UnsupportedType "Only a list of header parameters is supported.")
                            let parameterList =
                                newParameterList |> Seq.map fst |> Seq.toList
                            let replacedPayloadHeaders =
                                newParameterList
                                |> Seq.filter (fun (_, isReplaced) -> isReplaced)
                                |> Seq.map (fun (p,_) -> p.name)
                                |> Seq.toList
                            (payloadSource, ParameterList parameterList),
                            [ replacedPayloadHeaders ; newReplacedPayloadHeaders ]
                            |> List.concat
                         ) []

    // Assign dynamic objects to query parameters if they have dependencies.
    // When there is more than one parameter set, the dictionary must be the one for the schema.
    //
    let queryParameters, replacedCustomPayloadQueries =
        let queriesSpecifiedAsCustomPayloads = dictionary.getCustomPayloadQueryParameterNames()
        requestParameters.query
        |> List.mapFold (fun newReplacedPayloadQueries (payloadSource, requestQuery) ->
                            let parameterList =
                                // The grammar should always have examples, if they exist here,
                                // which implies that 'useExamples' was specified by the user.
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

                            let replacedPayloadQueries =
                                parameterList
                                |> Seq.filter (fun p -> queriesSpecifiedAsCustomPayloads |> Seq.contains p.name)
                                |> Seq.map (fun p -> p.name)
                                |> Seq.toList

                            (payloadSource, ParameterList parameterList),
                            [ replacedPayloadQueries ; newReplacedPayloadQueries ]
                            |> List.concat
                         ) []

    let bodyParameters, newDictionary =
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

    let contentHeaders =
        let requestHasBody = match (requestParameters.body |> Seq.head |> snd) with
                             | ParameterList p -> p |> Seq.length > 0
                             | Example (FuzzingPayload.Constant (PrimitiveType.String, str)) ->
                                not (String.IsNullOrWhiteSpace str)
                             | _ -> raise (UnsupportedType "unsupported body parameter type")
        if requestHasBody then
            [("Content-Type","application/json")]
        else []


    let getCustomPayloadParameters customPayloadType parametersFoundInSpec =
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

    let customPayloadHeaderParameters = getCustomPayloadParameters CustomPayloadType.Header replacedCustomPayloadHeaders

    // Note: only injecting custom payload query parameters is supported at this time.
    // For replacement, restler_custom_payload should be used.
    let customPayloadQueryParameters = getCustomPayloadParameters CustomPayloadType.Query replacedCustomPayloadQueries

    let headers =
        ([ ("Accept", "application/json")
           ("Host", host)] @
           contentHeaders
           )
    {
        id = requestId
        Request.method = method
        Request.path = path
        queryParameters = queryParameters @
                                [(ParameterPayloadSource.DictionaryCustomPayload,
                                  RequestParametersPayload.ParameterList customPayloadQueryParameters)]
        headerParameters = headerParameters @
                                [(ParameterPayloadSource.DictionaryCustomPayload,
                                  RequestParametersPayload.ParameterList customPayloadHeaderParameters)]
        httpVersion = "1.1"
        headers = headers
        token = TokenKind.Refreshable
        bodyParameters = bodyParameters
        responseParser  = responseParser
        inputDynamicObjectVariables = if responseParser.IsSome then responseParser.Value.inputWriterVariables else []
        requestMetadata = requestMetadata
    },
    newDictionary

/// Generates the requests, dynamic objects, and response parsers required for the main RESTler algorithm
let generateRequestGrammar (swaggerDocs:Types.ApiSpecFuzzingConfig list)
                           (dictionary:MutationsDictionary)
                           (config:Restler.Config.Config)
                           (globalExternalAnnotations: ProducerConsumerAnnotation list)
                           (userSpecifiedExamples:ExampleConfigFile option) =
    let getRequestData (swaggerDoc:OpenApiDocument) =
        let requestDataSeq = seq {
            for path in swaggerDoc.Paths do
                let ep = path.Key.TrimEnd([|'/'|])

                for m in path.Value do
                    let requestId = { RequestId.endpoint = ep;
                                      RequestId.method = getOperationMethodFromString m.Key }

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
                            let exampleRequestPayloads = getExampleConfig (ep,m.Key) m.Value config.DiscoverExamples config.ExamplesDirectory userSpecifiedExamples
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
                        let requestParameters =
                            {
                                RequestParameters.path =
                                    let usePathExamples =
                                        config.UsePathExamples |> Option.defaultValue false
                                    Parameters.pathParameters
                                            m.Value ep
                                            (if usePathExamples then exampleConfig else None)
                                            config.TrackFuzzedParameterNames
                                RequestParameters.header =
                                    let useHeaderExamples =
                                        config.UseHeaderExamples |> Option.defaultValue false
                                    Parameters.getAllParameters
                                        m.Value
                                        OpenApiParameterKind.Header
                                        (if useHeaderExamples then exampleConfig else None)
                                        config.DataFuzzing
                                        config.TrackFuzzedParameterNames
                                RequestParameters.query =
                                    let useQueryExamples =
                                        config.UseQueryExamples |> Option.defaultValue false
                                    Parameters.getAllParameters
                                        m.Value
                                        OpenApiParameterKind.Query
                                        (if useQueryExamples then exampleConfig else None)
                                        config.DataFuzzing
                                        config.TrackFuzzedParameterNames
                                RequestParameters.body =
                                    let useBodyExamples =
                                        config.UseBodyExamples |> Option.defaultValue false
                                    Parameters.getAllParameters
                                        m.Value
                                        OpenApiParameterKind.Body
                                        (if useBodyExamples then exampleConfig else None)
                                        config.DataFuzzing
                                        config.TrackFuzzedParameterNames
                            }

                        let allResponseProperties = seq {
                            for r in m.Value.Responses do
                                if validResponseCodes |> List.contains r.Key && not (isNull r.Value.ActualResponse.Schema) then
                                    yield generateGrammarElementForSchema r.Value.ActualResponse.Schema (None, false) false
                                                                          (true (*isRequired*), false (*isReadOnly*)) [] id
                        }

                        // 'allResponseProperties' contains the schemas of all possible responses
                        // Pick just the first one for now
                        // TODO: capture all of them and generate cases for each one in the response parser
                        let responseProperties = allResponseProperties |> Seq.tryHead

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
                                            responseProperties = responseProperties
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
                                         let r = getRequestData sd.swaggerDoc
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
    let dependenciesIndex, newDictionary = Restler.Dependencies.extractDependencies
                                            requestData
                                            globalAnnotations
                                            dictionary
                                            config.ResolveQueryDependencies
                                            config.ResolveBodyDependencies
                                            config.AllowGetProducers
                                            config.DataFuzzing
                                            perResourceDictionaries
                                            config.ApiNamingConvention

    logTimingInfo "Generating request primitives..."

    let dependencies =
        dependenciesIndex
        |> Seq.map (fun kvp -> kvp.Value)
        |> Seq.concat
        |> Seq.toList

    let responseParsers = getResponseParsers dependencies

    let basePath = swaggerDocs.[0].swaggerDoc.BasePath
    let host = swaggerDocs.[0].swaggerDoc.Host

    // Get the request primitives for each request
    let requests, newDictionary =
        requestData
        |> Seq.mapFold ( fun currentDict (requestId, rd) ->
                            let responseParser =
                                match responseParsers.TryGetValue(requestId) with
                                | (true, v ) -> Some v
                                | (false, _ ) -> None
                            generateRequestPrimitives
                                requestId
                                responseParser
                                rd.requestParameters
                                dependenciesIndex
                                basePath
                                host
                                config.ResolveQueryDependencies
                                config.ResolveBodyDependencies
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

    // Make sure the grammar will be stable by sorting elements as required before returning it.
    let requests =
        requests |> Seq.map (fun req ->
                                    // Writer variables should be ordered by identifier name
                                    let responseParser =
                                        match req.responseParser with
                                        | None -> None
                                        | Some rp ->
                                            Some ({ rp with writerVariables =
                                                                rp.writerVariables
                                                                |> List.sortBy (fun writerVariable ->
                                                                                    writerVariable.requestId.endpoint,
                                                                                    writerVariable.requestId.method,
                                                                                    writerVariable.accessPathParts.getJsonPointer().Value) } )
                                    { req with responseParser = responseParser })
                |> Seq.toList

    { Requests = requests },
    dependencies,
    (newDictionary, perResourceDictionaries),
    examples
