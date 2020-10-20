// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.Utilities

module Operators =
    let stn x = Seq.singleton x

/// Helper module to produce compact messages in the console, but more
/// verbose messages in a log file to assist troubleshooting.
module Logging =
    open Microsoft.FSharpLu.Logging
    open System

    let logTimingInfo (message:string) =
        printfn "[%A] %s" DateTime.Now message
        Trace.info "%s" message

    let logInfo (message:string) =
        printfn "%s" message
        Trace.info "%s" message

    let logWarning (message:string) =
        printfn "%s" message
        Trace.warning "%s" message

    let logError (message:string) =
        printfn "%s" message
        Trace.error "%s" message

module JsonParse =
    open Newtonsoft.Json.Linq

    let getProperty (obj:JObject) (propertyName:string) =
        if obj.ContainsKey(propertyName) then
            obj.[propertyName] |> Some
        else
            None

    let addProperty (obj:JObject) (propertyName:string) (newValue:JToken) =
        if not (obj.ContainsKey(propertyName)) then
            obj.Add(propertyName, JObject())
        obj.[propertyName].Value<JObject>().Add(newValue)
        obj

    let getPropertyAsString (obj:JObject) (propertyName:string) =
        if obj.ContainsKey(propertyName) then
            let v = obj.[propertyName]
            let s = v.Value<string>()
            s |> Some
        else
            None

module Dict =
    open System.Collections.Generic
    let tryGetString (dict:IDictionary<_, obj>) name =
        match dict.TryGetValue name with
        | true, v ->  v :?> string |> Some
        | false, _ -> None

    let tryGetDict (dict:IDictionary<_, obj>) name =
        match dict.TryGetValue name with
        | true, v ->  v :?> IDictionary<_, obj> |> Some
        | false, _ -> None
