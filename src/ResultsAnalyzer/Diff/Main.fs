// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.


module Restler.ResultsAnalyzer.Diff.Main

open Microsoft.FSharpLu.Json

open Restler.ResultsAnalyzer.Common.Utilities
open Restler.ResultsAnalyzer.Common.Http
open Restler.ResultsAnalyzer.Common.Abstractions
open Restler.ResultsAnalyzer.Common.Log

open Restler.ResultsAnalyzer.Diff.Diff
open Restler.ResultsAnalyzer.Diff.DiffLines

type DiffArgs =
    {
        /// Path to two raw, textual network logs.
        logFiles: string * string
        /// Parse request/response bodies as JSON.
        jsonBody: bool
        /// Diff only requests, ignore differences in responses.
        onlyRequests: bool
        /// Ignore differences in response bodies of GET requests.
        ignoreGetResponses: bool
        /// Show parts that are equal in both logs, instead of shortening to the string "Equal".
        showEqual: bool
        /// Abstractions to apply before diffing the two logs.
        abstractionOptions: AbstractionOptions
    }

module DiffArgs =
    let initWithDefaults logA logB =
        {
            logFiles = logA, logB
            jsonBody = false
            onlyRequests = false
            ignoreGetResponses = false
            showEqual = false
            abstractionOptions = AbstractionOptions.None
        }

// Replace response bodies to GET requests by a constant string, so they don't show up in the diff (-> less false positives).
let private ignoreGetResponses { request = request; response = response } : RequestResponse<string> =
    let filteredResponse =
        if request.method = "GET"
        then
            response
            |> Option.map
                (fun resp -> { resp with body = "_IGNORE_GET_RESPONSE_BODY_" })
        else
            response
    {
        request = request
        response = filteredResponse
    }

let main (args:DiffArgs) =
    // Parse textual logs to structured representation
    let logs = args.logFiles |> Pair.map (fun file ->
        file
        |> Log.parseFile
        |> Log.removeTimings
        |> Seq.map (
            Seq.map (
                // If we shall diff only requests, remove responses here
                (if args.onlyRequests
                 then RequestResponse.bindResponse (fun _resp -> None)
                 else id)
                // If body is JSON, format it nicely by parsing >> pretty-printing
                >> (if args.jsonBody
                    then RequestResponse.parseJsonBody >> RequestResponse.mapBody Compact.serialize
                    else id)
                // Apply abstractions
                >> (RequestResponse.abstractAll args.abstractionOptions)
                >> (if args.ignoreGetResponses then ignoreGetResponses else id)
            )
        )
    )

    // Compute differences (line-based for request/response bodies).
    let diff = logs |> Log.diffLines

    // Output diff
    // Optionally print also equal values. If not given, they are just shown as "Equal".
    diff |> Compact.serializeToStreamWith stdout [new FlattenEditConverter(args.showEqual)]
