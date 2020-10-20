// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/// Generic types and functions for computing differences (edit scripts) between two types.
module Restler.ResultsAnalyzer.Diff.Diff

open Restler.ResultsAnalyzer.Common.Utilities

open Newtonsoft.Json
open Microsoft.FSharp.Reflection

/// "Edit scripts", that is, instructions on how to modify something A to become B.
[<AutoOpen>]
module Types =

    /// Primitive edit operation: Replace one value by another.
    type Replace<'T> = Replace of 'T * 'T

    /// Generic recursive edit on trees: Either the two subtrees were equal, or they were modified by 'RecEdit.
    // Note the general pattern for recursive edits: if there was no modification, the original value of type 'T is carried along,
    // otherwise the edit operation can be expressed as a totally unrelated type 'RecEdit.
    type Edit<'T, 'RecEdit> =
        | Equal of 'T
        | Edit of 'RecEdit

    /// Abbreviation, when the recursive edit operation is just Replace.
    type Edit<'T> = Edit<'T, Replace<'T>>

    /// Generic recursive edit on options: Either both options were equal, or the Some variant was inserted or deleted,
    /// or the Some variant was modified by 'RecEdit.
    [<RequireQualifiedAccess>]
    type OptionEdit<'T, 'RecEdit> =
        | Equal of 'T option
        | Insert of 'T
        | Delete of 'T
        | Edit of 'RecEdit

    /// Generic recursive edit on elements in a sequence or values in a map:
    /// Either the values were equal, or they were inserted/deleted, or they were modified by 'RecEdit.
    [<RequireQualifiedAccess>]
    type SeqMapElementEdit<'T, 'RecEdit> =
        | Equal of 'T
        | Insert of 'T
        | Delete of 'T
        | Edit of 'RecEdit

    /// Generic sequence edit as a sequence of edits of the elements.
    type SeqEdit<'T, 'RecEdit> = seq<SeqMapElementEdit<'T, 'RecEdit>>

    /// Abbreviation, for when
    /// 1. The edit operation on elements is just Replace.
    /// 2. If every element of the sequence is equal, express it as the sequence itself being equal.
    ///    (Note the outer Edit wrapper.)
    type SeqEdit<'T> = Edit<seq<'T>, SeqEdit<'T, Replace<'T>>>

    /// Generic map edit as a map of keys to edits on the values:
    /// - SeqMapElementEdit.Equal means the key was present with the same value in both maps.
    /// - SeqMapElementEdit.Insert means the key was not present with any value in the right map.
    /// - SeqMapElementEdit.Delete means the key was not present with any value in the left map.
    /// - SeqMapElementEdit.Edit means the key was present in both maps, but the value has changed by 'RecEdit.
    /// Note that we cannot express edits on keys with this, i.e., if a key is changed but the value remained the same,
    /// it is simply expressed as a Delete of the old key + Insert of the new key.
    type MapEdit<'K, 'V, 'RecEdit when 'K : comparison > = Map<'K, SeqMapElementEdit<'V, 'RecEdit>>

    /// Abbreviation, for when
    /// 1. The edit operation on values is just Replace.
    /// 2. If every value of the map is equal and all the same keys were present, express it as the map itself being equal.
    ///    (Note the outer Edit wrapper.)
    type MapEdit<'K, 'V when 'K : comparison > = Edit<Map<'K, 'V>, MapEdit<'K, 'V, Replace<'V>>>

    /// Custom JsonConverter for nicer output with Newtonsoft.Json of the recursive edit types Edit, OptionEdit,
    /// and SeqMapElementEdit. This does two things:
    /// - "Flatten" the output of the recursive Edit variant, i.e., serialize `inner` instead of `{ "Edit": inner }`
    /// - (Optional:) Do not print the equal contents, i.e., serialize to `"Equal"` instead of `{ "Equal": contents }`
    type FlattenEditConverter(printEqual:bool) =
        inherit JsonConverter()

        override __.CanConvert(ty) =
            let ty = ty.BaseType
            if ty <> null && ty.IsGenericType then
                let ty = ty.GetGenericTypeDefinition()
                (ty = typedefof<Edit<_,_>>) || (ty = typedefof<OptionEdit<_, _>>) || (ty = typedefof<SeqMapElementEdit<_, _>>)
            else false

        override __.WriteJson(writer: JsonWriter, value: obj, serializer: JsonSerializer) =
            let caseInfo, fields = FSharpValue.GetUnionFields(value, value.GetType())
            match caseInfo.Name, fields with
            | "Edit", [| inner |] ->
                serializer.Serialize(writer, inner)
            | "Equal", [| t |] ->
                if printEqual
                then serializer.Serialize(writer, t)
                else serializer.Serialize(writer, "Equal")
            | otherTag, [| t |] ->
                writer.WriteStartObject()
                writer.WritePropertyName(otherTag)
                serializer.Serialize(writer, t)
                writer.WriteEndObject()
            | tag, fields -> failwithf "Unexpected *Edit union variant %A with fields %A" tag fields

        override __.ReadJson(reader: JsonReader, ty: System.Type, existingValue: obj, serializer: JsonSerializer) =
            failwith "not implemented"


// Helpers on the edit types:

module Edit =
    let isEqual = function | Equal _ -> true | _ -> false

    /// Map over the Edit variant with f.
    let map f edit =
        match edit with
        | Equal x -> Equal x
        | Edit x -> Edit (f x)

    /// Returns the edit if it was Edit, otherwise returns defaultEditValue.
    let defaultEdit defaultEditValue edit =
        match edit with
        | Equal _ -> defaultEditValue
        | Edit x -> x

