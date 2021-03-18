// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.Dependencies

open System.Collections.Generic
open Restler.Grammar
open System
open Restler.AccessPaths
open Restler.Dictionary
open Restler.Utilities.Operators
open Restler.Utilities.Logging
open Restler.ApiResourceTypes
open Restler.DependencyAnalysisTypes
open Restler.Annotations

exception UnsupportedType of string
exception InvalidSwaggerEndpoint

/// Determines whether a producer is valid for a given consumer.
let isValidProducer (p:ResponseProducer) (consumer:Consumer) (allowGetProducers:bool) =
    let consumerEndpoint, consumerMethod = consumer.id.RequestId.endpoint,
                                            consumer.id.RequestId.method
    let producerEndpoint, producerMethod = p.id.RequestId.endpoint,
                                            p.id.RequestId.method
    if not ([ OperationMethod.Put ; OperationMethod.Post ] |> Seq.contains producerMethod || allowGetProducers) then
        false
    else if consumerEndpoint = producerEndpoint then
        // The requests can't be identical
        if consumerMethod = producerMethod then
            false
        else
            // If the producer and consumer have the same endpoint,
            // and the producer is a POST, the consumer can be anything
            // '' PUT -> anything except POST
            // '' PATCH -> anything except PUT or POST
            // etc.
            match producerMethod with
            | OperationMethod.Post -> true
            | OperationMethod.Put -> consumerMethod <> OperationMethod.Post
            | OperationMethod.Patch ->
                consumerMethod <> OperationMethod.Put &&
                consumerMethod <> OperationMethod.Post
            | OperationMethod.Get ->
                consumerMethod <> OperationMethod.Put &&
                consumerMethod <> OperationMethod.Post &&
                consumerMethod <> OperationMethod.Patch
            | _ -> false
    else
        not (producerEndpoint.StartsWith(consumerEndpoint))

/// Handles the pattern of a PUT 'CreateOrUpdate'
/// Precondition: the consumer resource name is the last (right-most) path parameter.
// 'CreateOrUpdate' PUT requests are handled as follows:
// If the request is a PUT, update the mutation dictionary with a 'restler_custom_payload_uuid_suffix' entry
// The naming schema is 'consumerResourceName' followed by a dash.
// This is required to generate a new name on every PUT.
// Otherwise, make the PUT request the producer.
// TODO: there is currently a gap in coverage: only the create version of PUT will be executed by RESTler.
//
// For reference, below is the corresponding PUT annotation that causes the same producer-consumer
// to be identified as this function.
//{
//    "producer_resource_name": "name",
//    "producer_method": "PUT",
//    "consumer_param": "applicationGatewayName",
//    "producer_endpoint": "/subscriptions/{subscriptionId}/applicationGateways/{applicationGatewayName}",
//    "except": {
//        "consumer_endpoint":"/subscriptions/{subscriptionId}/applicationGateways/{applicationGatewayName}",
//        "consumer_method": "PUT"
//    }
//}
let getCreateOrUpdateProducer (consumer:Consumer)
                              dictionary
                              (producers:Producers)
                              consumerResourceName
                              producerParameterName
                              pathParameterIndex
                              (bracketedConsumerResourceName:string) =

    let matchProducer (producerParameterName:string) (producerEndpoint:string) =
        producers.getIndexedByEndpointProducers(producerParameterName, producerEndpoint, [OperationMethod.Put])

    // Find the producer endpoint
    let consumerEndpoint = consumer.id.RequestId.endpoint
    let producerEndpoint = consumerEndpoint.Substring(0, pathParameterIndex + bracketedConsumerResourceName.Length)

    // Pattern with ending path parameter - the producer
    if consumerEndpoint = producerEndpoint && consumer.id.RequestId.method = OperationMethod.Put then
        // WARNING: the code below creates a uuid suffix, but does not check that a dynamic object is
        // actually produced by the response.  The reasoning for this is that, if no dynamic object is
        // found, then it is possible one is not produced and resources will not be leaked.
        // If this turns out not to be the case, a fix is to check that the producer parameter name
        // exists (similar to the check in the 'else' branch below), and only use a uuid suffix if found, otherwise
        // use a static value.
        let dictionary =
            if dictionary.restler_custom_payload_uuid4_suffix.Value.ContainsKey(consumerResourceName) then
                dictionary
            else
                let prefixValue = generatePrefixForCustomUuidSuffixPayload consumerResourceName
                { dictionary with
                                restler_custom_payload_uuid4_suffix =
                                    Some (dictionary.restler_custom_payload_uuid4_suffix.Value.Add(consumerResourceName, prefixValue))
                }
        // The producer is a dictionary payload.  The code below makes sure the new dictionary is correctly
        // updated above for this resource.
        dictionary,
        (dictionary.getParameterForCustomPayloadUuidSuffix consumerResourceName consumer.id.AccessPathParts consumer.id.PrimitiveType) |> Seq.tryHead
    else
        // Find the corresponding PUT request, which is the producer, if it exists.
        if pathParameterIndex < 1 then
            raise (InvalidOperationException("This heuristic should only execute for path parameters."))

        let possibleProducers =
            // When the naming convention is not strictly compliant to the OpenAPI spec guidelines,
            // the name of the producer may be omitted from the path, e.g.
            // PUT /slots/{slot} returning a response with "id" or "name" as the dynamic object, instead of
            // more strict /slots/slotId returning "id".
            // Use the above heuristic when the inferred producer resource name is not present.
            let inferredResourceNameProducers = matchProducer producerParameterName producerEndpoint
            if inferredResourceNameProducers |> Seq.isEmpty then
                let commonProducerNames = ["id"; "name"]
                commonProducerNames
                |> Seq.map (fun name -> matchProducer name producerEndpoint)
                |> Seq.concat
            else
                inferredResourceNameProducers

        let resourceProducer =
            possibleProducers
            // HACK: sort the producers by increasing access path length.
            // This will fix a particular case in logic apps.
            // The proper way for users to fix this
            // is to provide an exact path-based annotation.
            |> Seq.sortBy (fun p ->
                                match p.id.AccessPath with
                                | None ->
                                    raise (Exception("Invalid case"))
                                | Some s -> s.Length)
            |> Seq.map ResponseObject
            |> Seq.tryHead

        dictionary, resourceProducer

