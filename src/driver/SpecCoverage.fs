// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.Driver.SpecCoverage
open System
open System.Collections.Generic
open Newtonsoft.Json.Linq
open Restler.Grammar

/// The text of the sent API request and received service response
type RequestResponseText =
    {
        request : string
        response : string option
    }

/// If a request is invalid (not covered), the reason for the failure
[<Flags>]
type RequestFailureInformation =
    /// The request was not executed, because an earlier dependency failed
    | SequenceFailure
    /// An external failure, such as a connection failure
    | ResourceFailure
    /// An earlier request succeeded, but dependency data could not be parsed from the response
    | ParserFailure
    /// The request or a dependency returned a 500
    | ErrorCode500Range

type RenderingId = string

type PrefixRendering =
    {
        /// The rendering ID
        /// This is a combination of the request ID and the combination number of
        /// the request sequence executed to test this request
        id : string

        /// Whether the request succeeded
        /// When part of the sequence prefix, 'None' indicates the request was not executed
        valid : bool option
    }

type RequestCoverageData =
    {
        /// The rendered request ID, which includes a request hash and the sequence combination ID
        renderingId : RenderingId

        /// The request endpoint and method
        requestId : RequestId

        /// Indicates whether the request succeeded
        valid : bool

        /// 'None' if the request was not rendered
        requestResponseText : RequestResponseText option

        /// The list of rendering ID requests executed to satisfy dependencies for this request
        matchingPrefix: PrefixRendering list

        requestFailureInformation: RequestFailureInformation option
    }

let parseSpecCovMin filePath : RequestCoverageData list =
    // Parse the data as json and extract the necessary fields
    let specCovData = JObject.Parse(System.IO.File.ReadAllText(filePath));
    specCovData.Properties()
    |> Seq.map (fun rcd ->
        let data = rcd.Value.Value<JObject>()
        let valid =
            match Restler.Utilities.JsonParse.getProperty data "valid" with
            | None -> failwith "Invalid coverage file, 'valid' not found"
            | Some x -> if x.Value<int>() = 0 then false else true

        let endpoint =
            match Restler.Utilities.JsonParse.getProperty data "endpoint" with
            | None -> failwith "Invalid coverage file, 'endpoint' not found"
            | Some x -> x.Value<string>()

        let method =
            match Restler.Utilities.JsonParse.getProperty data "verb" with
            | None -> failwith "Invalid coverage file, 'verb' not found"
            | Some x -> getOperationMethodFromString (x.Value<string>())

        let requestResponse =
            let requestText =
                Restler.Utilities.JsonParse.getPropertyAsString data "request"
            let responseText =
                Restler.Utilities.JsonParse.getPropertyAsString data "response"

            match requestText, responseText with
            | Some req, Some resp ->
                if isNull req then
                    None
                else
                    Some { request = req ; response = if isNull resp then None else Some resp }
            | _ -> None

        let matchingPrefix =
            match Restler.Utilities.JsonParse.getProperty data "matching_prefix" with
            | None -> failwith "Invalid coverage file, 'matching_prefix' not found"
            | Some prefix ->
                // {{
                //  "id": "4fc287fccdb64d22a7d070386dacdde9207540d0_1",
                //  "valid": 1
                //}}

                let renderingInfoList =
                        prefix.Children()
                        |> Seq.map (fun elem ->
                                    let valid = if elem.Value<JObject>().ContainsKey("valid") then
                                                    elem.["valid"].Value<bool>() |> Some
                                                else None
                                    {
                                        PrefixRendering.id = elem.["id"].Value<string>()
                                        PrefixRendering.valid = valid
                                    }
                        )
                        |> Seq.toList
                renderingInfoList

        let requestRenderingCoverageData =
            {
                RequestCoverageData.renderingId = rcd.Name
                requestId = { endpoint = endpoint; method = method ; xMsPath = None }
                valid = valid
                requestResponseText = requestResponse
                matchingPrefix = matchingPrefix
                requestFailureInformation = None
            }
        requestRenderingCoverageData
    )
    |> Seq.toList

let getSkippedRequests (reqCoverageData:RequestCoverageData list) =
    reqCoverageData
    |> Seq.filter (fun reqCov ->
                        reqCov.requestResponseText.IsNone)

let getSuccessfulRequests (reqCoverageData:RequestCoverageData list) =
    reqCoverageData
    |> Seq.filter (fun reqCov -> reqCov.requestResponseText.IsSome)
    |> Seq.groupBy(fun reqCov -> reqCov.requestId)
    |> Seq.filter (fun (requestId, combinations) ->
                    combinations |> Seq.exists (fun c -> c.valid)
    )
    |> Seq.map fst

