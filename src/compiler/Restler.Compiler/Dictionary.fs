// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.Dictionary

open Restler.Grammar
open Restler.ApiResourceTypes
open Restler.Utilities
open Restler.Utilities.Operators
open Restler.AccessPaths

type InvalidMutationsDictionaryFormat (msg:string) =
    inherit System.Exception(msg)

type MutationsDictionary =
    {
        // Each string type has a matching 'unquoted' type
        restler_fuzzable_string : string list option
        restler_fuzzable_string_unquoted : string list option
        restler_fuzzable_datetime : string list option
        restler_fuzzable_datetime_unquoted : string list option
        restler_fuzzable_date : string list option
        restler_fuzzable_date_unquoted : string list option
        restler_fuzzable_uuid4 : string list option
        restler_fuzzable_uuid4_unquoted : string list option

        restler_fuzzable_int : string list option
        restler_fuzzable_number : string list option
        restler_fuzzable_bool : string list option
        restler_fuzzable_object : string list option
        restler_custom_payload : Map<string, string list> option
        restler_custom_payload_unquoted : Map<string, string list> option
        restler_custom_payload_uuid4_suffix : Map<string, string> option
        restler_custom_payload_header :  Map<string, string list> option
        restler_custom_payload_header_unquoted :  Map<string, string list> option
        restler_custom_payload_query :  Map<string, string list> option
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

        member x.findBodyCustomPayload endpoint (method:string) =
            let bodyPayloadName = sprintf "%s/%s/__body__" endpoint (method.ToLower())
            match x.findPayloadEntry x.restler_custom_payload bodyPayloadName with
            | Some _ -> Some bodyPayloadName
            | None -> None

        /// Find a custom payload that is specific to the request type
        /// The syntax is <endpoint>/<method>/<propertyNameOrPath>
        /// Examples:
        ///   - Specify values for the parameter 'blogId' anywhere in the payload
        ///         (path parameter will be replaced):  /blog/{blogId}/get/blogId
        member x.findRequestTypeCustomPayload endpoint (method:string) propertyNameOrPath =
            let requestTypePayloadName = sprintf "%s/%s/%s" endpoint (method.ToLower()) propertyNameOrPath
            match x.findPayloadEntry x.restler_custom_payload requestTypePayloadName with
            | Some _ -> Some requestTypePayloadName
            | None -> None

        // Note: per-endpoint dictionaries allow restricting a payload to a specific endpoint.
        member x.getParameterForCustomPayload consumerResourceName (accessPathParts: AccessPath) primitiveType parameterKind =
            // Check both custom payloads and unquoted custom payloads.
            [
                (if parameterKind = ParameterKind.Query then
                    x.restler_custom_payload_query
                 else (Some Map.empty)), CustomPayloadType.Query
                (if parameterKind = ParameterKind.Header then
                    x.restler_custom_payload_query
                 else (Some Map.empty)), CustomPayloadType.Header
                x.restler_custom_payload, CustomPayloadType.String
                x.restler_custom_payload_unquoted, CustomPayloadType.String
            ]
            |> Seq.map (fun (custom_payload_entries, payloadType) ->
                // First, check for an exact access path, and if one is not found, check for the resource name.
                let payloadName, payloadEntry =
                    match x.findPathPayloadEntry custom_payload_entries accessPathParts with
                    | Some (e,v) -> e, Some v
                    | None ->
                        consumerResourceName, x.findPayloadEntry custom_payload_entries consumerResourceName

                match payloadEntry with
                | Some entries when payloadType = CustomPayloadType.String ->
                        match entries |> List.tryHead with
                        | None -> raise (InvalidMutationsDictionaryFormat
                                            (sprintf "You must specify at least one payload value for %s" consumerResourceName))
                        | Some entry ->
                            let payloadTrimmed = entry.Trim()
                            let isObject = payloadTrimmed.StartsWith "{" || payloadTrimmed.StartsWith "["
                            DictionaryPayload
                                {
                                    payloadType = payloadType
                                    primitiveType = primitiveType
                                    name = payloadName
                                    isObject = isObject
                                } |> stn
                | Some _ ->
                    DictionaryPayload
                        {
                            payloadType = payloadType
                            primitiveType = primitiveType
                            name = payloadName
                            isObject = false
                        } |> stn

                | None -> Seq.empty)
            |> Seq.concat

        member private x.getKeys mapList =
            mapList
            |> Seq.map (fun custom_payload_header_entries ->
                            match custom_payload_header_entries with
                            | None -> Seq.empty
                            | Some d -> d |> Map.toSeq)
            |> Seq.concat
            |> Seq.map (fun (k,_) -> k)
            |> Seq.distinct

        member x.getCustomPayloadHeaderParameterNames() =
            x.getKeys [ x.restler_custom_payload_header; x.restler_custom_payload_header_unquoted ]

        member x.getCustomPayloadQueryParameterNames() =
            x.getKeys [ x.restler_custom_payload_query ]

        member x.getCustomPayloadNames() =
            x.getKeys [ x.restler_custom_payload; x.restler_custom_payload_unquoted ]

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
                DictionaryPayload
                    {
                        payloadType = payloadType
                        primitiveType = primitiveType
                        name = payloadName
                        isObject = isObject
                    } |> stn
            | Some _ ->
                DictionaryPayload
                    {
                        payloadType = payloadType
                        primitiveType = primitiveType
                        name = payloadName
                        isObject = false
                    } |> stn
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
        restler_fuzzable_string = Some [DefaultPrimitiveValues.[PrimitiveType.String]]
        restler_fuzzable_string_unquoted = Some []
        restler_fuzzable_int = Some [DefaultPrimitiveValues.[PrimitiveType.Int]]
        restler_fuzzable_number = Some [DefaultPrimitiveValues.[PrimitiveType.Number]]
        restler_fuzzable_bool = Some [DefaultPrimitiveValues.[PrimitiveType.Bool]]
        restler_fuzzable_datetime = Some [DefaultPrimitiveValues.[PrimitiveType.DateTime]]
        restler_fuzzable_datetime_unquoted = Some []
        restler_fuzzable_date = Some [DefaultPrimitiveValues.[PrimitiveType.Date]]
        restler_fuzzable_date_unquoted = Some []
        restler_fuzzable_object = Some [DefaultPrimitiveValues.[PrimitiveType.Object]]
        restler_fuzzable_uuid4 = Some [DefaultPrimitiveValues.[PrimitiveType.Uuid]]
        restler_fuzzable_uuid4_unquoted = Some []
        restler_custom_payload = Some (Map.empty<string, string list>)
        restler_custom_payload_unquoted = Some (Map.empty<string, string list>)
        restler_custom_payload_uuid4_suffix = Some (Map.empty<string, string>)
        restler_custom_payload_header = Some (Map.empty<string, string list>)
        restler_custom_payload_header_unquoted = None
        restler_custom_payload_query = Some (Map.empty<string, string list>)
        shadow_values = None
    }

/// Reads the dictionary from the specified file and returns it if it is valid
let getDictionary dictionaryFilePath =
    if System.IO.File.Exists dictionaryFilePath then
        match JsonSerialization.tryDeserializeFile<MutationsDictionary> dictionaryFilePath with
        | Choice1Of2 d ->
            Ok d
        | Choice2Of2 e ->
            Error (sprintf "ERROR: Cannot deserialize mutations dictionary.  %s" e)
    else
        Error (sprintf "ERROR: invalid path for dictionary: %s" dictionaryFilePath)

/// Reads the dictionary from the specified string
let getDictionaryFromString dictionaryString =
    match JsonSerialization.tryDeserialize<MutationsDictionary> dictionaryString with
    | Choice1Of2 d ->
        Ok d
    | Choice2Of2 e ->
        Error (sprintf "ERROR: Cannot deserialize mutations dictionary.  %s" e)