let getSameBodyInputProducer (consumer:Consumer)
                             dictionary
                             (producers:Producers) =

    let consumerResourceName = consumer.id.ResourceName
    let producerResourceName = "name"
    if consumer.parameterKind = ParameterKind.Body && consumerResourceName = "id" then
        let producer =
            match consumer.id.BodyContainerName with
            | None ->
                // ID is passed at the root of the payload in a PUT statement, nothing to do.
                None
            | Some _ ->
                let candidateInputProducers =
                    producers.getSamePayloadProducers(producerResourceName, consumer.id.RequestId)

                candidateInputProducers
                |> Seq.choose (fun p ->
                                    if p.id.ContainerName.IsNone then
                                        raise (invalidArg "samePayloadProducers" "The producer container must always exist in same payload producers.")

                                    if p.id.RequestId.endpoint <> consumer.id.RequestId.endpoint then
                                        raise (invalidArg "samePayloadProducers" (sprintf "The endpoints should be identical: producer: %s consumer: %s" p.id.RequestId.endpoint consumer.id.RequestId.endpoint))

                                    let matchingProducerTypeNames =
                                        consumer.id.CandidateTypeNames
                                        |> Seq.choose (fun consumerName ->
                                                            p.id.CandidateTypeNames |> Seq.tryFind( fun x -> x = consumerName))
                                        // Use the longest matching word
                                        |> Seq.sortBy (fun consumerName -> -1 * consumerName.Length )

                                    match matchingProducerTypeNames |> Seq.tryHead with
                                    | None -> None
                                    | Some tn ->
                                        let isSelfReferencing() =
                                            p.id.getParentAccessPath() = consumer.id.getParentAccessPath()

                                        // Heuristic: only infer a producer if it is higher in the tree than the consumer
                                        // This helps avoid incorrectly assigned producers from child properties of
                                        // this payload
                                        let isProducerHigher =
                                            p.id.AccessPathParts.path.Length < consumer.id.AccessPathParts.path.Length

                                        if isProducerHigher && not (isSelfReferencing()) then
                                            Some (tn, p)
                                        else None
                              )
                |> Seq.sortBy (fun (typeName, p) -> -1 * typeName.Length)
                |> Seq.tryHead
        let x =
            match producer with
            | None -> None
            | Some (tn, p) -> Some (SameBodyPayload p)
        dictionary, x
    else
        dictionary, None

/// Gets the producer for a consumer that is a nested object ID, as follows:
/// { "Subnet": { "id" : <dynamic object> } }
/// For each property of a body parameter that has a parent object, this
/// function searches for a request with an endpoint that has the
/// parent object name as a prefix of its container.
/// For example, for the above subnet id, the matching producer
/// will be /api/subnets/{subnetName}.
/// When several matches are found, the shortest endpoint is chosen.
let getNestedObjectProducer (consumer:Consumer)
                              dictionary
                              (producers:Producers)
                              producerParameterName
                              allowGetProducers =

    match consumer.id.ContainerName with
    | None -> dictionary, None
    | Some cn ->
        // Find producers with container name whose type matches the consumer parent type.
        // Example 1: a path container with the same primary name (without suffix), e.g. 'virtualNetworks/{virtualNetworkName}'
        // Example 2: a body container where the path is a valid producer relative to the current path.
        //            e.g. PUT /some/resource that returns { ... 'virtualNetwork' : { 'id' : ...}}
        let findMatchingProducers typeNames =
            let matchingProducers =
                typeNames
                |> Seq.map (fun typeName ->
                                producers.getIndexedByTypeNameProducers(producerParameterName, typeName, false)
                                |> Seq.filter (fun (x:ResponseProducer) ->
                                                    not x.id.IsNestedBodyResource &&
                                                    [ OperationMethod.Put ; OperationMethod.Post ] |> Seq.contains x.id.RequestId.method
                                              ))
                |> Seq.concat
                |> Seq.cache
            let endpointsCount =
                matchingProducers
                |> Seq.map (fun (p:ResponseProducer) -> p.id.RequestId.endpoint)
                |> Seq.distinct
                |> Seq.length
            matchingProducers, endpointsCount

        let exactMatchingProducers, exactMatchingProducerEndpointsCount =
            findMatchingProducers (consumer.id.CandidateTypeNames |> Seq.take 1)

        // In some cases, multiple matches may be found (including the current endpoint+method)
        // This may cause circular dependencies if the other requests also consume the same object
        // (for example, multiple requests have a 'VirtualNetwork' type parameter, which is
        // also returned in the response, but is pre-provisioned by a separate API).
        // When multiple POST or PUT matches exist (possibly including the current request),
        // do not assign a dependency because whether a new dynamic object is being created
        // cannot be reliably determined (and arbitrarily breaking cycles is more confusing).
        // Note: when GET producers are used, this is not an issue because the body of a GET will not
        // contain consumers of this resource type.
        let dictionary, candidateProducers =
            match exactMatchingProducerEndpointsCount with
            | 0 ->
                let approximateProducers, approximateProducerEndpointsCount =
                    findMatchingProducers (consumer.id.CandidateTypeNames |> Seq.skip 1) // first type name already covered above
                match approximateProducerEndpointsCount  with
                | 1 ->
                    dictionary,
                    approximateProducers
                | _ -> dictionary, Seq.empty
            | 1 ->
                dictionary,
                exactMatchingProducers
            | _ -> dictionary, Seq.empty
        dictionary,
        candidateProducers
        |> Seq.filter (fun (p:ResponseProducer) ->
                            isValidProducer p consumer allowGetProducers)
        |> Seq.map ResponseObject
        |> Seq.tryHead


