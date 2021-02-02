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


module Stream =
    /// https://en.wikipedia.org/wiki/UTF-8
    /// Byte order mark (or Preamble)
    /// If the UTF-16 Unicode byte order mark (BOM) character is at the start of a UTF-8 file, the first three bytes will be 0xEF, 0xBB, 0xBF.
    ///The Unicode Standard neither requires nor recommends the use of the BOM for UTF-8, but warns that it may be encountered at the 
    /// start of a file trans-coded from another encoding.[46] While ASCII text encoded using UTF-8 is backward compatible with ASCII, 
    /// this is not true when Unicode Standard recommendations are ignored and a BOM is added. Nevertheless, there was and still is 
    /// software that always inserts a BOM when writing UTF-8, and refuses to correctly interpret UTF-8 unless the first character is a BOM
    type FileStreamWithoutPreamble(filePath, mode: System.IO.FileMode) =
        inherit System.IO.FileStream(filePath, mode)

        let preamble = System.Text.UTF8Encoding.UTF8.GetString(System.Text.UTF8Encoding.UTF8.GetPreamble())

        override __.Write(s, offset, count) =
            let str = System.Text.UTF8Encoding.UTF8.GetString(s, offset, count)
            if str = preamble then
                ()
            else
                base.Write(s, offset, count)