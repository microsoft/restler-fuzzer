// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.ResultsAnalyzer.Common.Utilities

open System.IO
open System.Text
open System.Security.Cryptography

open Newtonsoft.Json

/// Active pattern for regular expressions.
/// See http://www.fssnip.net/29/title/Regular-expression-active-pattern
let (|Regex|_|) pattern input =
    let m = RegularExpressions.Regex.Match(input, pattern)
    if m.Success then Some(List.tail [ for g in m.Groups -> g.Value ])
    else None

module String =
    /// Parse string that was serialized in python with repr().
    /// See https://www.python.org/dev/peps/pep-3138/
    let ofPythonRepr (repr:string): string =
        let sb = StringBuilder repr
        sb.Replace("\\r", "\r")
            .Replace("\\n", "\n")
            .Replace("\\t", "\t")
            .Replace(@"\\", @"\")
            .ToString()

    /// Provide a deterministic hash from a string, because
    /// F# Operator.hash / C# GetHashCode() are NOT deterministic between runs.
    /// 32 hex digits = 16 bytes = 128 bits => 2^64 elements before collision with 50% probability.
    let deterministicShortHash (str:string): string =
        let hashLength = 16 // bytes

        use sha1 = new SHA1Managed()
        let bytes = Encoding.Default.GetBytes(str)
        let hashBytes = sha1.ComputeHash(bytes)
        hashBytes
        |> Seq.take hashLength
        |> Seq.map (fun b -> b.ToString("x2"))
        |> String.concat ""

module Seq =
    /// Generic split on sequences (similar to String.Split).
    /// Split source into subsequences at every separator. The separator is not included in the subsequences.
    /// Each subsequence is produced lazily, so it uses little memory and has less latency on large input sequences.
    let split (separator:'T) (source:seq<'T>): seq<seq<'T>> = seq {
        let currentSubseq = new ResizeArray<'T>()

        for x in source do
            if x <> separator then
                currentSubseq.Add(x)
            else
                // Copy the subsequence before yielding...
                yield Seq.ofArray (currentSubseq.ToArray())
                // ...and before clearing the underlying buffer.
                currentSubseq.Clear()

        // Don't forget to yield the last subsequence.
        currentSubseq.TrimExcess()
        yield currentSubseq
    }

module Map =
    /// Like Map.ofSeq, but returns None if the sequence contains duplicate keys
    /// (and creating the map would thus loose information).
    let tryOfSeq (seq:seq<'K * 'V>): Map<'K, 'V> option =
        let keys = seq |> Seq.map fst
        if (Seq.length keys) <> (Seq.length (Seq.distinct keys))
        then None
        else Some (seq |> Map.ofSeq)

    /// Append two Maps, but return None if there were duplicate keys
    let tryAppend (mapA:Map<'K, 'V>) (mapB:Map<'K, 'V>): Map<'K, 'V> option =
        mapA
        |> Map.toSeq
        |> Seq.append (Map.toSeq mapB)
        |> tryOfSeq

    /// Like Seq.choose
    let choose f map =
        map
        |> Map.map (fun _key value -> f value)
        |> Map.filter (fun _key value -> Option.isSome value)
        |> Map.map (fun _key value -> Option.get value)

/// Homogeneous 2-tuple
type Pair<'T> = 'T * 'T

module Pair =
    /// Apply f to both members of the pair.
    /// See https://stackoverflow.com/questions/21960145/is-there-an-existing-function-to-apply-a-function-to-each-member-of-a-tuple
    let map f (a, b) = (f a, f b)

    /// "Reorder" two pairs, i.e., create a pair of the first elements and a pair of the second elements.
    let zip (a1, a2) (b1, b2) = (a1, b1), (a2, b2)

/// Extend Microsoft.FSharpLu.Json.Compact with serialization to stream,
/// i.e., not first materializing into a string in memory like Compact.serialize.
module Compact =
    let serializeToStreamWith (textWriter:TextWriter) (additionalConverters: seq<JsonConverter>) x =
        let serializer = new JsonSerializer()
        // See FSharpLu source for these default values: https://github.com/Microsoft/fsharplu/blob/master/FSharpLu.Json/Compact.fs
        serializer.Formatting <- Formatting.Indented
        serializer.NullValueHandling <- NullValueHandling.Ignore
        serializer.MissingMemberHandling <- MissingMemberHandling.Error
        // Add the additional converters BEFORE the "fallback" standard FSharpLu one.
        for converter in additionalConverters do
            serializer.Converters.Add(converter)
        serializer.Converters.Add(new Microsoft.FSharpLu.Json.CompactUnionJsonConverter(true))

        use jsonTextWriter = new JsonTextWriter(textWriter)
        serializer.Serialize(jsonTextWriter, x)

    let serializeToStream textWriter x = serializeToStreamWith textWriter [] x