/// Find producer given a candidate producer resource name
/// Returns a producer matching the specified consumer.
/// May also return an updated dictionary.
let findProducerWithResourceName
                 (producers:Producers)
                 (consumer:Consumer)
                 (dictionary:MutationsDictionary)
                 (allowGetProducers:bool)
                 (perRequestDictionary:MutationsDictionary option)
                 (producerParameterName:string) =

    let consumerResourceName = consumer.id.ResourceName

    let consumerEndpoint = consumer.id.RequestId.endpoint
    let bracketedConsumerResourceName =
        if consumer.parameterKind = ParameterKind.Path then
            sprintf "{%s}" consumerResourceName
            |> Some
        else None
    let pathParameterIndex =
        match bracketedConsumerResourceName with
        | None -> None
        | Some bracketedName ->
            consumerEndpoint.IndexOf(bracketedName)
            |> Some

    let producerEndpoint, producerContainer =
        match consumer.parameterKind with
        | ParameterKind.Body
        | ParameterKind.Query -> None, None
        | ParameterKind.Path ->
            let producerEndpoint =
                // Search according to the path
                // producerEndpoint contains everything including the container
                if pathParameterIndex.Value = 0 then
                    raise InvalidSwaggerEndpoint
                else if pathParameterIndex.Value > 0 then
                    consumerEndpoint.Substring(0, pathParameterIndex.Value - 1)  // subtract one to remove the slash.
                    |> Some
                else
                    None

            // We need to find the container (here, "accounts") to filter a particular API structure that does not
            // fully conform to the OpenAPI spec (see below).
            let producerContainer =
                match producerEndpoint with
                | None -> None
                | Some ep -> ep.Split([|'/'|]) |> Seq.last |> Some
            producerEndpoint, producerContainer

    let matchingResourceProducers, matchingResourceProducersByEndpoint =
        // The logic below guards against including cases where the container returns a
        // matching field which belongs to a different class. For example, imagine
        // the following problematic path: dnsZones/{zoneName}/{recordType} and that
        // we are looking for "recordType", i.e., "type". This field should ideally
        // be in the following container "dnsZones/{zoneName}/records/. However,
        // because the structure is strange, without the following check, we will
        // match a field named "type" returned by  dnsZones/{zoneName} which will
        // be a zone type and not a record-type.
        // accounts starts with 'account'
        match producerContainer with
        | None ->
            Seq.empty, Seq.empty
        | Some pc when pc.StartsWith("{") ->
             Seq.empty, Seq.empty
        | Some pc ->
            producers.getSortedByMatchProducers(producerParameterName, true),
            if producerEndpoint.IsSome then
                producers.getIndexedByEndpointProducers(producerParameterName, producerEndpoint.Value,
                                                        [OperationMethod.Put; OperationMethod.Post;
                                                         OperationMethod.Get])
            else Seq.empty

    let annotationMatches =
        let ann = consumer.annotation
        match ann with
        | None -> Seq.empty
        | Some a ->
            let producersWithMatchingResourceIds =
                producers.getIndexedByEndpointProducers(a.producerId.resourceName, a.producerId.requestId.endpoint,
                                                        [ OperationMethod.Put ; OperationMethod.Post ; OperationMethod.Get ])

            // When the annotation has a path, the producer can be matched exactly
            // TODO: an unnamed resource, such as an array element, cannot be currently assigned as a producer, because
            // its name will be the array name.
            if producersWithMatchingResourceIds |> Seq.isEmpty then
                printfn "Annotated resource not found: %A" a

            match producersWithMatchingResourceIds
                    |> Seq.filter (fun p ->
                                            // Match on the path, if it exists,
                                            // otherwise match on the ID only
                                            match a.producerParameter with
                                            | ResourceName _ ->
                                                p.id.RequestId = a.producerId.requestId &&
                                                p.id.ResourceName = a.producerId.resourceName
                                            | ResourcePath annotationProducerResourcePath ->
                                                p.id.RequestId = a.producerId.requestId &&
                                                p.id.AccessPathParts = annotationProducerResourcePath
                                        )
                        // HACK: sort the producers by increasing access path length.
                        // This may fix particular customer cases when annotations are missing.
                        // The proper way to fix this
                        // is to provide an exact path-based annotation.
                    |> Seq.sortBy (fun p -> match p.id.AccessPath with
                                            | None ->
                                                raise (Exception("Invalid case"))
                                            | Some p -> p.Length)
                    |> Seq.tryHead with
            | None -> Seq.empty
            | Some matchingProducer ->
                match a.exceptConsumerId with
                | None -> stn matchingProducer
                | Some exceptConsumer ->
                    if consumer.id.RequestId = exceptConsumer then Seq.empty
                    else stn matchingProducer

    let dictionaryMatches =
        let perRequestDictionaryMatches =
            match perRequestDictionary with
            | None -> Seq.empty
            | Some d ->
                // TODO: error handling.  only one should match.
                d.getParameterForCustomPayload consumer.id.ResourceName consumer.id.AccessPathParts consumer.id.PrimitiveType
        let globalDictionaryMatches =
            dictionary.getParameterForCustomPayload consumer.id.ResourceName consumer.id.AccessPathParts consumer.id.PrimitiveType
        [
            perRequestDictionaryMatches
            globalDictionaryMatches
        ]
        |> Seq.concat

    let uuidSuffixDictionaryMatches =
        let perRequestDictionaryMatches =
            match perRequestDictionary with
            | None -> Seq.empty
            | Some d ->
                // TODO: error handling.  only one should match.
                d.getParameterForCustomPayloadUuidSuffix consumer.id.ResourceName consumer.id.AccessPathParts consumer.id.PrimitiveType
        let globalDictionaryMatches =
           dictionary.getParameterForCustomPayloadUuidSuffix consumer.id.ResourceName consumer.id.AccessPathParts consumer.id.PrimitiveType
        [
            perRequestDictionaryMatches
            globalDictionaryMatches
        ]
        |> Seq.concat

    // Here the producers just match on the resource name.  If the container also matches,
    // it will match fully.
    let inferredExactMatches = matchingResourceProducersByEndpoint
                               |> Seq.filter (fun (p:ResponseProducer) ->
                                                  isValidProducer p consumer allowGetProducers)

    let inferredApproximateMatches =
        matchingResourceProducers
        |> Seq.filter (fun p ->
                            if String.IsNullOrWhiteSpace p.id.RequestId.endpoint then false
                            else
                                // Everything up to the next dependency
                                // e.g. producerEndpoint = "/api/webhooks/account/{accountId}/blah/id"
                                // look for /api/webhooks/account/{accountId}/blah, /api/webhooks/account/{accountId}
                                let producerMatch =
                                    match producerEndpoint with
                                    | None -> false
                                    | Some pe ->
                                        pe.StartsWith(p.id.RequestId.endpoint) &&
                                        (not (pe.Replace(p.id.RequestId.endpoint, "").Contains("{"))) &&
                                        p.id.ResourceName = producerParameterName
                                // Check for the presence of the producer container in the path to this resource.
                                let containerMatch =
                                    match p.id.BodyContainerName, producerContainer with
                                    | None,_
                                    | _,None -> false
                                    | Some container, Some producerContainer ->
                                        container = producerContainer
                                producerMatch && containerMatch)
        |> Seq.filter (fun (p:ResponseProducer) ->
                           isValidProducer p consumer allowGetProducers)


    // Check for special case: PUT request that is both a producer and a consumer.
    // Conditions:
    // 1. There are no exact, annotation or dictionary matches (if there are, they should not be overridden).
    // 2. The consumer endpoint ends with 'consumerResourceName'.
    // 3. There is no POST request in exact producer matches.
    // 4. The consumer is a PUT request or there exists a PUT request with the same endpoint id.
    // Note: it's possible that a PUT parameter is specified in the body.
    // This case is not handled here, as it is not obvious which body parameter to use in such cases.
    let dictionary, producer =
        if consumer.parameterKind = ParameterKind.Path &&
           annotationMatches |> Seq.isEmpty &&
           // If there is a dictionary entry for a static value, it should override the inferred dependency
           (dictionary.getParameterForCustomPayload
                consumerResourceName
                consumer.id.AccessPathParts
                consumer.id.PrimitiveType
                )
            |> Seq.isEmpty &&
           inferredExactMatches |> Seq.isEmpty then

            getCreateOrUpdateProducer
                        consumer
                        dictionary
                        producers
                        consumerResourceName
                        producerParameterName
                        pathParameterIndex.Value
                        bracketedConsumerResourceName.Value
        else
            dictionary, None

    // Try to find a producer based on the container property name of the consumer in the body.
    let dictionary, producer =
        if producer.IsSome then
            dictionary, producer
        else if consumer.id.AccessPath.IsSome &&
             annotationMatches |> Seq.isEmpty &&
             // If there is a dictionary entry for a static value, it should override the inferred dependency
             (dictionary.getParameterForCustomPayload
                consumerResourceName
                consumer.id.AccessPathParts
                consumer.id.PrimitiveType)
             |> Seq.isEmpty &&
             (not (inferredExactMatches
                   |> Seq.exists (fun x -> x.id.RequestId.method = OperationMethod.Put ||
                                           x.id.RequestId.method = OperationMethod.Post))) then
            getNestedObjectProducer
                consumer
                dictionary
                producers
                producerParameterName
                allowGetProducers
        else dictionary, None

    let dictionary, producer =
        if producer.IsSome then
            dictionary, producer
        else
            dictionary,
            [   annotationMatches |> Seq.sortBy sortByMethod |> Seq.map ResponseObject
                dictionaryMatches
                uuidSuffixDictionaryMatches
                inferredExactMatches
                |> Seq.map ResponseObject
                inferredApproximateMatches
                |> Seq.map ResponseObject
            ]
            |> Seq.concat
            |> Seq.tryHead

    dictionary, producer


