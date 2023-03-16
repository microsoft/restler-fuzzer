// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/// Module for parsing results of different RESTler tasks in order to output them in 
/// a more user-friendly format or for reporting them in telemetry from the driver

namespace Restler.Driver

open System
open System.IO
open System.Runtime.InteropServices
open System.Text
open Microsoft.FSharpLu.File
open Restler.Driver.Types

module TaskResults =

    let getDataFromTestingSummary taskWorkingDirectory =
        let bugBucketCounts, specCoverageCounts =
            // Read the bug buckets file
            let bugBucketsFiles = Directory.GetFiles(taskWorkingDirectory, "testing_summary.json", SearchOption.AllDirectories)
            match bugBucketsFiles |> Seq.tryHead with
            | None ->
                Logging.logInfo <| "Testing summary was not found."
                [], []
            | Some testingSummaryFilePath ->
                let testingSummary =
                    Restler.Utilities.JsonSerialization.deserializeFile<Engine.TestingSummary> testingSummaryFilePath

                Logging.logInfo <| sprintf "Request coverage (successful / total): %s" testingSummary.final_spec_coverage
                Logging.logInfo <| sprintf "Attempted requests: %s" testingSummary.rendered_requests

                let bugBuckets = testingSummary.bug_buckets
                                    |> Seq.map (fun kvp -> kvp.Key, sprintf "%A" kvp.Value)
                                    |> Seq.toList
                if bugBuckets.Length > 0 then
                    Logging.logInfo <| "Bugs were found!"
                    Logging.logInfo <| "Bug buckets:"
                    let bugBucketsFormatted =
                        bugBuckets
                        |> List.fold (fun str (x,y) -> str + (sprintf "\n%s: %s" x y)) ""

                    Logging.logInfo <| sprintf "%s" bugBucketsFormatted
                else
                    Logging.logInfo <| "No bugs were found."

                let coveredRequests, totalRequests =
                    let finalCoverageValues =
                        testingSummary.final_spec_coverage.Split("/")
                                            |> Array.map (fun x -> x.Trim())
                    Int32.Parse(finalCoverageValues.[0]),
                    Int32.Parse(finalCoverageValues.[1])
                let totalMainDriverRequestsSent =
                    match testingSummary.total_requests_sent.TryGetValue("main_driver") with
                    | (true, v ) -> v
                    | (false, _ ) -> 0

                let requestStats =
                    [
                        "total_executed_requests_main_driver", totalMainDriverRequestsSent
                        "covered_spec_requests", coveredRequests
                        "total_spec_requests", totalRequests
                    ]
                    |> List.map (fun (x,y) -> x, sprintf "%A" y)
                (bugBuckets, requestStats)
        {|
            bugBucketCounts = bugBucketCounts
            specCoverageCounts = specCoverageCounts
        |}

    let generateApiCoverageReport taskWorkingDirectory =

        // Read the spec coverage file with raw request-response pairs
        let specCoverageFiles = Directory.GetFiles(taskWorkingDirectory, "speccov-min.json", SearchOption.AllDirectories)

        match specCoverageFiles |> Seq.tryHead with
        | None ->
            Logging.logInfo <| (sprintf "Spec coverage file %s not found." "speccov-min.json")
        | Some specCoverageFilePath ->
            
            let specCoverage = SpecCoverage.parseSpecCovMin specCoverageFilePath
            let failedRequestSequences = SpecCoverage.getFailedRequestSequences specCoverage

            // Serialize the failed requests to a json file as well as a more readable text file
            let specCovToInvestigateFileName = "coverage_failures_to_investigate.txt"
            let specCovToInvestigateTxtFilePath = 
                System.IO.Path.Combine(taskWorkingDirectory, specCovToInvestigateFileName)
            use stream = System.IO.File.CreateText(specCovToInvestigateTxtFilePath)

            SpecCoverage.printFailedRequestSequences failedRequestSequences stream

            Logging.logInfo <| sprintf "See '%s' to investigate API coverage." specCovToInvestigateFileName
