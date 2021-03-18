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

let getResponseParsers (dependencies:seq<ProducerConsumerDependency>) =
    // Index the dependencies by request ID.
    let parsers = new Dictionary<RequestId, ResponseParser>()

    // Generate the parser for all the consumer variables (Note this means we need both producer
    // and consumer pairs.  A response parser is only generated if there is a consumer for one or more of the
    // response properties.)
    dependencies
    |> Seq.choose (fun dep -> match dep.producer with
                               | Some (ResponseObject p) ->
                                    let writerVariable =
                                        {
                                            requestId = p.id.RequestId
                                            accessPathParts = p.id.AccessPathParts
                                        }
                                    Some writerVariable
                               | _ -> None)
    |> Seq.iter (fun writerVariable ->
                    let requestId = writerVariable.requestId

                    if parsers.ContainsKey(requestId) then
                        // Producer may be linked to multiple consumers in separate dependency pairs, so check it
                        // has not been added yet.
                        match parsers.[requestId].writerVariables |> List.tryFind  (fun p -> p = writerVariable) with
                        | Some p -> ()
                        | None ->
                            parsers.[requestId] <-
                                { parsers.[requestId] with writerVariables =
                                                            parsers.[requestId].writerVariables @ [writerVariable] }
                    else
                        parsers.Add(requestId,
                                    {
                                        writerVariables = [ writerVariable ]
                                    })
                 )
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

    let getPathParameterPayload (payload:ParameterPayload) =
        match payload with
        | LeafNode ln ->
            ln.payload
        | _ -> raise (UnsupportedType "Complex path parameters are not supported")

    let pathParameters (swaggerMethodDefinition:OpenApiOperation) (endpoint:string) =
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
                                           let schema = parameter.ActualSchema
                                           let leafProperty = getFuzzableValueForProperty ""
                                                                        schema
                                                                        true (*IsRequired*)
                                                                        false (*IsReadOnly*)
                                                                        (tryGetEnumeration schema)
                                                                        (tryGetDefault schema)

                                           let payload = LeafNode leafProperty
                                           Some (parameterName, payload))

        ParameterList parameterList

    let private getParametersFromExample (examplePayload:ExampleRequestPayload)
                                         (parameterList:seq<OpenApiParameter>) =
        parameterList
        |> Seq.choose (fun declaredParameter ->
                            // If the declared parameter isn't in the example, skip it.  Here, the example is used to
                            // select which parameters must be passed to the API.
                            match examplePayload.parameterExamples
                                  |> List.tryFind (fun r -> r.parameterName = declaredParameter.Name) with
                            | None -> None
                            | Some found ->
                                match found.payload with
                                | PayloadFormat.JToken payloadValue->
                                    let parameterGrammarElement =
                                        generateGrammarElementForSchema declaredParameter.ActualSchema (Some payloadValue) [] id
                                    Some (declaredParameter.Name, parameterGrammarElement)
                        )

    let private getParameters (parameterList:seq<OpenApiParameter>)
                               (exampleConfig:ExampleRequestPayload list option) (dataFuzzing:bool) =

        // When data fuzzing is specified, both the full schema and examples should be available for analysis.
        // Otherwise, use the first example if it exists, or the schema, and return a single schema.
        let examplePayloads =
            match exampleConfig with
            | None -> None
            | Some [] -> None
            | Some (firstExample::remainingExamples) ->
                // Use the first example specified to determine the parameter schema and values.
                let firstPayload = getParametersFromExample firstExample parameterList
                let restOfPayloads =
                    remainingExamples |> List.map (fun e -> getParametersFromExample e parameterList)
                Some (firstPayload::restOfPayloads)

        let schemaPayload =
            if dataFuzzing || examplePayloads.IsNone then
                Some (parameterList |> Seq.map (fun p -> (p.Name, generateGrammarElementForSchema p.ActualSchema None [] id)))
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

    let queryParameters (swaggerMethodDefinition:OpenApiOperation) exampleConfig dataFuzzing =
        let queryParameters = swaggerMethodDefinition.ActualParameters
                                   |> Seq.filter (fun p -> p.Kind = NSwag.OpenApiParameterKind.Query)
        // add shared parameters for the endpoint, if any
        let declaredSharedQueryParameters =
            getSharedParameters swaggerMethodDefinition.Parent.Parameters NSwag.OpenApiParameterKind.Query

        let allQueryParameters =
            [queryParameters ; declaredSharedQueryParameters ] |> Seq.concat
        getParameters allQueryParameters exampleConfig dataFuzzing

    let bodyParameters (swaggerMethodDefinition:OpenApiOperation) exampleConfig dataFuzzing =
        let bodyParameters = swaggerMethodDefinition.ActualParameters
                                   |> Seq.filter (fun p -> p.Kind = NSwag.OpenApiParameterKind.Body)
        // add shared parameters for the endpoint, if any
        let declaredSharedBodyParameters =
            getSharedParameters swaggerMethodDefinition.Parent.Parameters NSwag.OpenApiParameterKind.Body

        let allBodyParameters =
            [bodyParameters ; declaredSharedBodyParameters ] |> Seq.concat
        getParameters allBodyParameters exampleConfig dataFuzzing

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
            parameterList |> Map.ofSeq
        | _ -> raise (UnsupportedType "Only a list of path parameters is supported.")

    let path =
        (basePath + requestId.endpoint).Split([|'/'|], StringSplitOptions.RemoveEmptyEntries)
        |> Array.choose (fun p ->
                        if Parameters.isPathParameter p then
                            let consumerResourceName = Parameters.getPathParameterName p
                            match pathParameters |> Map.tryFind consumerResourceName with
                            | Some parameterPayload ->
                                let (propertyName, propertyPayload), _ =
                                    Restler.Dependencies.DependencyLookup.getDependencyPayload
                                                dependencies
                                                None
                                                requestId
                                                (consumerResourceName, parameterPayload)
                                                dictionary
                                Some (Parameters.getPathParameterPayload propertyPayload)
                            | None ->
                                // Parameter not found in parameter list.  This error was previously reported.
                                None
                        else
                            Some (Constant (PrimitiveType.String, p))
                      )
        |> Array.toList

    // Assign dynamic objects to query parameters if they have dependencies.
    // When there is more than one parameter set, the dictionary must be the one for the schema.
    //
    let queryParameters =
        requestParameters.query
        |> List.map (fun (payloadSource, requestQuery) ->
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
                        (payloadSource, ParameterList parameterList)
                     )

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

    let customHeaders =
        match dictionary.restler_custom_payload_header with
        | None -> []
        | Some headersMap ->
            headersMap |>
            Map.fold (fun headers headerKey headerValues ->
                match headerValues with
                | [] -> (headerKey, "") :: headers
                | [singleHeaderValue] -> (headerKey, singleHeaderValue) :: headers
                | multipleHeaderValues -> (headerKey, Microsoft.FSharpLu.Json.Compact.serialize multipleHeaderValues ) :: headers
            ) []
            |> List.rev

    let headers =
        ([ ("Accept", "application/json")
           ("Host", host)] @
           contentHeaders @ customHeaders
           )
    {
        id = requestId
        Request.method = method
        Request.path = path
        queryParameters = queryParameters
        httpVersion = "1.1"
        headers = headers
        token = TokenKind.Refreshable
        bodyParameters = bodyParameters
        responseParser  = responseParser
        requestMetadata = requestMetadata
    },
    newDictionary