let findProducer (producers:Producers)
                 (consumer:Consumer)
                 (dictionary:MutationsDictionary)
                 (allowGetProducers:bool)
                 (perRequestDictionary:MutationsDictionary option) =

    let possibleProducerParameterNames =
        // Try both the producer parameter name as inferred by naming convention,
        // and a match for the consumer resource (i.e. parameter) name itself.
        [ consumer.id.ProducerParameterName ; consumer.id.ResourceName ]

    let matchingProducers =
        possibleProducerParameterNames
        |> Seq.distinct
        |> Seq.choose (
            fun producerParameterName ->
                let mutationsDictionary, producer =
                    findProducerWithResourceName
                        producers
                        consumer
                        dictionary
                        allowGetProducers
                        perRequestDictionary
                        producerParameterName
                if producer.IsSome then
                    Some (mutationsDictionary, producer)
                else None
            )
    match matchingProducers |> Seq.tryHead with
    | Some result -> result
    | None -> dictionary, None

type PropertyAccessPath =
    {
        Name : string
        Path : AccessPath
    }

module private PropertyAccessPaths =
    // A leaf property may have a null name if it is an array item
    let getLeafPropertyAccessPath propertyName =
        if System.String.IsNullOrWhiteSpace propertyName then []
        else [propertyName]

    let getInnerPropertyAccessPathParts (p:InnerProperty) =
        seq {
            if not (System.String.IsNullOrWhiteSpace p.name) then
                yield p.name
            match p.propertyType with
            | Object
            | Property ->
                ()
            | Array ->
                yield "[0]"
        }
        |> Seq.toList

    let getInnerPropertyAccessPath (p:InnerProperty) =
        getInnerPropertyAccessPathParts p

    /// Gets an access path to an internal tree node given its parent access path
    let getLeafAccessPath (parentAccessPath:string list) (p:LeafProperty) =
        parentAccessPath @ ((getLeafPropertyAccessPath p.name) |> Seq.toList)

    /// Gets an access path to an internal tree node given its parent access path
    let getInnerAccessPath (parentAccessPath:string list) (p:InnerProperty) =
        parentAccessPath @ (getInnerPropertyAccessPath p)

    /// Gets an access path to an internal tree node given its parent access path
    let getLeafAccessPathParts (parentAccessPath:string list) (p:LeafProperty) =
        parentAccessPath
        @
        (getLeafPropertyAccessPath p.name)

    /// Gets an access path to an internal tree node given its parent access path
    let getInnerAccessPathParts (parentAccessPath:string list) (p:InnerProperty) =
        parentAccessPath
        @
        getInnerPropertyAccessPathParts p

// Any parameter or property value may be a consumer
let findAnnotation globalAnnotations
                   (parameterMap:Map<RequestId, RequestData>)
                   (requestId:RequestId)
                   (resourceName:string)
                   (resourceAccessPath:AccessPath) =

    let annotationMatches consumerParameter resourceName resourceAccessPath =
        match consumerParameter with
        | ResourceName rn -> rn = resourceName
        | ResourcePath p ->
              resourceAccessPath = p

    let globalAnnotation =
        match globalAnnotations
              |> Seq.filter (fun a -> annotationMatches a.consumerParameter resourceName resourceAccessPath
                             ) with
        | g when g |> Seq.isEmpty -> None
        | g ->
            if g |> Seq.length > 1 then
                printfn "ERROR: found more than one matching annotation"
            g |> Seq.tryHead
    let localAnnotations =
        match parameterMap.TryFind requestId with
        | Some rd ->
            rd.localAnnotations
        | None -> Seq.empty

    let localAnnotation =
        match localAnnotations
              |> Seq.filter (fun a -> annotationMatches a.consumerParameter resourceName resourceAccessPath
                             ) with
        | g when g |> Seq.isEmpty -> None
        | g ->
            if g |> Seq.length > 1 then
                printfn "ERROR: found more than one matching annotation"
            g |> Seq.tryHead

    // Local annotation takes precedence
    match (localAnnotation, globalAnnotation) with
    | (Some l, _) -> Some l
    | (None, g) -> g

let getProducer (request:RequestId) (response:ResponseProperties) =

    // All possible properties in this response
    let accessPaths = List<PropertyAccessPath>()

    let visitLeaf2 (parentAccessPath:string list) (p:LeafProperty) =
        let resourceAccessPath = PropertyAccessPaths.getLeafAccessPathParts parentAccessPath p
        let name =
            if System.String.IsNullOrWhiteSpace p.name then
                match parentAccessPath |> List.tryFindBack (fun elem -> not (String.IsNullOrWhiteSpace elem || elem.StartsWith("["))) with
                | None ->
                    // This case occurs if the response returns a single unnamed value.
                    // RESTler does not currently infer a producer for such cases.
#if DEBUG
    // Disable this warning in release - it is noisy and the parent access path is always empty.  This
    // needs to be further investigated.
                    printfn "WARNING: unnamed property found in response %s, request: %A.  Producer not inferred."
                                (parentAccessPath |> String.concat ",")
                                request
#endif
                    None
                | Some propertyName ->
                    Some propertyName
            else Some p.name
        if name.IsSome then
            accessPaths.Add( { Name = name.Value
                               Path = { path = resourceAccessPath |> List.toArray } })

    let visitInner2 (parentAccessPath:string list) (p:InnerProperty) =
        ()

    if [ OperationMethod.Post ; OperationMethod.Put; OperationMethod.Patch ; OperationMethod.Get ]
       |> Seq.contains request.method then
        Tree.iterCtx visitLeaf2 visitInner2 PropertyAccessPaths.getInnerAccessPathParts [] response

    accessPaths

