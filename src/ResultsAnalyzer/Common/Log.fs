// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/// Types and parsing of RESTler's network logs
module Restler.ResultsAnalyzer.Common.Log

open System

open Utilities
open Http
open Microsoft.FSharpLu

type LogLine =
    | SequenceBeginning
    | Sending of DateTime * Request<string>
    | Received of DateTime * Response<string>

module Log =
    let private parseDateTime (datetime:string): DateTime =
        // Try three possible date time formats:
        let formats = [|
            // Old log format (Python ctime() function), which doesn't have milliseconds
            // and was system dependent (either with 0-padded days or space-padded).
            // see https://stackoverflow.com/questions/53709244/python-time-ctime-format-0-padding-or-space-padding
            "ddd MMM dd HH:mm:ss yyyy";
            "ddd MMM d HH:mm:ss yyyy";
            // New log format (ISO8601, space delimited, with milliseconds)
            "yyyy-MM-dd HH:mm:ss.fff" |]
        // AllowWhiteSpaces because otherwise a date like Tue May  7 12:45:25 2019 cannot be parsed.
        let (success, parsedDatetime) = DateTime.TryParseExact(datetime, formats, Globalization.CultureInfo.InvariantCulture, Globalization.DateTimeStyles.AllowWhiteSpaces)
        if success then parsedDatetime
        else
            eprintfn "Error: Could not parse datetime '%s', used current time instead." datetime
            DateTime.Now

    let private parseLogLine (lineNo, line:string): LogLine option =
        match line with
        | Regex "^Generation-\d+: Rendering Sequence-\d+" [] ->
            Some SequenceBeginning
        | Regex "^([^']*): Sending: '(.*)'" [ date; request ] ->
            let date = parseDateTime date
            let parsedRequest =
                request
                |> String.ofPythonRepr
                |> Request.parse
            match parsedRequest with
            | None -> eprintfn "Error: Could not parse request in line %d: %s" lineNo request; None
            | Some request -> Some (Sending (date, request))
        | Regex "^([^']*): Received: '(.*)'" [ date; response ] ->
            let date = parseDateTime date
            let parsedResponse =
                response
                |> String.ofPythonRepr
                |> Response.parse
            match parsedResponse with
            | None -> eprintfn "Error: Could not parse response in line %d: %s" lineNo response; None
            | Some response -> Some (Received (date, response))
        | _ignoreOtherLogLines -> None

    let private pairRequestResponses (lines:seq<LogLine>): HttpSeqWithTime<string> =
        // "Peek" at the next line in the log to bundle requests and responses together into a pair.
        // For that, append a dummy "last element" (copy of the head), so that the true last element is not missed.
        let dummyLast = lines |> Seq.tryHead |> Option.toList
        Seq.append lines dummyLast
        |> Seq.pairwise
        |> Seq.choose (function
            | Sending (time, req), Sending _ ->
                Some { requestWithTime = (time, req); responseWithTime = None }
            | Sending (time, req), Received (timeResp, resp) ->
                Some { requestWithTime = (time, req); responseWithTime = Some (timeResp, resp) }
            | Received _, Sending _ ->
                None
            | Received _, Received (time, resp) ->
                failwithf "Unexpected response without prior request at %A: %A" time resp
            | SequenceBeginning, _ | _, SequenceBeginning ->
                failwithf "Unexpected sequence marker, should have been filtered out by Seq.split already!?"
        )

    let parseFile (path:string): LogWithTime<string> =
        let parsedLines =
            path
            |> IO.File.ReadLines
            // Keep only lines that are either a sequence marker or request/responses.
            |> Seq.indexed
            |> Seq.choose parseLogLine

        if Seq.isEmpty parsedLines then
            eprintfn "Error: Log file '%s' contains no valid lines (HTTP requests/responses)" path
            Seq.empty
        else
            parsedLines
            // Skip the first SequenceBeginning marker (otherwise Seq.split creates an empty first sequence)
            |> Seq.tail
            // Split into sequences of (request, responses)
            |> Seq.split SequenceBeginning
            |> Seq.map pairRequestResponses

    let removeTimings (log:LogWithTime<'T>): Log<'T> =
        log
        |> Seq.map (Seq.map (fun rr ->
            {
                request = snd rr.requestWithTime
                response = rr.responseWithTime |> Option.map snd
            })
        )