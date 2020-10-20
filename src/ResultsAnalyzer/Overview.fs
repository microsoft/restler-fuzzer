// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.ResultsAnalyzer.Overview

open System.IO

open Restler.ResultsAnalyzer.Common.Utilities
open Restler.ResultsAnalyzer.Common.Http
open Restler.ResultsAnalyzer.Common.Abstractions
open Restler.ResultsAnalyzer.Common.Log

/// "Signature" of a request for grouping, i.e., ignoring headers and body.
type RequestSignature =
    {
        /// HTTP method, e.g., GET, PUT, etc.
        method: string
        /// HTTP path, e.g., /some/parent/child/
        path: string
    }

    // Make ToString() convenient for printing signatures to console, by
    // 1. Left-aligning request method (HTTP verb).
    // 2. Escaping CR and LF in the path (can be there due to fuzzing), otherwise we get linebreaks in the output.
    override this.ToString() =
        sprintf "%-6s %s"
            this.method
            (this.path.Replace("\r","\\r").Replace("\n","\\n"))

module RequestSignature =
    let ofReq (req:Request<'T>) =
        {
            method = req.method
            path = req.uri.path |> String.concat "/"
        }

    // Custom ordering for RequestSignatures:

    // POST, PUT before the rest, because they are often used to create a resource and thus earlier in
    // RESTler "dependency order", which is useful for a quick first glance at overviews.
    let private HttpMethodOrder = [| "POST"; "PUT"; "GET"; "PATCH"; "DELETE" |]
    let private httpMethodIndex method = System.Array.IndexOf(HttpMethodOrder, method)

    let compare { method = methodA; path = pathA } { method = methodB; path = pathB } =
        // Order by paths first...
        let pathOrder = compare pathA pathB
        if pathOrder <> 0 then pathOrder
        else
            // ...then by custom method order (see above)...
            let knownMethodA = httpMethodIndex methodA
            let knownMethodB = httpMethodIndex methodB
            let customMethodOrder = compare knownMethodA knownMethodB
            if customMethodOrder <> 0 then customMethodOrder
            else
                // ...and only for unknown methods, fall back to string compare
                compare methodA methodB

/// "Signature" of a response for grouping, i.e., ignoring headers and body.
type ResponseSignature =
    {
        statusCode: int
        statusDescription: string
    }

    override this.ToString() = sprintf "%d %s" this.statusCode this.statusDescription

module ResponseSignature =
    let ofResp (resp:Response<'T>) =
        {
            statusCode = resp.statusCode
            statusDescription = resp.statusDescription
        }

    let toString (resp:ResponseSignature option) =
        resp
        |> Option.map (fun x -> x.ToString())
        |> Option.defaultValue "No response"


type OverviewArgs =
    {
        /// Path to raw, textual network log file.
        logFile: string
        /// Print counts in summary and overview.
        includeCounts: bool
        /// Print summary of overall requests/responses in the beginning.
        includeSummary: bool
        /// Directory, where to put text files that help finding hash -> request content.
        requestHashesDir: string option
        /// Abstractions to apply before grouping by signatures, hashes etc.
        abstractionOptions: AbstractionOptions
    }

module OverviewArgs =
    let initWithDefaults logFile =
        {
            logFile = logFile
            includeCounts = true
            includeSummary = true
            requestHashesDir = None
            abstractionOptions = AbstractionOptions.None
        }

let requestMap abstractionOptions logFile =
    let requestResponsePairs =
        logFile
        |> Log.parseFile
        |> Log.removeTimings
        // Flatten sequences of HTTP traffic into (stateless) pairs of (request, maybe response).
        |> Seq.concat
        // Apply abstractions
        |> Seq.map (RequestResponse.abstractAll abstractionOptions)
        // Simplify structure
        |> Seq.map (fun pair -> pair.request, pair.response)

    // Group and sort into multi-level hierarchy.
    let requestMap =
        requestResponsePairs
        // First level: group and sort requests by signature (= path + method).
        |> Seq.groupBy (fst >> RequestSignature.ofReq)
        |> Seq.sortWith (fun (a, _) (b, _) -> RequestSignature.compare a b)
        |> Seq.map (fun (requestSignature, requestsResponses) ->
            requestSignature,
            requestsResponses
            // Second level: group and sort by full request (= with headers and body).
            |> Seq.groupBy fst
            |> Seq.sortBy fst
            |> Seq.map (fun (request, entries) ->
                request,
                // Multiplicity: How often this full request.
                entries |> Seq.length,
                // Responses
                entries
                |> Seq.map snd
                // Third level: group and sort responses by signature (= status code/description).
                |> Seq.groupBy (Option.map ResponseSignature.ofResp)
                |> Seq.sortBy fst
                |> Seq.map (fun (responseSignature, responses) ->
                    responseSignature,
                    responses
                    |> Seq.sort
                )
            )
        )
        // Cache, so that iterating over it multiple times evaluates the underlying one only once
        |> Seq.cache

    requestMap, requestResponsePairs

let main args =
    let requestMap, requestResponsePairs = requestMap args.abstractionOptions args.logFile
    let fullRequests =
        requestMap
        |> Seq.map snd
        |> Seq.concat
        |> Seq.map (fun (req, count, _resps) -> req, count)
    let responseSignatures =
        requestResponsePairs
        |> Seq.countBy (snd >> (Option.map ResponseSignature.ofResp))
        |> Seq.sortBy fst

    // Output:
    if args.includeSummary then
        printfn "Summary:"
        if args.includeCounts then
            printfn "  Requests:"
            printfn "    %d unique request signatures (= HTTP method and path; after abstraction), see below for list." (Seq.length requestMap)
            printfn "    %d unique full request types (= including query, headers, and body; after abstraction), see below for list." (Seq.length fullRequests)
            printfn "    %d total concrete requests (= as actually sent by RESTler; no abstraction etc.)." (fullRequests |> Seq.sumBy snd)

            printfn "  Responses:"
            printfn "    %d unique response status codes:" (Seq.length responseSignatures)
            for responseSignature, count in responseSignatures do
                printfn "     %5d * %s" count (ResponseSignature.toString responseSignature)
            printfn "    %d total concrete responses." (responseSignatures |> Seq.sumBy snd)
        else
            printfn "  Response status codes:"
            for responseSignature, _count in responseSignatures do
                printfn "    %s" (ResponseSignature.toString responseSignature)
        printfn "\nBy request signatures (= HTTP method and path):"

    // Hash buckets output:
    match args.requestHashesDir with
    | None -> ()
    | Some dir ->
        let dir = Directory.CreateDirectory(dir)
        for request, _count in fullRequests do
            let filename = sprintf "%s_%s.http" request.method (Request.hash request)
            File.WriteAllText(Path.Combine(dir.FullName, filename), request.ToString())

    for requestSignature, requests in requestMap do
        printfn "%O" requestSignature
        for request, count, responses in requests do
            let hash = Request.hash request
            if args.includeCounts then
                printfn "  %d requests with hash=%s." count hash
                printfn "    %d unique response status codes:" (Seq.length responses)
            else
                printfn "  Requests with hash=%s" hash
                printfn "    Response status codes:"
            for responseSignature, responses in responses do
                if args.includeCounts then
                    printfn "     %4d * %s" (Seq.length responses) (ResponseSignature.toString responseSignature)
                else
                    printfn "      %s" (ResponseSignature.toString responseSignature)