let getParameterDependencies parameterKind globalAnnotations
                             (requestData:(RequestId*RequestData)[])
                             (requestId:RequestId)
                             (parameterName, parameterPayload)
                             namingConvention =

    let consumerList = new List<Consumer>()
    let annotatedRequests = requestData
                            |> Seq.filter (fun (_, reqData) -> reqData.localAnnotations |> Seq.length > 0)
                            |> Map.ofSeq
    let getConsumer (resourceName:string) (resourceAccessPath:string list) (primitiveType:PrimitiveType option) =
        if String.IsNullOrEmpty resourceName then
            failwith "[getConsumer] invalid usage"
        let resourceReference =

            match parameterKind with
            | ParameterKind.Path ->

                let pathToParameter =
                    let x = requestId.endpoint.Split("/", StringSplitOptions.RemoveEmptyEntries)
                    let pathParamIndex =
                        x |> Array.findIndex (fun x -> x = sprintf "{%s}" parameterName)
                    x |> Array.take (pathParamIndex)
                PathResource { name = resourceName ;
                               PathParameterReference.responsePath = { path = Array.empty }
                               PathParameterReference.pathToParameter = pathToParameter }

            | ParameterKind.Query ->
                QueryResource resourceName
            | ParameterKind.Body ->
                BodyResource { name = resourceName ; fullPath = { path = resourceAccessPath |> List.toArray }}
        {
                id = ApiResource(requestId, resourceReference,
                                 namingConvention,
                                 if primitiveType.IsSome then primitiveType.Value else PrimitiveType.String)
                annotation = findAnnotation globalAnnotations annotatedRequests requestId resourceName { path = resourceAccessPath |> List.toArray }
                parameterKind = parameterKind
        }

    let visitLeaf (parentAccessPath:string list) (p:LeafProperty) =
        if not (String.IsNullOrEmpty p.name) then
            let resourceAccessPath = PropertyAccessPaths.getLeafAccessPath parentAccessPath p
            let primitiveType =
                match p.payload with
                | FuzzingPayload.Fuzzable (pt, _) -> Some pt
                | FuzzingPayload.Constant (pt, _) -> Some pt
                | FuzzingPayload.Custom c -> Some c.primitiveType
                | _ -> None
            let c = getConsumer p.name resourceAccessPath primitiveType
            consumerList.Add(c)

    let visitInner (parentAccessPath:string list) (p:InnerProperty) =
        if not (String.IsNullOrEmpty p.name) then
            let resourceAccessPath = PropertyAccessPaths.getInnerAccessPath parentAccessPath p
            let c = getConsumer p.name resourceAccessPath None
            consumerList.Add(c)

    match parameterKind with
    | ParameterKind.Path ->
        let c = getConsumer parameterName [] None
        consumerList.Add(c)
    | ParameterKind.Query ->
        if String.IsNullOrEmpty parameterName then
            Tree.iterCtx visitLeaf visitInner PropertyAccessPaths.getInnerAccessPath [] parameterPayload
        else
            let parameterDependency = getConsumer parameterName [] None
            consumerList.Add(parameterDependency)
    | ParameterKind.Body ->

        Tree.iterCtx visitLeaf visitInner PropertyAccessPaths.getInnerAccessPath [] parameterPayload

    consumerList |> List.ofSeq


/// Create a producer that is identified by its path in the body only.
/// For example, an API 'POST /products  { "tables": [{ "name": "ergoDesk" } ], "chairs": [{"name": "ergoChair"}]  }'
/// that returns the same body.
/// Here, the producer resource name is 'name', and the producer container is 'tables'.
let createBodyProducer (consumerResourceId:ApiResource) =
    {
        ResponseProducer.id = ApiResource(consumerResourceId.RequestId,
                                           consumerResourceId.ResourceReference,
                                           consumerResourceId.NamingConvention,
                                           consumerResourceId.PrimitiveType)
    }

/// Create a path producer that is the result of invoking an API endpoint, which
/// is identified by the last part of the endpoint.
/// For example: POST /customers, or PUT /product/{productName}
let createPathProducer (requestId:RequestId) (accessPath:PropertyAccessPath)
                       (namingConvention:NamingConvention option) =
    {
        ResponseProducer.id = ApiResource(requestId,
                                           // The producer is a body resource, since it comes from the
                                           // response path.
                                           BodyResource { name = accessPath.Name
                                                          fullPath = accessPath.Path
                                                          },
                                           namingConvention, PrimitiveType.String)
    }