/// Generates the requests, dynamic objects, and response parsers required for the main RESTler algorithm
let generateRequestGrammar (swaggerDocs:Types.ApiSpecFuzzingConfig list)
                           (dictionary:MutationsDictionary)
                           (config:Restler.Config.Config)
                           (globalExternalAnnotations: ProducerConsumerAnnotation list) =
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

                        if useBodyExamples || useQueryExamples || config.DiscoverExamples then
                            let exampleRequestPayloads = getExampleConfig m.Value config.DiscoverExamples config.ExamplesDirectory
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
                                RequestParameters.path = Parameters.pathParameters m.Value ep
                                RequestParameters.query =
                                    let useQueryExamples =
                                        config.UseQueryExamples |> Option.defaultValue false
                                    Parameters.queryParameters m.Value (if useQueryExamples then exampleConfig else None) config.DataFuzzing
                                RequestParameters.body =
                                    let useBodyExamples =
                                        config.UseBodyExamples |> Option.defaultValue false
                                    Parameters.bodyParameters m.Value (if useBodyExamples then exampleConfig else None) config.DataFuzzing
                            }

                        let allResponseProperties = seq {
                            for r in m.Value.Responses do
                                if validResponseCodes |> List.contains r.Key && not (isNull r.Value.ActualResponse.Schema) then
                                    yield generateGrammarElementForSchema r.Value.ActualResponse.Schema None [] id
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
                            [inlineAnnotations ; externalAnnotations ] |> List.concat
                         )
            |> List.concat
        [perSwaggerAnnotations ; globalExternalAnnotations] |> List.concat

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

    // Get the examples
    let examples =
        requestData
        |> Seq.choose ( fun (requestId, rd) ->
                            match rd.exampleConfig with
                            | None -> None
                            | Some [] -> None
                            | Some ep ->
                                let exampleFiles =
                                    ep |> List.choose (fun x -> x.exampleFilePath)
                                Some ((requestId.endpoint, requestId.method.ToString()), exampleFiles))
        |> Map.ofSeq

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
