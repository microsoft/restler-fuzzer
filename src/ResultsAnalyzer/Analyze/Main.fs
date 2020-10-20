// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/// Given a path to REST-ler network logs in the expected format,
/// analyze them and output a json summary report.
/// Note: currently, the output is grouped by request.
// TODO (VSTS #6035): this must also be categorized by request sequence.
module Restler.ResultsAnalyzer.Analyze.Main

open System
open System.IO

open Restler.ResultsAnalyzer.Analyze.Types
open Restler.ResultsAnalyzer.Common.Abstractions
open Restler.ResultsAnalyzer.Common.Log
open Restler.ResultsAnalyzer.Common.Http

[<Literal>]
let UnknownResponseCode = 0

[<Literal>]
let DefaultMaxInstancesPerBucket = Int32.MaxValue

type AnalyzeArgs =
    {
        logsPath : string
        outputDirPath : string
        includePayload : bool
        maxInstancesPerBucket : int
        fuzzingDictionaryPath: string option
    }

module AnalyzeArgs =
    let initWithDefaults logsPath =
        {
            logsPath = logsPath
            outputDirPath = ""
            includePayload = true
            maxInstancesPerBucket = DefaultMaxInstancesPerBucket
            fuzzingDictionaryPath = None
        }

let main (args:AnalyzeArgs) =
    printfn "Analyzing REST-ler network logs in %s" args.logsPath

    let networkLogs =
        if Directory.Exists args.logsPath then
            Directory.GetFiles(args.logsPath, "network.testing.*.txt", SearchOption.AllDirectories)
        else
            [|args.logsPath|]

    let dictionarySuffixes =
        match args.fuzzingDictionaryPath with
        | None -> List.empty
        | Some dictionaryFilePath ->
            if File.Exists dictionaryFilePath then
                match Microsoft.FSharpLu.Json.Compact.tryDeserializeFile<Restler.Dictionary.MutationsDictionary> dictionaryFilePath with
                | Choice1Of2 d ->
                    d.restler_custom_payload_uuid4_suffix
                    |> Option.defaultValue Map.empty
                    |> Map.toSeq
                    |> Seq.map (fun (_jsonProperty, jsonValue) -> new System.Text.RegularExpressions.Regex(jsonValue))
                    |> Seq.toList
                | Choice2Of2 e ->
                    eprintfn "Cannot deserialize mutations dictionary: %s" e
                    exit 1
            else
                eprintfn "Invalid Path to mutations dictionary: %s" dictionaryFilePath
                exit 1

    let abstractionOptions =
        { AbstractionOptions.None with
            abstractUuid = true
            abstractRandomSuffix = dictionarySuffixes
        }

    let requestResponsePairs logFile =
        logFile
        |> Log.parseFile
        |> Log.removeTimings
        // Flatten sequences of HTTP traffic into (stateless) pairs of (request, maybe response).
        |> Seq.concat
        // Apply abstractions
        |> Seq.map (RequestResponse.abstractAll abstractionOptions)
        // Simplify structure
        |> Seq.map (fun pair -> pair.request, pair.response)

    let failedStatusRequestResponsePairs =
        networkLogs
        |> Seq.map (requestResponsePairs)
        |> Seq.concat
        // Success codes are not bucketized, so exclude them early to improve memory usage.
        |> Seq.filter (fun (req, resp) ->
                            match resp with
                            | Some response -> isFailure response.statusCode
                            | None -> true)
        |> Seq.cache

    let failedByResponseCode =
        failedStatusRequestResponsePairs
        |> Seq.groupBy (fun (req, resp) ->
                            match resp with
                            | Some response -> response.statusCode
                            | None -> UnknownResponseCode)

    let allBuckets = Restler.ResultsAnalyzer.Analyze.Buckets.getBuckets failedByResponseCode

    let errorBucketsFilePath = Path.Combine(args.outputDirPath, "errorBuckets.json")

    let allBucketsMapTrimmed =
        allBuckets
        |> List.map(fun (errorCode, bucketDictionary) ->
                        let trimmed = bucketDictionary
                                      |> Seq.map (fun kvp -> (kvp.Key,
                                                              kvp.Value
                                                              |> Seq.truncate args.maxInstancesPerBucket))
                        errorCode, trimmed |> Map.ofSeq) //maybe dont need this?
        |> Map.ofSeq

    Microsoft.FSharpLu.Json.Compact.serializeToFile errorBucketsFilePath allBucketsMapTrimmed

    let runSummaryFilePath = Path.Combine(args.outputDirPath, "runSummary.json")
    let runDataMap = failedByResponseCode |> Map.ofSeq
    let runSummary =
        {
            RunSummary.requestsCount = failedStatusRequestResponsePairs |> Seq.length
            sequencesCount = 0
            RunSummary.bugCount = match runDataMap |> Map.tryFind BugResponseCode with
                                  | Some x -> x |> Seq.length
                                  | None -> 0
            RunSummary.errorBuckets =
                allBuckets
                |> Seq.map (fun (errorCode, dict) ->
                                dict |> Seq.map (fun kvp -> (errorCode, kvp.Key), kvp.Value |> Seq.length))
                |> Seq.concat
                |> Map.ofSeq

            RunSummary.codeCounts = runDataMap
                                    |> Map.map (fun k v ->
                                                  (v |> Seq.length))
                                    |> Map.toSeq
                                    |> Seq.sortByDescending (fun (k, v) -> v)
                                    |> Map.ofSeq
        }

    Microsoft.FSharpLu.Json.Compact.serializeToFile runSummaryFilePath runSummary
