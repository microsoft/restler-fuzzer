// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/// Convert a textual RESTler network log to JSON.
module Restler.ResultsAnalyzer.Convert

open Restler.ResultsAnalyzer.Common.Log
open Restler.ResultsAnalyzer.Common.Http
open Restler.ResultsAnalyzer.Common.Utilities

type ConvertArgs =
    {
        /// Path to raw, textual network log file.
        logFile: string
        /// Parse request/response bodies as JSON.
        jsonBody: bool
    }

module ConvertArgs =
    let initWithDefaults logFile =
        {
            logFile = logFile
            jsonBody = false
        }

let main args =
    let httpSeqs =
        args.logFile
        |> Log.parseFile
        |> Log.removeTimings
    if args.jsonBody then
        httpSeqs
        |> Seq.map (Seq.map RequestResponse.parseJsonBody)
        |> Compact.serializeToStream stdout
    else
        httpSeqs
        |> Compact.serializeToStream stdout