/// Failed requests are attempted requests where every combination was invalid
let getFailedRequests (reqCoverageData:RequestCoverageData list) =
    reqCoverageData
    |> Seq.filter (fun reqCov -> reqCov.requestResponseText.IsSome)
    |> Seq.groupBy(fun reqCov -> reqCov.requestId)
    |> Seq.filter (fun (requestId, combinations) ->
                    combinations |> Seq.filter (fun c -> c.valid) |> Seq.isEmpty
    )
    |> Seq.map fst

/// Given a matching prefix list of the form
/// <requestHash1_combinationId1>, <requestHash2_combinationId2>, ...
/// Returns the matching prefix that will match the combination keys for the request renderings
/// <requestHash1_combinationId1>, <requestHash2_combinationId2__combinationId1>, ...
let getMatchingPrefixWithSequenceCombinationIds matchingPrefix =
    let prefixCombinations =
        matchingPrefix
        |> List.map (fun prefixRenderingId -> prefixRenderingId.id.Split("_").[1])

    let matchingPrefixWithSequenceCombinationId =
        matchingPrefix
        |> Seq.mapi (fun idx prefixRendering ->
                        let prefixStr = prefixCombinations |> Seq.take idx |> String.concat ""
                        if idx > 0 then
                            { prefixRendering with id = sprintf "%s__%s" prefixRendering.id prefixStr }
                        else
                            prefixRendering
        )
    matchingPrefixWithSequenceCombinationId

/// This function generates the rendering ID of the first rendering given a rendering ID
let getFirstRenderingId renderingId =
    let requestHash = renderingId.id.Split("_").[0]
    let firstRendering = sprintf "%s_%d" requestHash 1
    let prefixRendering =
        let split = renderingId.id.Split("__")
        if split.Length > 1 then
            split.[1]
        else
            ""
    sprintf "%s%s" firstRendering prefixRendering

let tryGetReqCoverageData renderingId (renderingToReqCovMap:Map<RenderingId, RequestCoverageData>) =
    match renderingToReqCovMap |> Map.tryFind renderingId.id with
    | Some prefixRendering ->
        Some prefixRendering
    | None ->
        // Sometimes, the rendering ID is not present in the coverage file.
        // Fix up the value to get the first rendering, which should always be present.
        let firstRenderingId = getFirstRenderingId renderingId
        match renderingToReqCovMap |> Map.tryFind firstRenderingId with
        | Some prefixRendering ->
            Some prefixRendering
        | None -> None

/// Find each request that is invalid due to a sequence failure, and return a map of
/// the requests to their source of failure.
/// A sequence failure can be identified by a request that was not attempted, for which
/// a pre-requisite request is invalid in the prefix but that same request is valid
/// Returns a map of requests to the number of sequence failures they caused
let getSequenceFailureSources (renderingToReqCovMap:Map<RenderingId, RequestCoverageData>)
                              (validRequests:seq<RequestId>) =
    let seqFailures =
        renderingToReqCovMap
        |> Map.toSeq
        |> Seq.fold (fun result (_,rcd) ->
            let validRequestFailedInPrefix =
                getMatchingPrefixWithSequenceCombinationIds rcd.matchingPrefix
                |> Seq.choose(fun prefixRenderingId ->
                    let requestId =
                        match tryGetReqCoverageData prefixRenderingId renderingToReqCovMap with
                        | Some prefixCoverageData ->
                            Some prefixCoverageData.requestId
                        | None ->
                            // Raise an error if this is not found in the speccov file!
                            printfn "ERROR: prefix rendering ID %s for request '%s %s' not found in spec coverage file."
                                        prefixRenderingId.id rcd.requestId.endpoint (rcd.requestId.method.ToString())
                            None
                    match requestId, prefixRenderingId.valid with
                    | Some reqId, Some valid ->
                        if not valid && validRequests |> Seq.contains reqId then
                            Some reqId
                        else None
                    | _,_ -> None
                )
                |> Seq.tryHead
            match validRequestFailedInPrefix with
            | None -> result
            | Some req -> (req,rcd.requestId)::result
        ) []
        |> Seq.distinct
        |> Seq.map (fun (prefixRequestId, failureRequestId) -> prefixRequestId)
        |> Seq.countBy (fun requestId -> requestId)

    seqFailures