module OptionEdit =
    let isEqual = function | OptionEdit.Equal _ -> true | _ -> false

    let ofEdit<'T, 'RecEdit> (edit:Edit<'T, 'RecEdit>): OptionEdit<'T, 'RecEdit> =
        match edit with
        | Equal x -> OptionEdit.Equal (Some x)
        | Edit x -> OptionEdit.Edit x

module SeqMapElementEdit =
    let isEqual = function | SeqMapElementEdit.Equal _ -> true | _ -> false

    let ofEdit<'T, 'RecEdit> (edit:Edit<'T, 'RecEdit>): SeqMapElementEdit<'T, 'RecEdit> =
        match edit with
        | Equal x -> SeqMapElementEdit.Equal x
        | Edit x -> SeqMapElementEdit.Edit x

module SeqEdit =
    /// If all elements of a sequence are Inserts or Deletes, and the sequence is contained in another sequence,
    /// we can regard the whole subsequence as Insert'd or Delete'd.
    let flatten<'T, 'RecEdit>
        (edit:SeqEdit<seq<'T>, SeqEdit<'T, 'RecEdit>>)
        : SeqEdit<seq<'T>, SeqEdit<'T, 'RecEdit>> =
        edit |> Seq.map (function
            | SeqMapElementEdit.Edit edit ->
                let inserts = edit |> Seq.map (function | SeqMapElementEdit.Insert t -> Some t | _ -> None)
                let deletes = edit |> Seq.map (function | SeqMapElementEdit.Delete t -> Some t | _ -> None)
                if inserts |> Seq.forall Option.isSome then SeqMapElementEdit.Insert <| Seq.choose id inserts
                else if deletes |> Seq.forall Option.isSome then SeqMapElementEdit.Delete <| Seq.choose id deletes
                else SeqMapElementEdit.Edit edit
            | e -> e
        )


// Functions for creating edit scripts (through diffing) from two generic values, options, sequences, and maps:

let diff (a:'T, b:'T): Edit<'T, Replace<'T>> =
    if a = b then Equal a
    else Edit (Replace (a, b))

module Option =
    let diff<'T, 'RecEdit>
        (differ:Pair<'T> -> Edit<'T, 'RecEdit>)
        (options:Pair<'T option>)
        : OptionEdit<'T, 'RecEdit> =
        match options with
        | Some a, Some b -> OptionEdit.ofEdit <| differ (a, b)
        | Some a, None -> OptionEdit.Delete a
        | None, Some b -> OptionEdit.Insert b
        | None, None -> OptionEdit.Equal None

module Seq =
    // This is very naive and essentially assumes the sequences have the same length.
    // (If not the same length, the edit script will contain a lot of spurious replacements starting from the first insertion/deletion point.)
    // TODO Proper diff algorithm that minimizes the edit script for sequences.
    //      One option is a simple dynamic programming solution (but that is O(n*m) in the sequences lengths).
    //      See, e.g., https://en.wikipedia.org/wiki/Longest_common_subsequence_problem#Code_for_the_dynamic_programming_solution
    //      Even better would be Myers diff algorithm (O(n)).
    //      See "An O(ND) Difference Algorithm and Its Variations" by E. Myers (1986)
    let diffWith<'T, 'RecEdit>
        (differ:Pair<'T> -> Edit<'T, 'RecEdit>)
        (seqs:Pair<seq<'T>>)
        : Edit<seq<'T>, SeqEdit<'T, 'RecEdit>> =
            // Compare the elements in the sequence pairwise.
            // Seq.zip stops until the shorter of the two sequences is exhausted.
            let commonPrefix =
                seqs ||> Seq.zip
                |> Seq.map differ
                |> Seq.map SeqMapElementEdit.ofEdit

            // Then append the deleted elements (if the left sequence was longer) or insert elements (if right sequence was longer).
            let (aTail, bTail) = seqs |> Pair.map (Seq.skip (Seq.length commonPrefix))
            let editSeq = commonPrefix
            let editSeq = Seq.append editSeq (aTail |> Seq.map SeqMapElementEdit.Delete)
            let editSeq = Seq.append editSeq (bTail |> Seq.map SeqMapElementEdit.Insert)

            // Note that this searches for the first element that is NOT equal and then outputs the Edit variant.
            // This keeps the diffing past the first difference lazy.
            let someElementNotEqual = editSeq |> Seq.exists (SeqMapElementEdit.isEqual >> not)
            if someElementNotEqual
            then Edit editSeq
            else Equal (fst seqs)

    let diff<'T when 'T : equality > = diffWith<'T, Replace<'T>> diff

module Map =
    let diffWith<'K, 'V, 'RecEdit when 'K : comparison >
        (valueDiffer:Pair<'V> -> Edit<'V, 'RecEdit>)
        (maps:Pair<Map<'K, 'V>>)
        : Edit<Map<'K, 'V>, MapEdit<'K, 'V, 'RecEdit>> =
            let allKeys = maps |> Pair.map (Map.toSeq >> (Seq.map fst)) ||> Seq.append

            let editSeq =
                allKeys
                |> Seq.map (fun key ->
                    let value =
                        match maps |> Pair.map (Map.tryFind key) with
                        | (Some a, Some b) -> SeqMapElementEdit.ofEdit <| valueDiffer (a, b)
                        | (Some a, None) -> SeqMapElementEdit.Delete a
                        | (None, Some b) -> SeqMapElementEdit.Insert b
                        | (None, None) -> failwithf "allKeys should be in either of the two maps, but %A was in neither!?" key
                    (key, value))

            let allElementsEqual =
                editSeq
                |> Seq.map snd
                |> Seq.forall SeqMapElementEdit.isEqual
            if allElementsEqual then Equal (fst maps)
            else Edit (Map.ofSeq editSeq)

    let diff<'K, 'V when 'K : comparison and 'V : equality > = diffWith<'K, 'V, Replace<'V>> diff
