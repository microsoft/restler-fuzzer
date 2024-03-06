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


/// Helper that adds options specific to RESTler to Microsoft.FSharpLu.Json
module JsonSerialization = 
    open Newtonsoft.Json
    open Microsoft.FSharpLu.Json
    open System.Runtime.CompilerServices

    // Create a custom deserializer that has identical behavior to FShapLu.Json.Compact
    // except with dates parsed as strings

    type TupleAsArraySettings =
        static member formatting = Formatting.Indented
        static member settings = 
            let settings =
                JsonSerializerSettings(
                    NullValueHandling = NullValueHandling.Ignore,
                    MissingMemberHandling = MissingMemberHandling.Error,
                    DateParseHandling = DateParseHandling.None
                )
            settings.Converters.Add(CompactUnionJsonConverter(true, true))
            settings

    type private S = With<TupleAsArraySettings>
        
    let inline serialize x = S.serialize x

    let inline deserialize< ^T> json : ^T = S.deserialize< ^T> json

    let inline serializeToFile file obj = S.serializeToFile file obj

    let inline tryDeserializeFile< ^T> file = S.tryDeserializeFile< ^T> file

    let inline tryDeserialize< ^T> json = S.tryDeserialize< ^T> json

    let inline deserializeFile< ^T> file = S.deserializeFile< ^T> file

    let inline serializeToStream stream obj = S.serializeToStream stream obj

    let inline deserializeStream< ^T> stream = S.deserializeStream< ^T> stream

module JsonParse =
    open Newtonsoft.Json.Linq
    open System.Collections.Generic

    let getProperty (obj:JObject) (propertyName:string) =
        if obj.ContainsKey(propertyName) then
            obj.[propertyName] |> Some
        else
            None

    let getArrayItem (a:JArray) (idx:int) =
        if a.Count > idx then
            a.[idx] |> Some
        else
            None

    let addProperty (obj:JObject) (propertyName:string) (newValue:JToken) =
        if not (obj.ContainsKey(propertyName)) then
            obj.Add(propertyName, JObject())
        obj.[propertyName].Value<JObject>().Add(newValue)
        obj

    let removeProperty (obj:JObject) (propertyName:string) =
        if obj.ContainsKey(propertyName) then
            obj.Remove(propertyName) |> ignore

    let getPropertyAsString (obj:JObject) (propertyName:string) =
        if obj.ContainsKey(propertyName) then
            let v = obj.[propertyName]
            let s = v.Value<string>()
            s |> Some
        else
            None

    let mergeWithOverride (defaultJson:string) (overrideJson:string) =
        let newJson = JsonSerialization.deserialize<Dictionary<string, obj>> defaultJson

        let userConfigAsJson = JsonSerialization.deserialize<Dictionary<string, obj>> overrideJson
        for prop in userConfigAsJson do
            // Overwrite the default property
            if newJson.ContainsKey(prop.Key) then
                newJson.Remove(prop.Key) |> ignore
            newJson.Add(prop.Key, userConfigAsJson.[prop.Key])
        JsonSerialization.serialize newJson

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

    let serializeToFile filePath data = 
        use fs = new FileStreamWithoutPreamble(filePath, System.IO.FileMode.Create)
        JsonSerialization.serializeToStream fs data
        fs.Flush()
        fs.Dispose()

module String = 
    open System.Text
    open System.Security.Cryptography

    /// Provide a deterministic hash from a string, because
    /// F# Operator.hash / C# GetHashCode() are NOT deterministic between runs.
    /// 32 hex digits = 16 bytes = 128 bits => 2^64 elements before collision with 50% probability.
    let deterministicShortHash (str:string): string =
        let hashLength = 16 // bytes

        use sha1 = SHA1.Create()
        let bytes = Encoding.Default.GetBytes(str)
        let hashBytes = sha1.ComputeHash(bytes)
        hashBytes
        |> Seq.take hashLength
        |> Seq.map (fun b -> b.ToString("x2"))
        |> String.concat ""

    /// Provide a deterministic hash from a string, because
    /// F# Operator.hash / C# GetHashCode() are NOT deterministic between runs.
    /// 32 hex digits = 16 bytes = 128 bits => 2^64 elements before collision with 50% probability.
    let deterministicShortStreamHash (s:System.IO.Stream): string =
        let hashLength = 16 // bytes

        use sha1 = SHA1.Create()
        let hashBytes = sha1.ComputeHash(s)
        hashBytes
        |> Seq.take hashLength
        |> Seq.map (fun b -> b.ToString("x2"))
        |> String.concat ""