/// Input: the requests in the RESTler grammar, without dependencies, the dictionary, and any available annotations or examples.
/// Returns: the producer-consumer dependencies, and a new dictionary, augmented if required after inferring dependencies.
let extractDependencies (requestData:(RequestId*RequestData)[])
                         (globalAnnotations:seq<ProducerConsumerAnnotation>)
                         (customDictionary:MutationsDictionary)
                         (queryDependencies:bool)
                         (bodyDependencies:bool)
                         (allowGetProducers:bool)
                         (dataFuzzing:bool)
                         (perResourceDictionaries:Map<string, string * MutationsDictionary>)
                         (namingConvention:NamingConvention option)
                         : Dictionary<string, List<ProducerConsumerDependency>> * MutationsDictionary =

    let getParameterConsumers requestId parameterKind (parameters:RequestParametersPayload) resolveDependencies =
        match parameters with
        | ParameterList parameterList when resolveDependencies ->
            parameterList
            |> Seq.map (fun p -> getParameterDependencies
                                                    parameterKind
                                                    globalAnnotations
                                                    requestData
                                                    requestId
                                                    p
                                                    namingConvention)

            |> Seq.concat
        | _ -> Seq.empty

    logTimingInfo "Getting consumers..."

    let pathConsumers =
        requestData
        |> Array.Parallel.map
            (fun (r, rd) -> r, getParameterConsumers r ParameterKind.Path rd.requestParameters.path true)

    let queryConsumers =
        requestData
        |> Array.Parallel.map
            (fun (r, rd) ->
                let c =
                    let queryParametersList =
                        if dataFuzzing then
                            // IMPORTANT: when data fuzzing, the schema must be used when analyzing
                            // producer-consumer dependencies, because this includes all of the
                            // possible parameters that may be passed in the query.
                            rd.requestParameters.query
                            |> Seq.filter (fun (x,y) -> x = ParameterPayloadSource.Schema)
                            |> Seq.map snd
                        else
                            // This list should only contain examples, or only the schema.
                            rd.requestParameters.query |> Seq.map snd
                    let allConsumers =
                        queryParametersList
                        |> Seq.map (fun queryParameters ->
                                        getParameterConsumers r ParameterKind.Query queryParameters queryDependencies)
                        |> Seq.concat
                    // There may be duplicate consumers since different payload examples may overlap in the properties they use.
                    allConsumers
                    |> Seq.distinctBy (fun c -> c.id.RequestId, c.id.ResourceName, c.id.AccessPathParts)
                r, c)

    let producers = Producers()
    let bodyConsumers =
        requestData
        |> Array.Parallel.map
            (fun (r, rd) ->
                let bodyParametersList =
                    if dataFuzzing then
                        // IMPORTANT: when data fuzzing, the schema must be used when analyzing
                        // producer-consumer dependencies, because this includes all of the
                        // possible parameters that may be passed in the body.
                        rd.requestParameters.body
                        |> Seq.filter (fun (x,y) -> x = ParameterPayloadSource.Schema)
                        |> Seq.map snd
                    else
                        rd.requestParameters.body |> Seq.map snd
                let allConsumers =
                    bodyParametersList
                    |> Seq.map (fun bodyParameters ->
                                    getParameterConsumers r ParameterKind.Body bodyParameters bodyDependencies)
                    |> Seq.concat
                // There may be duplicate consumers since different payload examples may overlap in the properties they use.
                let distinctConsumers =
                    allConsumers
                    |> Seq.distinctBy (fun c -> c.id.RequestId, c.id.ResourceName, c.id.AccessPathParts)

                // Special case: also create producers for select parameter properties.
                // These may have references from the same body that use the newly created resource

                let producerPropertyNames = ["name"]
                distinctConsumers
                |> Seq.cache
                |> Seq.iter (fun consumer ->
                                let resourceName = consumer.id.ResourceName

                                if producerPropertyNames |> List.contains resourceName &&
                                    // A 'same body' producer must have an identifying container in the body
                                    consumer.id.ContainerName.IsSome then
                                        let producer = createBodyProducer consumer.id
                                        producers.AddSamePayloadProducer(resourceName, producer)
                                )
                r, distinctConsumers)

    logTimingInfo "Getting producers..."

    requestData
    // Only include POST, PUT, PATCH, and GET requests.  Others are never producers.
    |> Array.filter (fun (r, _) -> [ OperationMethod.Post ; OperationMethod.Put; OperationMethod.Patch ;
                                     OperationMethod.Get ]
                                    |> List.contains r.method)
    |> Microsoft.FSharp.Collections.Array.Parallel.iter
            (fun (r, rd) ->
                match rd.responseProperties with
                | None -> ()
                | Some rp ->
                    let responseProducerAccessPaths = getProducer r rp
                    for ap in responseProducerAccessPaths do
                        let producer = createPathProducer r ap namingConvention
                        let resourceName = ap.Name
                        producers.AddResponseProducer(resourceName, producer))


    logTimingInfo "Done processing producers"

    logTimingInfo "Compute dependencies"
    let consumers = seq { yield pathConsumers
                          yield queryConsumers
                          yield bodyConsumers }
                    |> Array.concat

    let dependencies = Dictionary<string, List<ProducerConsumerDependency>>()

    let findDependencies (consumer:Consumer) =
        lock dependencies
                (fun () ->
                    let key = match consumer.id.AccessPath with
                                | None -> consumer.id.ResourceName
                                | Some resourcePath -> resourcePath

                    // If the exact same dependency already appears, do not add it.
                    // This covers the case where the same uuid suffix is referred to in
                    // multiple locations
                    match dependencies.TryGetValue(key) with
                    | false, _ -> None
                    | true, deps  ->
                        deps |> Seq.tryFind (fun dep ->
                                                    dep.consumer.id.RequestId = consumer.id.RequestId &&
                                                    dep.consumer.id.ResourceName = consumer.id.ResourceName &&
                                                    dep.consumer.id.AccessPath = consumer.id.AccessPath
                                                    && dep.producer.IsSome))

    let addDependency d =
        lock dependencies
                (fun () ->
                    let key = match d.consumer.id.AccessPath with
                                | None -> d.consumer.id.ResourceName
                                | Some resourcePath -> resourcePath

                    dependencies.TryAdd(key, List<ProducerConsumerDependency>()) |> ignore
                    // If the exact same dependency already appears, do not add it.
                    // This covers the case where the same uuid suffix is referred to in
                    // multiple locations
                    match dependencies.[key]
                            |> Seq.tryFind (fun dep ->
                                                    dep.consumer.id.RequestId = d.consumer.id.RequestId &&
                                                    dep.consumer.id.ResourceName = d.consumer.id.ResourceName &&
                                                    dep.consumer.id.AccessPath = d.consumer.id.AccessPath
                                                    && dep.producer.IsSome) with
                    | None ->
                        dependencies.[key].Add(d)
                    | Some found ->
                        if d.producer.IsSome && found.producer.Value <> d.producer.Value then
                            raise (Exception(sprintf "Multiple producers for the same consumer should not exist.  Consumer ID: %A %s %A, producers: %A (existing) <> %A (current)"
                                                        found.consumer.id.RequestId found.consumer.id.ResourceName found.consumer.id.AccessPath
                                                        found.producer d.producer))
                )

    /// Gets dependencies for this consumer.
    /// Returns an updated mutations dictionary
    let getDependenciesForConsumer (c:Consumer) : MutationsDictionary =
        let perResourceDict =
            match perResourceDictionaries |> Map.tryFind c.id.RequestId.endpoint with
            | None -> None
            | Some (_,d) -> Some d
        let newDict, p = findProducer producers c customDictionary allowGetProducers perResourceDict

        let dep = { consumer = c ; producer = p }
        addDependency dep
        newDict

    let newCustomPayloadUuidSuffix =
        let generatedSuffixes =
            consumers
            |> Array.Parallel.map
                (fun (requestId, requestConsumers) ->
                    // First, look for producers in a different payload
                    let requestConsumers = requestConsumers |> Seq.toArray
                    let newUuidSuffixes =
                        requestConsumers
                        |> Array.Parallel.map
                            (fun cx -> getDependenciesForConsumer cx)
                        |> Seq.map (fun newDict ->
                                        newDict.restler_custom_payload_uuid4_suffix.Value
                                        |> Map.toSeq
                                    )
                        |> Seq.concat

                    logTimingInfo (sprintf "Second pass dependencies for request %A" requestId)

                    // Then do a second pass for producers in the same payload.  Two passes are required because the
                    // same payload body producer's dependency needs to be known.
                    let newUuidSuffixes2 =
                        requestConsumers
                        |> Array.Parallel.map
                                (fun cx ->
                                        match findDependencies cx with
                                        | Some dep  -> Seq.empty
                                        | None ->
                                            let newDict, producer =
                                                getSameBodyInputProducer
                                                    cx
                                                    customDictionary
                                                    producers
                                            match producer with
                                            | None -> Seq.empty
                                            | Some (SameBodyPayload rp) ->
                                                // Special case: another dependency must be added: producer -> uuid suffix
                                                let dep = { consumer = cx ; producer = producer }

                                                // However, it is possible that the 'name' producer (now the consumer) consumes its
                                                // resource from another endpoint.  Then, that inferred dependency should
                                                // override this one produced by the 'same body payload' heuristic.  Do not
                                                // add the 'same body payload' dependencies in this case.
                                                let consumerResourceName = rp.id.ResourceName
                                                let prefixName = generateIdForCustomUuidSuffixPayload rp.id.ContainerName.Value consumerResourceName

                                                let suffixProducer =
                                                    DictionaryPayload (CustomPayloadType.UuidSuffix, PrimitiveType.String, prefixName, false)

                                                let suffixConsumer =
                                                    {
                                                        Consumer.id = ApiResource(rp.id.RequestId,
                                                                                  rp.id.ResourceReference,
                                                                                  rp.id.NamingConvention,
                                                                                  PrimitiveType.String)
                                                        Consumer.parameterKind = ParameterKind.Body
                                                        Consumer.annotation = None
                                                    }
                                                let suffixDep = { consumer = suffixConsumer ; producer = Some suffixProducer }

                                                // Only add these two dependencies if a *different* producer for the suffix dep does not
                                                // already exist.
                                                match findDependencies suffixConsumer with
                                                | None ->
                                                    addDependency dep
                                                    addDependency suffixDep
                                                    let newUuidSuffx =
                                                        if newDict.restler_custom_payload_uuid4_suffix.Value.ContainsKey(prefixName) then
                                                            Seq.empty
                                                        else
                                                            let prefixValue = generatePrefixForCustomUuidSuffixPayload prefixName
                                                            (prefixName, prefixValue) |> stn
                                                    newUuidSuffx
                                                | Some existingDep ->
                                                    match existingDep.producer with
                                                    | None ->
                                                        raise (Exception("Invalid case"))
                                                    | Some (DictionaryPayload _) ->
                                                        addDependency dep
                                                        Seq.empty
                                                    | Some _ -> Seq.empty

                                            | Some _ ->
                                                raise (Exception("Only same body producers are expected at this point"))
                                    )
                        |> Seq.concat

                    logTimingInfo (sprintf "Done dependencies for request %A" requestId)
                    (requestId, [newUuidSuffixes; newUuidSuffixes2] |> Seq.concat))

        [ generatedSuffixes |> Seq.map (snd) |> Seq.concat
          (customDictionary.restler_custom_payload_uuid4_suffix.Value |> Map.toSeq)
        ]
        |> Seq.concat
        // Merge the dictionaries with 'customDictionary'
        |> Seq.distinctBy (fst)  // only keep unique keys
        |> Map.ofSeq

    let newDictionary =
        { customDictionary with
                restler_custom_payload_uuid4_suffix =
                    Some newCustomPayloadUuidSuffix
        }

    logTimingInfo "Dependency analysis completed."

    dependencies,
    newDictionary