/// Gets the requests sorted by the number of child dependencies
let getRequestsSortedByNumberOfConsumers (renderingToReqCovMap:Map<RenderingId, RequestCoverageData>) =
    // Compute the map of request ID to number of requests it is blocking if invalid
    // For example, for a resource hierarchy /A/B/C, if 'A' cannot be created, the map
    // will contain {'A': 2, 'B': 1, 'C': 0} - failure to create 'A' will block
    // creation of 'B' and 'C'
    let requestConsumerCounts =
        renderingToReqCovMap
        |> Map.toSeq
        |> Seq.fold (fun result (_,rcd) ->
            let reqs =
                getMatchingPrefixWithSequenceCombinationIds rcd.matchingPrefix
                |> Seq.choose (fun prefixRenderingId ->
                                    match renderingToReqCovMap |> Map.tryFind prefixRenderingId.id with
                                    | Some prefixRendering ->
                                            Some (rcd.requestId, prefixRendering.requestId)
                                    | None ->
                                        // Sometimes, the rendering ID is not present in the coverage file.
                                        // Fix up the value to get the first rendering, which should always be present.
                                        let firstRenderingId = getFirstRenderingId prefixRenderingId
                                        match renderingToReqCovMap |> Map.tryFind firstRenderingId with
                                        | Some prefixRendering ->
                                                Some (rcd.requestId, prefixRendering.requestId)
                                        | None ->
                                            printfn "ERROR: prefix rendering ID %s for request '%s %s' not found in spec coverage file."
                                                    prefixRenderingId.id rcd.requestId.endpoint (rcd.requestId.method.ToString())
                                            None
                )
            // Include the request ID, so every request is counted at least once
            [reqs ; result ; [rcd.requestId, rcd.requestId] ] |> Seq.concat
        ) []
        |> Seq.distinct
        |> Seq.groupBy (fun (requestId, prefixRequestId) -> prefixRequestId)
        |> Seq.map (fun (prefixRequestId, b) -> prefixRequestId, (b |> Seq.length) - 1)

    requestConsumerCounts

type Combination =
    {
        rendering : PrefixRendering
        requestId : RequestId option
        requestHash : string option
        requestResponseText : RequestResponseText option
        failureInfo : RequestFailureInformation option
    }

type FailedRequestWithSequence =
    {
        /// The request Id
        requestId : RequestId

        /// The number of times the request failed
        failureCount : int

        /// The number of requests that this request is a producer for
        /// i.e. the number of requests that cannot be tested if this request
        /// cannot be tested
        dependentRequestCount : int

        /// 'True' if this request failed sporadically
        isSequenceFailure : bool

        /// The requests that could not be tested
        /// because this request failed
        failedRequests : RequestId list

        /// The request combination and prefix sequence
        /// for the rendered combinations for this request
        combinations : (string * RequestResponseText option * seq<Combination>) list
    }

let getRequestSequence (reqCoverageData:RequestCoverageData list)
                       (renderingToReqCovMap:Map<RenderingId, RequestCoverageData>)
                       (renderedCombination:RequestCoverageData) =

    let getRequestResponseText (reqData:RequestCoverageData) =
        let getEscapedString (str:string) =
            let escapeChars = [("\n", "\\n"); ("\r", "\\r"); ("\t", "\\t") ]
            escapeChars
            |> List.fold(fun (state:string) (a,b) ->
                            state.Replace(a,b)) str

        match reqData.requestResponseText with
            | None -> None
            | Some requestResponseText ->
                {
                    request = getEscapedString requestResponseText.request
                    response = match requestResponseText.response with
                               | None -> None
                               | Some r -> Some (getEscapedString r)
                }
                |> Some

    // This request should always be rendered, so there will always
    // be a rendering ID separated by underscores
    let reqCombination = renderedCombination.renderingId.Split("_").[1]
    // Get the requests from the matching prefix.
    let matchingPrefixRequests =
        reqCoverageData
        |> Seq.filter (fun rcd -> rcd.matchingPrefix
                                    |> List.exists (fun ri -> ri.id = rcd.renderingId))
    let matchingPrefixWithSequenceCombinationId =
        getMatchingPrefixWithSequenceCombinationIds renderedCombination.matchingPrefix

    reqCombination,
    getRequestResponseText renderedCombination,
    matchingPrefixWithSequenceCombinationId
    |> Seq.map (fun prefixRendering ->
        // Find the request and print out the req/response
        //
        match tryGetReqCoverageData prefixRendering renderingToReqCovMap with
        | None ->
            let prefixReqHash = renderedCombination.renderingId.Split("_").[0]
            let firstCombination = sprintf "%s_%d" prefixReqHash 1
            match renderingToReqCovMap |> Map.tryFind firstCombination with
            | Some rcd ->
                {
                    rendering = prefixRendering
                    requestId = Some rcd.requestId
                    requestHash = None
                    requestResponseText = None
                    failureInfo = rcd.requestFailureInformation
                }
            | None ->
                {
                    rendering = prefixRendering
                    requestId = None
                    requestHash = Some prefixReqHash
                    requestResponseText = None
                    failureInfo = None
                }
        | Some rcd ->
            let requestResponseText = getRequestResponseText rcd
            {
                rendering = prefixRendering
                requestId = Some rcd.requestId
                requestHash = None
                requestResponseText = requestResponseText
                failureInfo = rcd.requestFailureInformation
            }
    )

