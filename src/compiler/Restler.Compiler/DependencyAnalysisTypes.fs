﻿// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/// Types used the compiler implementation.
/// These should not appear in the grammar.
module Restler.DependencyAnalysisTypes

open System.Collections.Generic
open Restler.Examples
open Restler.Grammar
open Restler.ApiResourceTypes

/// Data gathered from Swagger and user parameters to create the fuzzing grammar.
type RequestData =
    {
        requestParameters : RequestParameters
        localAnnotations : seq<ProducerConsumerAnnotation>
        responseProperties : ResponseProperties option
        responseHeaders : (string * ResponseProperties) list
        requestMetadata : RequestMetadata
        exampleConfig : ExampleRequestPayload list option
    }

// When choosing among several producers, the order in which they should be
// chosen according to the method.
let sortByMethod (resource:ApiResource) =
    match resource.RequestId.method with
    | OperationMethod.Get -> 4
    | OperationMethod.Patch -> 3
    | OperationMethod.Put -> 2
    | OperationMethod.Post -> 1
    | _ -> 5

// When choosing among several producers, the order in which
// they should be chosen.
let inferredMatchSortUniqueSortIndex = ref 0
let inferredMatchSort (resource:ApiResource) =

    let getProducersSortId =
        if resource.RequestId.method = OperationMethod.Get then
            // When choosing a GET producer, pick the one with a path parameter
            // at the end.  This attempts to avoid GET requests that always succeed,
            // but may return an empty list of results.
            if resource.RequestId.endpoint.EndsWith("}") then 2
            else 3
        else 1
    sortByMethod resource,
    getProducersSortId,
    (match resource.AccessPath with
     | None -> 0
     | Some ap -> ap.Length),
    (System.Threading.Interlocked.Increment(inferredMatchSortUniqueSortIndex)) // For tuple uniqueness

type private ProducersSortedByMatch = SortedList<int * int * int * int, ResponseProducer>

type private ResponseProducersIndexedByEndpoint = Dictionary<RequestId, List<ResponseProducer>>
type private BodyPayloadInputProducersIndexedByEndpoint = Dictionary<RequestId, List<BodyPayloadInputProducer>>

type private ProducersIndexedByTypeName = Dictionary<string, List<ResponseProducer>>

type private ProducerIndexes =
    {
        sortedByMatch : ProducersSortedByMatch
        sortedByMatchNonNested : ProducersSortedByMatch
        indexedByEndpoint : ResponseProducersIndexedByEndpoint
        samePayloadProducers : BodyPayloadInputProducersIndexedByEndpoint
        indexedByTypeName : ProducersIndexedByTypeName
        inputOnlyProducers : List<InputOnlyProducer>
    }

type Producers() =

    let producers = Dictionary<string, ProducerIndexes>()

    let tryAdd resourceName =
        producers.TryAdd(resourceName, { sortedByMatch = ProducersSortedByMatch()
                                         sortedByMatchNonNested = ProducersSortedByMatch()
                                         indexedByEndpoint = ResponseProducersIndexedByEndpoint()
                                         samePayloadProducers = BodyPayloadInputProducersIndexedByEndpoint()
                                         indexedByTypeName = ProducersIndexedByTypeName()
                                         inputOnlyProducers = List<InputOnlyProducer>()
                                       }) |> ignore
        producers.[resourceName]

    let tryGet resourceName =
        match producers.TryGetValue(resourceName) with
        | false, _ -> None
        | true, p -> Some p

    member x.AddResponseProducer(resourceName:string, producer:ResponseProducer) =
        lock producers (fun () ->
                            let resourceProducers = tryAdd resourceName
                            let sortKey = inferredMatchSort producer.id
                            resourceProducers.sortedByMatch.Add(sortKey , producer)
                            if not producer.id.IsNestedBodyResource then
                                resourceProducers.sortedByMatchNonNested.Add(sortKey, producer)
                            let key = { endpoint = producer.id.RequestId.endpoint.ToLower()
                                        method = producer.id.RequestId.method
                                        xMsPath = None }
                            resourceProducers.indexedByEndpoint.TryAdd(key, new List<ResponseProducer>()) |> ignore
                            resourceProducers.indexedByEndpoint.[key].Add(producer)

                            producer.id.CandidateTypeNames
                            |> List.iter (fun tn ->
                                            resourceProducers.indexedByTypeName.TryAdd(tn, new List<ResponseProducer>()) |> ignore
                                            resourceProducers.indexedByTypeName.[tn].Add(producer)
                                          )
                        )

    member x.AddSamePayloadProducer(resourceName:string, producer:BodyPayloadInputProducer) =
        lock producers (fun () ->
                            let key = { endpoint = producer.id.RequestId.endpoint.ToLower()
                                        method = producer.id.RequestId.method
                                        xMsPath = None }
                            let resourceProducers = tryAdd resourceName
                            resourceProducers.samePayloadProducers.TryAdd(key, new List<BodyPayloadInputProducer>()) |> ignore
                            resourceProducers.samePayloadProducers.[key].Add(producer))

    member x.getSamePayloadProducers(producerResourceName:string, requestId:RequestId) =
        match tryGet producerResourceName with
        | None -> Seq.empty
        | Some p ->
            let key = { endpoint = requestId.endpoint.ToLower()
                        method = requestId.method
                        xMsPath = None }
            match p.samePayloadProducers.TryGetValue(key) with
            | false, _ -> Seq.empty
            | true, lst ->
                lst |> seq

    member x.addInputOnlyProducer(resourceName:string, producer:InputOnlyProducer) =
        lock producers (fun () ->
                            let resourceProducers = tryAdd resourceName
                            let key = { endpoint = producer.id.RequestId.endpoint.ToLower()
                                        method = producer.id.RequestId.method
                                        xMsPath = None }

                            resourceProducers.inputOnlyProducers.Add(producer))

    member x.getInputOnlyProducers(producerResourceName:string) =
        match tryGet producerResourceName with
        | None -> Seq.empty
        | Some p ->
            p.inputOnlyProducers |> seq

    member x.getIndexedByEndpointProducers(producerResourceName:string, endpoint:string, operations:OperationMethod list) =
        match tryGet producerResourceName with
        | None -> Seq.empty
        | Some p ->
            let endpointLookup = endpoint.ToLower()
            seq {
                for m in operations do
                    match p.indexedByEndpoint.TryGetValue({ endpoint = endpointLookup ; method = m; xMsPath = None}) with
                    | false, _ -> ()
                    | true, p -> yield p |> seq
            }
            |> Seq.concat

    member x.getIndexedByTypeNameProducers(producerResourceName:string, typeName: string, includeNestedProducers:bool) =
        match tryGet producerResourceName with
        | None -> Seq.empty
        | Some p ->
            match p.indexedByTypeName.TryGetValue(typeName) with
            | false, _ -> Seq.empty
            | true, p -> p |> seq

    member x.getSortedByMatchProducers(producerResourceName:string, includeNestedProducers:bool) =
        match tryGet producerResourceName with
        | None -> Seq.empty
        | Some p ->
            if includeNestedProducers then
                p.sortedByMatch.Values |> seq
            else
                p.sortedByMatchNonNested.Values |> seq


type ProducerKind = 
| Input
| Response

/// Object IDs are currently names, but could be extended to
/// both the name and the type (as declared in the API spec) in the future.
type ResourceId =
    {
        requestId : RequestId
        resourceReference : ResourceReference
    }
