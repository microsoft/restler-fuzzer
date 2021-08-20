// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.XMsPaths

/// A path in x-ms-path format
type XMsPath =
    {
        /// The path part of the endpoint declared in the specification
        pathPart : string

        /// The query part of the endpoint
        queryPart : string
    }
    member x.getEndpoint() =
        sprintf "%s?%s" x.pathPart x.queryPart

    member x.getNormalizedEndpoint() =
        let transformedQuery =
            x.queryPart.Replace("=", "/")
                        .Replace("&", "/")

        let normalizedEndpoint =
            sprintf "%s%s%s"
                x.pathPart
                (if x.pathPart = "/" then "" else "/")
                transformedQuery
        normalizedEndpoint

let getXMsPath (endpoint:string) =
    let pathPart, queryPart =
        match endpoint.Split('?') with
        | [| p; q |] -> p, Some q
        | [| p |] -> p, None
        | _ ->
            // Best-effort fallback - try to use the original endpoint
            endpoint, None
    match queryPart with
    | None -> None
    | Some qp ->
        Some { pathPart = pathPart
               queryPart = qp }

/// Transform x-ms-paths present in the specification into paths, so they can be parsed
/// with a regular OpenAPI specification parser.
let convertXMsPathsToPaths (xMsPathsEndpoints:seq<string>) =
    let mapping =
        xMsPathsEndpoints

        |> Seq.map (fun ep ->
                        match getXMsPath ep with
                        | None -> ep, ep
                        | Some xMsPath ->
                            let normalizedEnpoint = xMsPath.getNormalizedEndpoint()
                            ep, normalizedEnpoint)
        |> Map.ofSeq
    mapping
