// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.ResultsAnalyzer.OverviewDiff

open System

open Restler.ResultsAnalyzer.Overview

open Restler.ResultsAnalyzer.Common.Utilities
open Restler.ResultsAnalyzer.Common.Http
open Restler.ResultsAnalyzer.Common.Abstractions

type OverviewDiffArgs = {
    /// Path to two raw, textual network logs.
    logFiles: string * string
    /// Abstractions to apply before diffing the two logs.
    abstractionOptions: AbstractionOptions
}

module OverviewDiffArgs =
    let initWithDefaults logFiles = {
        logFiles = logFiles
        abstractionOptions = AbstractionOptions.None
    }

let main args =
    let requestMapA, requestMapB =
        args.logFiles
        |> Pair.map (Overview.requestMap args.abstractionOptions)
        ||> Pair.zip
        |> fst
    // Since order doesn't matter for the second log (the order of the output is determined by the first/"old" log),
    // build map (= balanced tree) from the second log, so lookup of a request signature is O(log n) instead of O(n) search.
    let requestMapB = requestMapB |> Map.ofSeq

    // Iterate over all request signatures in log A and output a difference if
    // (1) the request signature does not exist at all in log B, or
    // (2) the signature exists, but the full requests (hashes) are different in log B, or
    // (3) the signature and full requests exist, but the response codes are different in log B.
    for requestSignatureA, requestsA in requestMapA do
        let requestsB =
            requestMapB
            |> Map.tryFind requestSignatureA
            // requestMap is essentially a MultiMap, so isPresent(key) iff not(empty(value))
            |> Option.defaultValue Seq.empty
            |> Seq.map (fun (request, _count, responses) -> request, responses)
            // Again, order for log B doesn't matter, but lookup should be quick -> make map, not seq.
            |> Map.ofSeq

        if Map.isEmpty requestsB
        then
            // Mark missing elements by preceding '-' as in textual diffs (VS Code will highlight those lines automatically in .diff files).
            printfn "-%O" requestSignatureA
        else
            // Collect all differences under this request signature first and only print the signature if there were any differences at all.
            let requestDiffLines = new System.IO.StringWriter()

            for requestA, _count, responsesA in requestsA do
                let hash = Request.hash requestA

                let responsesB =
                    requestsB
                    |> Map.tryFind requestA
                    |> Option.defaultValue Seq.empty
                    |> Seq.map fst
                    |> Set.ofSeq

                if Set.isEmpty responsesB
                then
                    // The whole request is missing with all its responses.
                    fprintfn requestDiffLines "-  Requests with hash=%s" hash
                    for response in responsesA |> Seq.map fst do
                        fprintfn requestDiffLines "-    %s" (ResponseSignature.toString response)
                else
                    let missingResponses =
                        responsesA
                        |> Seq.map fst
                        // We aren't missing any responses that were "bad" in the first place
                        |> Seq.where (fun response ->
                            match response with
                            | None -> false
                            | Some response -> response.statusCode < 400)
                        |> Seq.where (fun response -> responsesB |> Set.contains response |> not)

                    // TODO Should we also list "bad" responses that were added, e.g., 400/409/500 etc.?

                    if not (Seq.isEmpty missingResponses) then
                        // The request itself hasn't changed, but the responses to it have. Print the request hash anyhow for context.
                        fprintfn requestDiffLines "   Requests with hash=%s" hash
                        for response in missingResponses do
                            fprintfn requestDiffLines "-    %s" (ResponseSignature.toString response)

                        // Also print _added_ response codes for this request (for context, often helps to quickly identify the issue).
                        let addedResponses =
                            responsesA
                            |> Seq.map fst
                            |> Set.ofSeq
                            |> Set.difference responsesB
                            |> Set.toSeq
                            |> Seq.sort
                        for response in addedResponses do
                            fprintfn requestDiffLines "+    %s" (ResponseSignature.toString response)

            let requestDiffLines = requestDiffLines.ToString()
            if not (String.IsNullOrEmpty requestDiffLines) then
                printfn " %O" requestSignatureA
                printf "%s" requestDiffLines

                // If any request or any response for a particular request was removed,
                // also print all _added_ requests and their response codes (for context, often helps in debugging).
                let addedRequests =
                    requestsA
                    |> Seq.map (fun (req, _count, _resp) -> req)
                    |> Seq.fold (fun map req -> Map.remove req map) requestsB
                    |> Map.toSeq
                    |> Seq.sortBy fst
                for request, responses in addedRequests do
                    printfn "+  Requests with hash=%s" (Request.hash request)
                    for response in responses |> Seq.map fst do
                        printfn "+    %s" (ResponseSignature.toString response)
