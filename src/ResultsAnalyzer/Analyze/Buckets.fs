// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.ResultsAnalyzer.Analyze.Buckets

open System
open System.Collections.Generic
open Types

open Restler.ResultsAnalyzer.Common.Http

module Similarity =
    let generalizePrimitiveValue (word:string) =
        let generalized = seq {
            match (Guid.TryParse(word)) with
            | (true, _) -> yield "guid"
            | (false, w) -> ()
            match (Int64.TryParse(word)) with
            | (true, _) -> yield "int64"
            | (false, w) -> ()
            match (UInt64.TryParse(word)) with
            | (true, _) -> yield "uint64"
            | (false, w) -> ()
            match (Double.TryParse(word)) with
            | (true, _) -> yield "double"
            | (false, w) -> ()
        }
        match generalized |> Seq.tryHead with
        | None -> word
        | Some s -> s

    let ngramSplit n (wordDelimiters:string) (s:string) =
        let words = s.Split(wordDelimiters.ToCharArray(), StringSplitOptions.RemoveEmptyEntries)

        let w2 = words |> Array.map (generalizePrimitiveValue)
                       |> Array.filter (fun s -> s.Trim().Length > 1)
        w2 |> Seq.windowed n
                |> Seq.groupBy id
                |> Seq.map (fun (ngram, occurrences) ->
                    ngram |> String.concat ",", Seq.length occurrences)

    let getJaccardSimilarity words1 words2 =
        let a = set words1
        let b = set words2
        let c = Set.intersect a b
        let intersectionCount = c |> Set.count
        let unionCount = (a |> Set.count) + (b |> Set.count) - intersectionCount
        float intersectionCount / float unionCount

[<Literal>]
let wordDelimiters = " /:\\\",-';.<>!\r\n"

let MaxBucketCountPerCode = 100
let DistanceBound = 0.5
let NgramSize = 5
// Implement a simple bucketing scheme for error messages by using the Jacquard similarity metric
// for n-grams of the error messages.
// The below shortcut to only check a small N of messages before bucketizing
// works reasonably well for error bucketization,
// because there are relatively few error buckets
// per service, and the goal is to group error messages with the same error but slight
// differences in text (e.g. due to generated identifiers, context).
// This is not the best approach to measure coverage based on error messages, since cases
// that have the exact same message but refer to different parameters (e.g. "invalid parameter: 'name'"
// will be bucketed together - that coverage problem will need additional heuristics and taking
// the request into account.
let MaxBucketSizeToAnalyze = 5

let getDistance responseData
                (nGrams:Dictionary<string, seq<string * int>>)
                (bucketRequestData:RequestExecutionSummary list) =
    let responseContent =
        responseData.body

    let ngram1 =
        if not (nGrams.ContainsKey(responseContent)) then
            let ng = Similarity.ngramSplit NgramSize wordDelimiters responseContent
            nGrams.Add(responseContent, ng)
        nGrams.[responseContent]
    bucketRequestData
        |> List.truncate MaxBucketSizeToAnalyze
        |> List.map (fun rd ->
                        let rc2 =
                            match rd.response with
                            | ResponseData rd -> rd.content
                            | ResponseText txt -> txt

                        let ngram2 =
                            if not (nGrams.ContainsKey(rc2)) then
                                let ng = Similarity.ngramSplit NgramSize wordDelimiters rc2
                                nGrams.Add(rc2, ng)
                            nGrams.[rc2]
                        Similarity.getJaccardSimilarity ngram1 ngram2)
        |> List.max

let getBuckets (runDataByResponseCode:seq<int * seq<Request<string> * Response<string> option>>) =
    let b = seq {
        for errorCode, responseBucket in runDataByResponseCode do
            // Do not bucketize the successful requests.
            let len = responseBucket |> Seq.length

            let buckets = Dictionary<Guid, RequestExecutionSummary list>()
            let nGrams = Dictionary<string, seq<string * int>>()
            for (request, response) in responseBucket do
                if response.IsSome then
                    let requestSummary =
                        {
                            RequestExecutionSummary.request =
                                RequestData
                                    {
                                        method = request.method
                                        path = request.uri.path
                                                |> List.filter (fun s -> not (String.IsNullOrWhiteSpace s))
                                                |> List.fold (fun p s-> sprintf "%s/%s" p s) ""
                                        query = request.uri.queryString
                                                |> Map.toSeq
                                                |> Seq.map (fun (paramName,paramValue) -> sprintf "%s=%s" paramName paramValue)
                                                |> String.concat "&"
                                        body = request.body
                                    }
                            RequestExecutionSummary.response =
                                match response with
                                | Some r ->
                                    ResponseData
                                        {
                                            code = r.statusCode
                                            codeDescription = r.statusDescription
                                            content = r.body
                                        }
                                | None ->
                                    ResponseText "Error: Response could not be parsed.  See the network logs to investigate."
                            RequestExecutionSummary.requestPayload = None
                            RequestExecutionSummary.responsePayload = None
                        }
                    match response with
                    | None ->
                        // TODO: extend implementation to bucketize invalid responses by the text
                        ()
                    | Some resp ->
                        if buckets.Count = 0 then
                            buckets.Add(Guid.NewGuid(), [requestSummary])
                        else
                            let id, dist =
                                buckets
                                |> Seq.map (fun kvp -> (kvp.Key, getDistance resp nGrams kvp.Value))
                                |> Seq.maxBy (fun (k, d) -> d)

                            if dist > DistanceBound then
                                buckets.[id] <- requestSummary::buckets.[id]
                            else if buckets.Count < MaxBucketCountPerCode then
                                buckets.Add(Guid.NewGuid(), [requestSummary])
                            else
                                eprintfn "ERROR: Ran out of buckets for error code %d! The maximum is: %d" errorCode MaxBucketCountPerCode
            yield errorCode, buckets
    }
    b |> Seq.toList