module DependencyLookup =
    let getConsumerPayload (dependencies:Dictionary<string, List<ProducerConsumerDependency>>)
                            (pathPayload:FuzzingPayload list option)
                            requestId
                            consumerResourceName
                            (consumerResourceAccessPath : AccessPath)
                            defaultPayload =
        if String.IsNullOrEmpty consumerResourceName then
            raise (UnsupportedType "Empty consumer name is not valid")

        // Find the producer
        let findProducer (dependencyList:List<ProducerConsumerDependency>) =
            let producers =
                dependencyList
                    // Note: in some cases, two dependencies will appear - one that was inserted
                    // analyzing same-body dependencies, and one that was computer as usual.
                    // Make sure there is only one producer.
                |> Seq.filter (fun dep ->
                                 dep.producer.IsSome &&
                                 dep.consumer.id.RequestId = requestId &&
                                 dep.consumer.id.ResourceName = consumerResourceName &&
                                 dep.consumer.id.AccessPathParts = consumerResourceAccessPath)
            if producers |> Seq.length > 1 then
                raise (Exception("Multiple producer-consumer dependencies detected for the same producer."))
            match producers |> Seq.tryHead with
            | None -> None
            | Some x -> x.producer
        let producer =
            match consumerResourceAccessPath.getJsonPointer() with
            | None ->
                if dependencies.ContainsKey(consumerResourceName) then
                    findProducer dependencies.[consumerResourceName]
                else None
            | Some resourceAccessPath ->
                if dependencies.ContainsKey(resourceAccessPath) then
                    findProducer dependencies.[resourceAccessPath]
                else None

        match producer with
        | None -> defaultPayload
        | Some (ResponseObject responseProducer) ->
            let variableName = generateDynamicObjectVariableName responseProducer.id.RequestId (Some responseProducer.id.AccessPathParts) "_"
            DynamicObject variableName
        | Some (DictionaryPayload (customPayload, primitiveType, resourceName, isObject)) ->
            Custom { payloadType = customPayload
                     primitiveType = primitiveType
                     payloadValue = resourceName
                     isObject = isObject }
        | Some (SameBodyPayload payloadPropertyProducer) ->
            // The producer is a property in the same input payload body.
            // The consumer should consist of a set of payload parts, creating the full URI (with resolved dependencies)
            // to that property.
            if pathPayload.IsNone then
                raise (ArgumentException(sprintf "Same body payload cannot be created without a path payload: %A" payloadPropertyProducer.id))

            // Construct the payload.  Use custom_payload_uuid_suffix with the container name as the resource name.
            // Exclude the name and re-assemble the remaining child path.
            let uriParts = payloadPropertyProducer.id.AccessPathParts.getPathPropertyNameParts()
                            // Skip the 'properties' container, which is typically not
                            // part of the URI.
                           |> Array.filter (fun x -> x <> "properties")

            let containerName = payloadPropertyProducer.id.ContainerName.Value

            let childPayloadExceptName =
                let payloadValue = sprintf "/%s/" (uriParts.[0..uriParts.Length-2] |> String.concat "/")
                FuzzingPayload.Constant (PrimitiveType.String, payloadValue)

            let namePrefix = generateIdForCustomUuidSuffixPayload containerName payloadPropertyProducer.id.ResourceName
            let namePayload = FuzzingPayload.Custom
                                    {
                                        payloadType = CustomPayloadType.UuidSuffix
                                        primitiveType = PrimitiveType.String
                                        payloadValue = namePrefix
                                        isObject = false
                                    }
            // Add the endpoint (path) payload, with resolved dependencies
            let pp = pathPayload.Value
                        |> List.map (fun x -> [ FuzzingPayload.Constant (PrimitiveType.String, "/")
                                                x ]
                                        )
                        |> List.concat
            FuzzingPayload.PayloadParts (pp @  [childPayloadExceptName] @ [namePayload] )

    let getDependencyPayload
            (dependencies:Dictionary<string, List<ProducerConsumerDependency>>)
            pathPayload requestId (requestParameter:(string * ParameterPayload)) (dictionary:MutationsDictionary) =

        // First, pre-compute producer-consumer relationships within the same body payload.
        // These then need to be passed through each property in order to substitute dynamic objects.

        let parameterPayload = snd requestParameter

        let visitLeaf (resourceAccessPath:string list) (p:LeafProperty) =
#if DEBUG
            if String.IsNullOrEmpty p.name then
                printfn "Warning: leaf property should always have a name unless it's an array element."
