// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/// Types and parsing of raw HTTP/1.x traffic
module Restler.ResultsAnalyzer.Common.Http

open System

// For computation expressions: let! and Option.maybe { ... }
open Microsoft.FSharpLu

[<Literal>]
let private HttpDelimiter = "\r\n"
[<Literal>]
let private BodyDelimiter = "\r\n\r\n"

[<AutoOpen>]
module Types =

    /// For now we only support "absolute paths", i.e., URIs without protocol, host, and port.
    /// See https://tools.ietf.org/html/rfc2616#section-5.1.2 for the "abs_path".
    /// See https://tools.ietf.org/html/rfc2616#section-3.2.2 for all types of HTTP URIs.
    type Uri =
        {
            /// List of path components, seperated by '/' (not included)
            path: string list
            /// Map of paramter name -> value, empty if there was no query string.
            /// Note: Technically the HTTP RFC does not specify the query string at all.
            /// For example, it does not have to be a map of <name>=<value> parameters.
            /// See https://stackoverflow.com/questions/4557387/is-a-url-query-parameter-valid-if-it-has-no-value
            /// The .NET query string parser handles that gracefully however:
            /// A string without '&' or '=' is parsed as a single map entry "" -> "the string".
            queryString: Map<string, string>
        }

        /// Print as URI: path separated from query by '?', query string parameters as '<name>=<value>'.
        override this.ToString() =
            (this.path |> String.concat "/")
            + if this.queryString.IsEmpty then "" else "?"
            + (this.queryString
                |> Seq.map (fun param -> param.Key + "=" + param.Value)
                |> String.concat "&")

    /// Map of header name -> value.
    /// See https://tools.ietf.org/html/rfc2616#section-4.2
    /// Note: While header names are supposed to be case-insensitive, we intentionally do not normalize them (e.g., with ToLower()) when parsing.
    /// This retains all of the original information and is useful for debugging, but one has to be careful when doing "high-level" operations.
    /// E.g., the header names "x-gzip", "X-Gzip", and "gzip" are supposedly all equivalent, but would be different here.
    type Headers = Map<string, string>

    /// See https://tools.ietf.org/html/rfc2616#section-5
    /// Generic over body type 'T, which could be, e.g., JSON.
    type Request<'T> =
        {
            version: string
            method: string
            uri: Uri
            headers: Headers
            body: 'T
        }

        override this.ToString() =
            let headers =
                this.headers
                |> Seq.map (fun header -> header.Key + ": " + header.Value)
                |> String.concat HttpDelimiter
            sprintf "%s %O %s%s%s%s%O" this.method this.uri this.version HttpDelimiter headers BodyDelimiter this.body

    /// See https://tools.ietf.org/html/rfc2616#section-6
    /// Generic over body type 'T, which could be, e.g., JSON.
    type Response<'T> =
        {
            version: string
            statusCode: int
            statusDescription: string
            headers: Headers
            body: 'T
        }

        override this.ToString() =
            let headers =
                this.headers
                |> Seq.map (fun header -> header.Key + ": " + header.Value)
                |> String.concat HttpDelimiter
            sprintf "%s %d %s%s%s%s%O" this.version this.statusCode this.statusDescription HttpDelimiter headers BodyDelimiter this.body

    /// Pair of a request and its matching response (if any)
    type RequestResponse<'T> =
        {
            request: Request<'T>
            response: Response<'T> option
        }

    type RequestResponseWithTime<'T> =
        {
            requestWithTime: DateTime * Request<'T>
            responseWithTime: (DateTime * Response<'T>) option
        }

    /// Sequence of requests and their matching responses.
    type HttpSeq<'T> = seq<RequestResponse<'T>>

    type HttpSeqWithTime<'T> = seq<RequestResponseWithTime<'T>>

    type Log<'T> = seq<HttpSeq<'T>>

    type LogWithTime<'T> = seq<HttpSeqWithTime<'T>>

module Uri =
    let private parseQueryString (query:string): Map<string, string> =
        // Piggy back on .NET query string parser
        let queryCollection = System.Web.HttpUtility.ParseQueryString(query)
        // See https://stackoverflow.com/questions/13660647/f-namevaluecollection-to-map
        queryCollection.AllKeys
        |> Seq.map (fun key -> key, queryCollection.[key])
        |> Map.ofSeq

    let parse (uri:string): Uri option = Option.maybe {
        let! path, query =
            match uri.Split('?') with
            | [| path; query |] -> Some (path, parseQueryString query)
            | [| path |] -> Some (path, Map.empty)
            | _invalidUri -> None
        return {
            path = path.Split('/') |> Array.toList
            queryString = query
        }
    }

module Headers =
    let parse (headers:string): Headers option =
        let headerList =
            headers.Split(HttpDelimiter)
            // Special case: the RESTler engine inserts this string instead of
            // headers that include a token.
            |> Array.filter (fun x -> x <> "_OMITTED_AUTH_TOKEN_")
            |> Array.toSeq
            |> Seq.map (fun headerLine ->
                match headerLine.Split(':', 2) with
                // Header keys are supposed to be case-insensitive.
                // (But we do not lowercase them here, as to not lose information.)
                // Leading and trailing whitespace is ignored in values.
                // See https://tools.ietf.org/html/rfc2616#section-4.2 for both.
                | [| key; value |] -> Some (key, value.Trim())
                | _invalidHeaderLine -> None)
        // If a single header couldn't be parsed, parsing of the whole header section failed.
        if Seq.contains None headerList
        then
            None
        else
            headerList
            |> Seq.map Option.get
            |> Map.ofSeq
            |> Some

/// Helper for the common parts of parsing HTTP requests and responses.
/// (In HTTP lingo: message = request | response)
/// See https://tools.ietf.org/html/rfc2616#section-4.1
/// Returns Some (start line, headers, body) or None if not a valid HTTP message
let private parseHttpMessage (message:string): Option<string * Headers * string> = Option.maybe {
    let! startAndHeaders, body =
        // Body may itself contain more \r\n\r\n, so stop splitting after 2 elements.
        match message.Split(BodyDelimiter, 2, StringSplitOptions.None) with
        | [| startAndHeaders; body |] ->
            Some (startAndHeaders, body)
        | _invalidBodyDelimiter ->
            None
    let! startLine, headers =
        // I am not 100% sure headers cannot contain newlines, so limit splitting here as well.
        match startAndHeaders.Split(HttpDelimiter, 2, StringSplitOptions.None) with
        | [| startLine; headers |] -> Some (startLine, headers)
        | [| startLine |] -> Some (startLine, "")
        | _invalidStartLineDelimiter ->
            None
    let! headers = Headers.parse headers
    return startLine, headers, body
}

module Request =
    /// Parse an HTTP request, where the body is parsed to 'T by bodyParser.
    let parseWith (bodyParser: string -> 'T option) (req:string): Request<'T> option = Option.maybe {
        let! requestLine, headers, body = parseHttpMessage req
        let! method, uri, version =
            match requestLine.Split(' ') with
            | [| method; uri; version |] -> Some (method, uri, version)
            | _invalidRequestLine ->
                None
        let! uri = Uri.parse uri
        let! body = bodyParser body
        return {
            version = version
            method = method
            uri = uri
            headers = headers
            body = body
        }
    }

    let parse = parseWith Some

    // Utility functions to map over a Request's fields:

    let mapUri (f: Uri -> Uri) (req:Request<'T>) = { req with uri = f req.uri }
    let mapHeaders (f: Headers -> Headers) (req:Request<'T>) = { req with headers = f req.headers }
    // Note: We cannot use a copy and update record expression for mapBody, because f might change the body's generic type to 'U.
    // F# is not smart enough to figure out the correct result type Request<'U> and would wrongly constrain 'T = 'U.
    let mapBody (f: 'T -> 'U) (req:Request<'T>) =
        {
            version = req.version
            method = req.method
            uri = req.uri
            headers = req.headers
            body = f req.body
        }

    /// Hash to identify a particular request without having to compare or print the full contents.
    let hash req = req.ToString() |> Utilities.String.deterministicShortHash

module Response =
    /// Parse an HTTP response, where the body is parsed to 'T by bodyParser.
    let parseWith (bodyParser: string -> 'T option) (resp:string): Response<'T> option = Option.maybe {
        let! statusLine, headers, body = parseHttpMessage resp
        let! version, code, description =
            // Limit splitting because status description can contains spaces, e.g., "Bad Request"
            match statusLine.Split(' ', 3, StringSplitOptions.None) with
            | [| version; code; description |] ->
                Some (version, code, description)
            | _invalidStatusLine ->
                None
        let! code = Parsing.tryParseInt code
        let! body = bodyParser body
        return {
            version = version
            statusCode = code
            statusDescription = description
            headers = headers
            body = body
        }
    }

    let parse = parseWith Some

    // Utility functions to map over a Response's fields:

    let mapHeaders (f: Headers -> Headers) (resp:Response<'T>) = { resp with headers = f resp.headers }
    // See Request.mapBody above for comment
    let mapBody (f: 'T -> 'U) (resp:Response<'T>) =
        {
            version = resp.version
            statusCode = resp.statusCode
            statusDescription = resp.statusDescription
            headers = resp.headers
            body = f resp.body
        }

// Utility functions to map over parts of (request, response) pairs.
module RequestResponse =
    let mapRequest f { request = request; response = response } =
        {
            request = f request
            response = response
        }
    let mapResponse f { request = request; response = response } =
        {
            request = request
            response = Option.map f response
        }
    let bindResponse f { request = request; response = response } =
        {
            request = request
            response = Option.bind f response
        }

    // Since headers and bodies are present in both requests and responses, we can offer mapping over them as well:
    let mapHeaders f { request = request; response = response } =
        {
            request = Request.mapHeaders f request
            response = Option.map (Response.mapHeaders f) response
        }
    let mapBody f { request = request; response = response } =
        {
            request = Request.mapBody f request
            response = Option.map (Response.mapBody f) response
        }

    open Newtonsoft.Json
    open Newtonsoft.Json.Linq
    let parseJsonBody rr =
        mapBody
            (fun (body: string) ->
                try
                    JsonConvert.DeserializeObject<JToken>(body)
                with
                | :? JsonException as ex ->
                    eprintfn "Error: Could not parse body as JSON, using plain string instead."
                    eprintfn "%O" ex
                    eprintfn "Body was: %s" body
                    upcast new JValue(body)
            )
            rr