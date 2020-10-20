// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/// Output CSV (comma-separated values) of delays between (request, response) pairs.
module Restler.ResultsAnalyzer.Timing

open Restler.ResultsAnalyzer.Common.Http
open Restler.ResultsAnalyzer.Common.Log
open Restler.ResultsAnalyzer.Common.Utilities
open Restler.ResultsAnalyzer.Common.Abstractions

type TimingArgs =
    {
        /// Path to raw, textual network log file.
        logFile: string
        /// Abstractions to apply for the abstracted request/response columns of the produced CSV.
        abstractionOptions: AbstractionOptions
    }

module TimingArgs =
    let initWithDefaults logFile =
        {
            logFile = logFile
            abstractionOptions = AbstractionOptions.None
        }

let main args =
    let requestResponsePairs =
        args.logFile
        |> Log.parseFile
        |> Seq.concat
        // Apply abstractions, but keep the original data and time information around.
        |> Seq.map (fun { requestWithTime = (reqTime, req); responseWithTime = resp } ->
            // Use abstraction function for RequestResponse instead of replicating its implementation for RequestResponseWithTime.
            let reqRespAbstracted =
                RequestResponse.abstractAll
                    args.abstractionOptions
                    {
                        request = req
                        response = Option.map snd resp
                    }
            let req = (reqTime, req, reqRespAbstracted.request)
            let resp =
                match resp, reqRespAbstracted.response with
                | Some (respTime, resp), Some abstractedResp -> Some (respTime, resp, abstractedResp)
                | None, None -> None
                | _ -> failwith "If the original response was None, the abstracted one should be None as well and the other way around."
            (req, resp)
        )

    // Make Excel use , as delimiter by default
    printfn "sep=,"
    printfn "req method,req abstracted path,req concrete path,req abstracted hash,req time,resp status code/description,resp abstracted hash,resp time,delay (ms)"
    for ((reqTime, req, reqAbstracted), resp) in requestResponsePairs do
        // Notes about CSV format/escaping:
        // - CSV has a standard, (https://tools.ietf.org/html/rfc4180) but it is not well respected by producers/consumers in the real world.
        //   The two consumers we care about most are Excel (quick and dirty to look at) and Python pandas.read_csv (for plotting, statistics, etc.).
        // - Strings can be escaped with quotes, a quote inside the string with two doublequotes, e.g., "string with one double quote "" here."
        // - There is no reliable way to encode \r (CR) in a field :(
        //   Excel respects \r\n (CRLF, Windows newline) inside a quoted field, but not \r alone.
        //   So we escape \r and \n with a backslash, even if that breaks round-tripping open and save.
        // - \t before a field prevents Excel from "auto-detecting" the format of the datetime field (which would remove milliseconds).
        //   See https://superuser.com/questions/318420/formatting-a-comma-delimited-csv-to-force-excel-to-interpret-value-as-a-string/704291#704291
        let escapeNewlinesQuotes (str:string) =
            "\"" + (str.Replace("\n", "\\n")
                       .Replace("\r", "\\r")
                       .Replace("\"", "\"\""))
                 + "\""

        let pathAbstracted =
            reqAbstracted.uri.path
            |> String.concat "/"
            |> escapeNewlinesQuotes
        let path =
            req.uri.path
            |> String.concat "/"
            |> escapeNewlinesQuotes
        let reqHash = reqAbstracted.ToString() |> String.deterministicShortHash
        printf "%s,%s,%s,%s,\t%s,"
            req.method
            pathAbstracted
            path
            reqHash
            (reqTime.ToString "yyyy-MM-dd HH:mm:ss.fff")

        match resp with
        | None -> printfn ",,,"
        | Some (respTime, resp, respAbstracted) ->
            let respHash = respAbstracted.ToString() |> String.deterministicShortHash
            let delay = (respTime - reqTime).TotalMilliseconds |> System.Convert.ToInt32
            printfn "%d %s,%s,\t%s,%d"
                resp.statusCode
                resp.statusDescription
                respHash
                (respTime.ToString "yyyy-MM-dd HH:mm:ss.fff")
                delay

    ()