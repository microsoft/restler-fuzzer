// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/// Extend Http types with functions for abstracting (=replacing a pattern with a constant) certain parts.
module Restler.ResultsAnalyzer.Common.Abstractions

open System.Text.RegularExpressions

open Http

type AbstractionOptions =
    {
        abstractUuid: bool
        abstractHeader: Regex list
        abstractQueryParameter: Regex list
        abstractRandomSuffix: Regex list
        abstractCustom: Regex list
    }

module AbstractionOptions =
    let None =
        {
            abstractUuid = false
            abstractHeader = []
            abstractQueryParameter = []
            abstractRandomSuffix = []
            abstractCustom = []
        }

module RequestResponse =
    let abstractHeaderValueByKey (keyPattern:Regex) =
        RequestResponse.mapHeaders (
            Map.map (fun key value ->
                if keyPattern.IsMatch(key)
                then "_HEADER_ABSTRACTED_"
                else value))

    let abstractQueryParameterByName (namePattern:Regex) =
        RequestResponse.mapRequest (
            Request.mapUri (fun uri ->
                {
                    path = uri.path
                    queryString =
                        uri.queryString
                        |> Map.map (fun key value ->
                            if namePattern.IsMatch(key)
                            then "_QUERY_PARAMETER_ABSTRACTED_"
                            else value)
                }
            ))

    let private replaceInHeaderValues (pattern:Regex) (replacement:string) =
        RequestResponse.mapHeaders (
            Map.map (fun _key value ->
                pattern.Replace(value, replacement)))

    let private replaceInBody (pattern:Regex) (replacement:string) =
        RequestResponse.mapBody (fun body ->
            pattern.Replace(body, replacement))

    let private replaceInUri (pattern:Regex) (replacement:string) =
        RequestResponse.mapRequest (
            Request.mapUri (fun uri ->
                {
                    path =
                        uri.path
                        |> List.map (fun pathComponent -> pattern.Replace(pathComponent, replacement))
                    queryString =
                        uri.queryString
                        |> Map.map (fun _key value -> pattern.Replace(value, replacement))
                }
            ))

    /// Apply string mapping (regex pattern -> replacement string) on all "values" in Request/Response:
    /// - Uri path (each path component separately)
    /// - Uri query parameter values (not keys)
    /// - Header values (not keys)
    /// - Body (must be of type string)
    let private replaceInValues (pattern:Regex) (replacement:string) =
        replaceInUri pattern replacement
        >> replaceInHeaderValues pattern replacement
        >> replaceInBody pattern replacement

    let abstractUuid =
        let pattern = new Regex("[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
        replaceInValues pattern "_UUID_ABSTRACTED_"

    let private removeSpecialChars (pattern:Regex) = Regex.Replace(pattern.ToString(), "[^\w]", "")

    let abstractCustom pattern =
        // Include the pattern inside the replacement string to disambiguate different custom abstractions.
        let replacement = sprintf "_CUSTOM_ABSTRACTED_%s_" <| removeSpecialChars pattern
        replaceInValues pattern replacement

    let abstractRandomSuffix pattern =
        // Include the pattern inside the replacement string to disambiguate different random suffix abstractions.
        let replacement = sprintf "%s_RANDOM_SUFFIX_ABSTRACTED_" <| removeSpecialChars pattern
        let pattern = new Regex(sprintf "(%s)[0-9a-fA-F]{10}" <| pattern.ToString())
        replaceInValues pattern replacement

    /// Convenience: apply all abstractions specified in the commonly used command-line options.
    let abstractAll (options:AbstractionOptions) =
        (if options.abstractUuid then abstractUuid else id)
        // WARNING Earlier abstractions might produce a replacement that matches in later abstractions and gets replaced again :/
        // By applying the custom abstractions first, we at least have the most "compatible" or "agressive" one first and hopefully
        // simply because Header and QueryParameter abstractions are more restricted in scope, they won't match again...
        >> (options.abstractCustom
            |> Seq.fold (fun f pattern -> f >> abstractCustom pattern) id)
        >> (options.abstractRandomSuffix
            |> Seq.fold (fun f pattern -> f >> abstractRandomSuffix pattern) id)
        >> (options.abstractHeader
            |> Seq.fold (fun f pattern -> f >> abstractHeaderValueByKey pattern) id)
        >> (options.abstractQueryParameter
            |> Seq.fold (fun f pattern -> f >> abstractQueryParameterByName pattern) id)