#endif
            Tree.LeafNode
                {
                    name = p.name
                    payload =
                        if String.IsNullOrEmpty p.name then
                            p.payload
                        else
                            let propertyAccessPath =
                                { path = PropertyAccessPaths.getLeafAccessPath resourceAccessPath p |> List.toArray }
                            getConsumerPayload dependencies pathPayload requestId p.name
                                               propertyAccessPath
                                               p.payload
                    isRequired = p.isRequired
                    isReadOnly = p.isReadOnly
                }

        let visitInner (resourceAccessPath:string list) (p:InnerProperty) innerProperties =
            let dependencyPayload =
                if String.IsNullOrEmpty p.name then
                    None
                else
                    let defaultPayload =
                        match p.payload with
                        | None -> Fuzzable (PrimitiveType.String, "")
                        | Some p -> p
                    let propertyAccessPath =
                        { path = PropertyAccessPaths.getInnerAccessPath resourceAccessPath p
                                 |> List.toArray }
                    let payload = getConsumerPayload dependencies pathPayload requestId p.name
                                                     propertyAccessPath
                                                     defaultPayload
                    if payload <> defaultPayload then
                        printfn "Found dependency or dictionary entry on inner property of query or body: %s" p.name
                        Some payload
                    else
                        None

            // Handle the special case that this payload is an array.
            match dependencyPayload, p.propertyType with
            | Some dp, NestedType.Array ->
                if innerProperties |> Seq.length <> 1 then
                    raise (UnsupportedType (sprintf "Inner properties of an array should always be one item, found %d"
                                                    (innerProperties |> Seq.length)))
                let arrayItem = innerProperties |> Seq.head

                let dependencyArrayItem =
                    Tree.LeafNode
                        {
                            name = ""
                            payload = dp
                            isRequired = p.isRequired
                            isReadOnly = p.isReadOnly
                        }
                Tree.InternalNode (p, stn dependencyArrayItem)
            | _ ->
                Tree.InternalNode ({ p with payload = dependencyPayload }, innerProperties)

        // First, check if the parameter itself has a dependency
        let (parameterName, properties) = requestParameter
        let defaultPayload = (Fuzzable (PrimitiveType.String, ""))
        let dependencyPayload = getConsumerPayload dependencies pathPayload requestId parameterName EmptyAccessPath defaultPayload

        let payloadWithDependencies =
            if dependencyPayload <> defaultPayload then
                Tree.LeafNode
                        { name = "" ; payload = dependencyPayload ; isRequired = true ; isReadOnly = false }
            else
                Tree.cataCtx visitLeaf visitInner PropertyAccessPaths.getInnerAccessPath [] properties

        // Update custom payload in dictionary by visiting the tree and adding one for every payload type 'custom'
        let addDictionaryEntries (customPayloads:Map<string, string>) (p:LeafProperty) =
            let rec getDictionaryEntry (entries:Map<string, string>) payload =
                match payload with
                | Custom cp ->
                    if entries.ContainsKey(cp.payloadValue) then
                        entries
                    else
                        let prefixValue = generatePrefixForCustomUuidSuffixPayload cp.payloadValue
                        entries.Add(cp.payloadValue, prefixValue)
                | PayloadParts payloadList ->
                    payloadList
                    |> List.fold (fun e payloadPart ->
                                    getDictionaryEntry e payloadPart
                                  ) entries
                | _ -> entries
            getDictionaryEntry customPayloads p.payload

        let idInnerVisitor (entries:Map<string, string>) (p:InnerProperty) =
            entries

        let newCustomPayloads = Tree.fold
                                    addDictionaryEntries
                                    idInnerVisitor
                                    dictionary.restler_custom_payload_uuid4_suffix.Value
                                    payloadWithDependencies
        let newDictionary =
            { dictionary with restler_custom_payload_uuid4_suffix = Some newCustomPayloads }
        (parameterName, payloadWithDependencies), newDictionary

/// Serialize dependencies with all of the information available
/// This is primarily used for debugging
type SerializedProducerConsumerDependencies =
     Map<string, Map<string, ApiResourceTypes.ProducerConsumerDependency list>>

/// The dependencies file contains a brief summary of all parameters and
/// body properties for which a producer-consumer dependency was not inferred.  This
/// means that the input value for this property is either going to be from an enumeration
/// or a fuzzable value specified in the dictionary.
/// When parameters are present in this file, it does not necessarily mean
/// the API cannot be successfully executed (though, it is often the case for path
/// parameters).
/// The output format is intended to be easily transformed to an annotation that can be
/// specified in annotations.json to resolve the dependency.
/// Output format example:
/// {
///   "/api/doc" : {
///       "get": {
///               "path": [ <list of dependencies in annotation format> ],
///               "body": [ <list of dependencies in annotation format> ]
///         }
let writeDependencies dependenciesFilePath dependencies (unresolvedOnly:bool) =
    let dependencies =
        if unresolvedOnly then
            dependencies
            |> Seq.filter (fun d -> d.producer.IsNone)
        else dependencies

    let getMethod (id:ApiResource) =
        id.RequestId.method.ToString().ToUpper()

    let getParameter (id:ApiResource) =
        match id.ResourceReference with
        | PathResource p ->
            p.name
        | QueryResource q ->
            q
        | BodyResource b ->
            b.fullPath.getJsonPointer().Value

    let serializedDependencies =
        dependencies
        |> Seq.map (fun d ->
                        let consumer = d.consumer
                        let consumerParameter = getParameter consumer.id

                        let pe, pm, pr =
                            match d.producer with
                            | Some (ResponseObject rp) ->
                                rp.id.RequestId.endpoint,
                                getMethod rp.id,
                                getParameter rp.id
                            | Some (DictionaryPayload (payloadType, primitivePayloadType, payloadName, _)) ->
                                let customPayloadDesc =
                                    match payloadType with
                                    | CustomPayloadType.String -> ""
                                    | CustomPayloadType.UuidSuffix -> "_uuid_suffix"
                                    | CustomPayloadType.Header -> "_header"
                                "",
                                "",
                                sprintf "restler_custom_payload%s__%s" customPayloadDesc payloadName
                            | Some (SameBodyPayload rp) ->
                                // TODO: document the fact that annotations
                                // to the same body payload are not currently implemented.
                                // It's fine to still print this for debugging.
                                rp.id.RequestId.endpoint,
                                getMethod rp.id,
                                getParameter rp.id
                            | None -> "", "", ""

                        let annotation =
                            {
                                producer_endpoint =   pe
                                producer_method = pm
                                producer_resource_name = pr
                                consumer_param = consumerParameter
                                except = None
                            }
                        {|
                            endpoint = consumer.id.RequestId.endpoint
                            method = getMethod consumer.id
                            annotation = annotation
                            parameterKind = consumer.parameterKind
                        |}
                       )
    let grouped =
        let groupedByEndpoint =
            serializedDependencies
            |> Seq.groupBy (fun d -> d.endpoint)
        groupedByEndpoint
        |> Seq.map (fun (endpoint, endpointDeps) ->
                        endpoint,
                        endpointDeps
                        |> Seq.groupBy (fun d -> d.method)
                        |> Seq.map (fun (method, methodDeps) ->
                                        method,
                                        methodDeps
                                        |> Seq.groupBy (fun d -> d.parameterKind)
                                        |> Seq.map (fun (parameterKind, parameterKindDeps) ->
                                                        parameterKind,
                                                        parameterKindDeps
                                                        |> Seq.map (fun d -> d.annotation)
                                                        |> Seq.sortBy(fun a -> a.consumer_param))
                                        |> Map.ofSeq
                                    )
                         |> Map.ofSeq
                   )
        |> Map.ofSeq

    Microsoft.FSharpLu.Json.Compact.serializeToFile dependenciesFilePath grouped

let writeDependenciesDebug dependenciesFilePath dependencies =

    Microsoft.FSharpLu.Json.Compact.serializeToFile dependenciesFilePath dependencies
    // The below statement is present as an assertion, to check for deserialization issues for
    // specific grammars.
    Microsoft.FSharpLu.Json.Compact.deserializeFile<ProducerConsumerDependency list> dependenciesFilePath
    |> ignore
