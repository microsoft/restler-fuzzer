// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.ResultsAnalyzer.Analyze.Types

open System
open System.Text.RegularExpressions

[<Literal>]
let BugResponseCode = 500
let isFailure x =
    x >= 400

let isBug x =
    x = BugResponseCode

// TODO replace the Http types here with the ones in Common.Http and Common.Log

type HttpRequestData =
    {
        method : string
        path : string
        query : string
        body : string
    }

type HttpResponseData =
    {
        code : int
        codeDescription: string
        content : string
    }
    member x.isFailure =
        isFailure x.code

    member x.isBug =
        isBug x.code

type RequestTrace =
    | RequestData of HttpRequestData
    /// In some cases, the request RESTler sends is not well-formed
    /// (this may be either by design for fuzzing purposes, or a bug).
    /// For such cases, capture the text.
    | RequestText of string

type ResponseTrace =
    | ResponseData of HttpResponseData
    /// In some cases, the response RESTler gets is not well-formed as
    /// (this could be due to a bug in REST-ler or in the service under test)
    /// For example, a malformed request may cause the content to be returned
    /// in a different format than specified (e.g. HTML instead of json).
    /// If this format is not supported by the log analyzer, the text should still
    /// be captured and bucketized
    | ResponseText of string

type RequestExecutionSummary =
    {
        request: RequestTrace
        response: ResponseTrace
        requestPayload : string option
        responsePayload : string option
    }

type RunSummary =
    {
        /// Total number of executed requests
        requestsCount : int

        /// Total number of executed sequences
        sequencesCount : int

        /// The number of bugs found.  Note: for now, this will be
        /// the same as the number of 'BugResponseCode' errors above.
        bugCount : int

        /// The number of errors by HTTP response code
        codeCounts : Map<int, int>

        /// The number of errors in each error bucket
        errorBuckets : Map<int * Guid, int>
    }
