// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/// Functions and types for diffing Http types
module Restler.ResultsAnalyzer.Diff.DiffHttp

open Restler.ResultsAnalyzer.Common.Utilities
open Restler.ResultsAnalyzer.Common.Http

open Diff

[<AutoOpen>]
module Types =
    type UriEdit =
        {
            path: SeqEdit<string>
            queryString: MapEdit<string, string>
        }

    type HeadersEdit = MapEdit<string, string>

    // Generic over the type of edit of the body.
    // Different representations are appropriate for different types of bodies.
    // E.g., for a JSON body, we might want a "tree diff", but a string body a textual diff suffices.
    type RequestEdit<'Body, 'BodyEdit> =
        {
            version: Edit<string>
            method: Edit<string>
            uri: Edit<Uri, UriEdit>
            headers: HeadersEdit
            body: Edit<'Body, 'BodyEdit>
        }

    type ResponseEdit<'Body, 'BodyEdit> =
        {
            version: Edit<string>
            statusCode: Edit<int>
            statusDescription: Edit<string>
            headers: HeadersEdit
            body: Edit<'Body, 'BodyEdit>
        }

    type RequestResponseEdit<'Body, 'BodyEdit> =
        {
            request: Edit<Request<'Body>, RequestEdit<'Body, 'BodyEdit>>
            // Note: responses are optional, thus a special edit type for them
            response: OptionEdit<Response<'Body>, ResponseEdit<'Body, 'BodyEdit>>
        }

    type HttpSeqEdit<'Body, 'BodyEdit> =
        SeqEdit<RequestResponse<'Body>, RequestResponseEdit<'Body, 'BodyEdit>>

    type LogEdit<'Body, 'BodyEdit> =
        // A log is either completely equal (first parameter of the Edit), or
        // its HttpSeq's are edited as a SeqEdit<_,_>.
        Edit<Log<'Body>, SeqEdit<HttpSeq<'Body>, HttpSeqEdit<'Body, 'BodyEdit>>>

module Uri =
    let diff (uris:Pair<Uri>): Edit<Uri, UriEdit> =
        let edit =
            {
                path = uris |> Pair.map (fun uri -> uri.path) |> Seq.diff
                queryString = uris |> Pair.map (fun uri -> uri.queryString) |> Map.diff
            }
        if Edit.isEqual edit.path && Edit.isEqual edit.queryString
        then Equal (fst uris)
        else Edit edit

module Headers =
    let diff = Map.diff

module Request =
    /// Diffing of requests that is generic over the diffing method and type of the body.
    let diffWith
        (bodyDiffer:Pair<'Body> -> Edit<'Body, 'BodyEdit>)
        (reqs:Pair<Request<'Body>>)
        : Edit<Request<'Body>, RequestEdit<'Body, 'BodyEdit>> =
            let edit =
                {
                    version = reqs |> Pair.map (fun r -> r.version) |> diff
                    method = reqs |> Pair.map (fun r -> r.method) |> diff
                    uri = reqs |> Pair.map (fun r -> r.uri) |> Uri.diff
                    headers = reqs |> Pair.map (fun r -> r.headers) |> Headers.diff
                    body = reqs |> Pair.map (fun r -> r.body) |> bodyDiffer
                }
            let allFieldsEqual = Edit.isEqual edit.version && Edit.isEqual edit.method && Edit.isEqual edit.uri && Edit.isEqual edit.headers && Edit.isEqual edit.body
            if allFieldsEqual then Equal (fst reqs) else Edit edit

module Response =
    // Helper for comparing NON-optional requests.
    let private diffWithNonOption
        (bodyDiffer:Pair<'Body> -> Edit<'Body, 'BodyEdit>)
        (resps:Pair<Response<'Body>>)
        : Edit<Response<'Body>, ResponseEdit<'Body, 'BodyEdit>> =
            let edit =
                {
                    version = resps |> Pair.map (fun r -> r.version) |> diff
                    statusCode = resps |> Pair.map (fun r -> r.statusCode) |> diff
                    statusDescription = resps |> Pair.map (fun r -> r.statusDescription) |> diff
                    headers = resps |> Pair.map (fun r -> r.headers) |> Headers.diff
                    body = resps |> Pair.map (fun r -> r.body) |> bodyDiffer
                }
            let allFieldsEqual = Edit.isEqual edit.version && Edit.isEqual edit.statusCode && Edit.isEqual edit.statusDescription && Edit.isEqual edit.headers && Edit.isEqual edit.body
            if allFieldsEqual then Equal (fst resps) else Edit edit

    /// Diffing of responses that is generic over the diffing method and type of the body.
    let diffWith bodyDiffer resps = Option.diff (diffWithNonOption bodyDiffer) resps

module RequestResponse =
    /// Diffing of (request, response) pairs that is generic over the diffing method and types of bodies.
    let diffWith
        (reqBodyDiffer:Pair<Request<'Body>> -> Edit<Request<'Body>, RequestEdit<'Body, 'BodyEdit>>)
        (respBodyDiffer:Pair<Response<'Body> option> -> OptionEdit<Response<'Body>, ResponseEdit<'Body, 'BodyEdit>>)
        (requestResponse:Pair<RequestResponse<'Body>>)
        : Edit<RequestResponse<'Body>, RequestResponseEdit<'Body, 'BodyEdit>> =
        let (a, b) = requestResponse
        let edit =
            {
                request = (a.request, b.request) |> reqBodyDiffer
                response = (a.response, b.response) |> respBodyDiffer
            }

        let requestResponseEqual = Edit.isEqual edit.request && OptionEdit.isEqual edit.response
        if requestResponseEqual then Equal a else Edit edit