/// Extract a prioritized list of failed requests that should be investigated to improve API coverage.
let getFailedRequestSequences (reqCoverageData:RequestCoverageData list) =
    // Get all of the failing request IDs
    // For each request ID, print all of the combinations (order should be the same as in the
    // list, which was the original order of execution)
    let reqCoverageByRequest = reqCoverageData |> Seq.groupBy(fun x -> x.requestId) |> Map.ofSeq

    let renderingToReqCovMap =
        reqCoverageData |> Seq.map (fun rcd -> rcd.renderingId, rcd) |> Map.ofSeq

    // Filter out skipped requests
    let requestConsumerCounts =
        getRequestsSortedByNumberOfConsumers renderingToReqCovMap
        |> Map.ofSeq

    let failedRequests =
        getFailedRequests reqCoverageData

    let successfulRequests =
        getSuccessfulRequests reqCoverageData

    let sequenceFailureSources =
        getSequenceFailureSources renderingToReqCovMap successfulRequests

    // Count all of the occurrences in the matching prefix and sort in descending order.
    // This identifies the requests that will block most other requests.
    let failedRequests = failedRequests
                            |> Seq.map (fun requestId -> requestId, requestConsumerCounts.[requestId], false)

    let sequenceFailures = sequenceFailureSources
                            |> Seq.map (fun (requestId, count) -> (requestId, count, true))

    let allFailures =
        [ failedRequests ; sequenceFailures ] |> Seq.concat |> Seq.sortByDescending (fun (_, count,_) -> count)

    allFailures
    |> Seq.map (fun (requestId,failureCount,isSequenceFailure) ->
                    let combinations =
                        reqCoverageByRequest.[requestId]
                        |> Seq.truncate 5 // only report data for the first 5 combinations
                        |> Seq.map (getRequestSequence reqCoverageData renderingToReqCovMap)
                        |> Seq.toList
                    {
                        FailedRequestWithSequence.requestId = requestId
                        isSequenceFailure = isSequenceFailure
                        failureCount = failureCount
                        failedRequests = []
                        dependentRequestCount = requestConsumerCounts.[requestId]
                        combinations = combinations
                    }
                )

let printFailedRequestSequences (failedRequests:seq<FailedRequestWithSequence>) (writer : System.IO.TextWriter) =

    let writeLogLine format =
        writer.WriteLine()
        fprintf writer format

    let printRequestResponseText (r:RequestResponseText) =
        writeLogLine "\t> %s" r.request
        writeLogLine "\t< %s" (if r.response.IsNone then "" else r.response.Value)

    writer.WriteLine("This file contains the failing requests, ordered by the number of blocked dependent requests.")
    writer.WriteLine("To improve coverage, fix the failing requests in the order listed in this file.")
    writer.WriteLine("""
Note: some requests are labeled as 'sequence failure'.
This means the request depends on another request that is failing intermittently.
For example, a DELETE request for a resource may be skipped because the resource
PUT request failed due to exceeding quota.  The same PUT request succeeded earlier (and may
succeed later depending on the resource clean-up behavior in the service), so it is
considered an intermittent failure.""")
    for failedRequest in failedRequests do
        writeLogLine "-----------------------------------------------"
        writeLogLine "Request: %s %s" (failedRequest.requestId.method.ToString()) failedRequest.requestId.endpoint

        if failedRequest.isSequenceFailure then
            writeLogLine "This request failed sporadically %d times after succeeding." failedRequest.failureCount
            writeLogLine "Number of dependent requests: %d" failedRequest.dependentRequestCount
        else
            writeLogLine "Number of blocked dependent requests: %d" failedRequest.failureCount

        // TODO: it would be useful to also record and output here if this is an example payload or not
        for (reqCombination, reqRenderingText, prefixCombination) in failedRequest.combinations do

            writeLogLine "\n\t+++ Combination %s +++:" reqCombination
            writeLogLine "\tRequest sequence: "

            for req in prefixCombination do
                match req.requestResponseText with
                | Some r ->
                    printRequestResponseText r
                    writeLogLine ""
                | None ->
                    match req.requestId, req.requestHash with
                    | Some requestId,_ ->
                        // In some cases, the rendering ID is not in the report.
                        // This is the case for a prefix request that is invalid because all combinations
                        // have been exhausted
                        writeLogLine "\tAll request combinations failed for request %s %s"
                                        (requestId.method.ToString()) requestId.endpoint
                    | _, Some requestHash ->
                        writeLogLine "\tAll request combinations failed for request hash %s" requestHash
                    | _ ->
                        failwith "ERROR: no request hash or ID for prefix combination"

            // Print the last request
            if reqRenderingText.IsSome then
                printRequestResponseText reqRenderingText.Value
            else
                writeLogLine "\tNo request text sent or response received."
            writeLogLine ""

        writeLogLine ""
    writeLogLine ""

