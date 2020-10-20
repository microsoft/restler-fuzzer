// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.Telemetry

//Instrumentation key is from app insights resource in Azure Portal
let [<Literal>] InstrumentationKey = "6a4d265f-98cd-432f-bfb9-18ced4cd43a9"

type TelemetryClient(machineId: System.Guid, instrumentationKey: string) =
    let client = Microsoft.ApplicationInsights.TelemetryClient(new Microsoft.ApplicationInsights.Extensibility.TelemetryConfiguration(instrumentationKey))

    member __.RestlerStarted(version, task, executionId, featureList) =
        client.TrackEvent("restler started",
            dict ([
                "machineId", sprintf "%A" machineId
                "version", version
                "task", task
                "executionId", sprintf "%A" executionId
            ]@featureList))

    member __.RestlerFinished(version, task, executionId, status,
                              specCoverageCounts,
                              bugBucketCounts) =
        client.TrackEvent("restler finished",
            dict ([
                "machineId", sprintf "%A" machineId
                "version", version
                "task", task
                "executionId", sprintf "%A" executionId
                "status", sprintf "%A" status
            ]@bugBucketCounts@specCoverageCounts))

    member __.ResultsAnalyzerFinished(version, task, executionId, status) =
        client.TrackEvent("results analyzer finished",
            dict ([
                "machineId", sprintf "%A" machineId
                "version", version
                "task", task
                "executionId", sprintf "%A" executionId
                "status", sprintf "%A" status
            ]))

    interface System.IDisposable with
        member __.Dispose() =
            client.Flush()