// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.Dictionary

open Restler.Grammar
open Restler.ApiResourceTypes
open Restler.Utilities.Operators
open Restler.AccessPaths

exception InvalidMutationsDictionaryFormat of string

type MutationsDictionary =
    {
        // Each string type has a matching 'unquoted' type
        restler_fuzzable_string : string list
        restler_fuzzable_string_unquoted : string list
        restler_fuzzable_datetime : string list
        restler_fuzzable_datetime_unquoted : string list
        restler_fuzzable_uuid4 : string list
        restler_fuzzable_uuid4_unquoted : string list

        restler_fuzzable_int : string list
        restler_fuzzable_number : string list
        restler_fuzzable_bool : string list
        restler_fuzzable_object : string list
        restler_custom_payload : Map<string, string list> option
        restler_custom_payload_unquoted : Map<string, string list> option
        restler_custom_payload_uuid4_suffix : Map<string, string> option
        restler_custom_payload_header :  Map<string, string list> option
        shadow_values : Map<string, Map<string, string list>> option
        // TODO: restler_multipart_formdata :  Map<string, string list> option

        // Deprecated options
    }
    with
        member x.findPathPayloadEntry (payloadMap:Map<string, _> option) (entryPath:AccessPath) =
            match payloadMap with
            | None -> None
            | Some pMap ->
                pMap |> Map.filter (fun entry v ->
                                        match AccessPaths.tryGetAccessPathFromString entry with
                                        | None -> false
                                        | Some p ->
                                            p = entryPath)
                        |> Map.toSeq
                        |> Seq.tryHead

        member x.findPayloadEntry (payloadMap:Map<string, _> option) entryName =
            match payloadMap with
            | Some m ->
                m |> Map.tryFind entryName
            | None -> None

        // Note: per-endpoint dictionaries allow restricting a payload to a specific endpoint.
        member x.getParameterForCustomPayload consumerResourceName (accessPathParts: AccessPath) primitiveType =
            let payloadType = CustomPayloadType.String

            // First, check for an exact access path, and if one is not found, check for the resource name.
            let payloadName, payloadEntry =
                match x.findPathPayloadEntry x.restler_custom_payload accessPathParts with
                | Some (e,v) -> e, Some v
                | None ->
                    consumerResourceName, x.findPayloadEntry x.restler_custom_payload consumerResourceName

            match payloadEntry with
            | Some entries when payloadType = CustomPayloadType.String ->
                    match entries |> List.tryHead with
                    | None -> raise (InvalidMutationsDictionaryFormat
                                        (sprintf "You must specify at least one payload value for %s" consumerResourceName))
                    | Some entry ->
                        let payloadTrimmed = entry.Trim()
                        let isObject = payloadTrimmed.StartsWith "{" || payloadTrimmed.StartsWith "["
                        DictionaryPayload (payloadType, primitiveType, payloadName, isObject) |> stn
            | Some _ ->
                DictionaryPayload (payloadType, primitiveType, payloadName, false) |> stn
            | None -> Seq.empty

        member x.getParameterForCustomPayloadUuidSuffix
                    consumerResourceName
                    (accessPathParts: AccessPath)
                    primitiveType =
            let payloadType = CustomPayloadType.UuidSuffix

            // First, check for an exact access path, and if one is not found, check for the resource name.
            let payloadName, payloadEntry =
                match x.findPathPayloadEntry x.restler_custom_payload_uuid4_suffix accessPathParts with
                | Some (e,v) -> e, Some v
                | None ->
                    consumerResourceName, x.findPayloadEntry x.restler_custom_payload_uuid4_suffix consumerResourceName

            match payloadEntry with
            | Some entry when payloadType = CustomPayloadType.String ->
                let payloadTrimmed = entry.Trim()
                let isObject = payloadTrimmed.StartsWith "{" || payloadTrimmed.StartsWith "["
                DictionaryPayload (payloadType, primitiveType, payloadName, isObject) |> stn
            | Some _ ->
                DictionaryPayload (payloadType, primitiveType, payloadName, false) |> stn
            | None -> Seq.empty


        /// Combines the elements of the two dictionaries
        member x.combineCustomPayloadSuffix (secondDict:MutationsDictionary) =
            let combinedSuffix =
                match x.restler_custom_payload_uuid4_suffix, secondDict.restler_custom_payload_uuid4_suffix with
                | None, None -> None
                | None, Some sd -> Some sd
                | Some fd, None -> Some fd
                | Some fd, Some sd ->
                    let seqUnion =
                        [
                            fd |> Map.toSeq
                            sd |> Map.toSeq
                        ]
                        |> Seq.concat
                        |> Seq.distinctBy fst
                        |> Map.ofSeq
                    Some seqUnion
            { x with restler_custom_payload_uuid4_suffix = combinedSuffix }

/// The default mutations dictionary generated when a user does not specify it
let DefaultMutationsDictionary =
    {
        restler_fuzzable_string = ["fuzzstring"]
        restler_fuzzable_string_unquoted = []
        restler_fuzzable_int = ["0" ; "1"]
        restler_fuzzable_number = ["0.1"; "1.2"]
        restler_fuzzable_bool = ["true"]
        restler_fuzzable_datetime = ["6/25/2019 12:00:00 AM"]
        restler_fuzzable_datetime_unquoted = []
        restler_fuzzable_object = ["{}"]
        restler_fuzzable_uuid4 = ["903bcc44-30cf-4ea7-968a-d9d0da7c072f"]
        restler_fuzzable_uuid4_unquoted = []
        restler_custom_payload = Some (Map.empty<string, string list>)
        restler_custom_payload_unquoted = Some (Map.empty<string, string list>)
        restler_custom_payload_uuid4_suffix = Some (Map.empty<string, string>)
        restler_custom_payload_header = None
        shadow_values = None
    }

/// Gets the dictionary from string
let getDictionaryFromString dictStr =
    match Microsoft.FSharpLu.Json.Compact.tryDeserialize<MutationsDictionary> dictStr with
    | Choice1Of2 d ->
        Ok d
    | Choice2Of2 e ->
        Error (sprintf "ERROR: Cannot deserialize mutations dictionary.  %s" e)

/// Reads the dictionary from the specified file and returns it if it is valid
let getDictionary dictionaryFilePath =
    if System.IO.File.Exists dictionaryFilePath then
        match Microsoft.FSharpLu.Json.Compact.tryDeserializeFile<MutationsDictionary> dictionaryFilePath with
        | Choice1Of2 d ->
            Ok d
        | Choice2Of2 e ->
            Error (sprintf "ERROR: Cannot deserialize mutations dictionary.  %s" e)
    else
        Error (sprintf "ERROR: invalid path for dictionary: %s" dictionaryFilePath)
