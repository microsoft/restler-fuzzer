// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/// Functions for line-based diffing of strings and Http requests/responses where bodies are strings
module Restler.ResultsAnalyzer.Diff.DiffLines

open Restler.ResultsAnalyzer.Common.Utilities
open Restler.ResultsAnalyzer.Common.Http

open Diff
open DiffHttp

// Note 1: The type is somewhat peculiar. While the input type is a string,
// the edit type is a sequence of string edits (because the edits happen line-based).
// Note 2: The primitive edit operation type is unit, because our string diff algorithm
// currently never issues Replace<'T>. Instead, it always issues a sequence of [Delete; Insert].
// Note 3: Ideally, we would like to use a void/never/bottom type instead of unit, but F# doesn't have one.
type LinesEdit = seq<SeqMapElementEdit<string, unit>>

/// Diffing of strings
module String =
    open DiffPlex
    open DiffPlex.DiffBuilder
    open DiffPlex.DiffBuilder.Model

    /// String diff with line granularity.
    /// That is, even when only a single character changed in a line, the whole line will be regarded as changed.
    /// While this does not produce the most minimal diffs, it is often more useful for humans than super "chopped" character-level diffs.
    let diffLines (a:string, b:string): Edit<string, LinesEdit> =
        // Use DiffPlex library, which implements Myers algorithm (O(n) in space and time).
        let diffBuilder = new InlineDiffBuilder(new Differ())
        let diff = diffBuilder.BuildDiffModel(a, b)
        let editSeq =
            diff.Lines
            |> Seq.map (fun diffPiece ->
                match diffPiece.Type with
                | ChangeType.Unchanged -> SeqMapElementEdit.Equal diffPiece.Text
                | ChangeType.Inserted -> SeqMapElementEdit.Insert diffPiece.Text
                | ChangeType.Deleted -> SeqMapElementEdit.Delete diffPiece.Text
                | err -> failwithf "I do not know how to handle ChangeType %A" err)

        let allElementsEqual = editSeq |> Seq.forall SeqMapElementEdit.isEqual
        if allElementsEqual then Equal a else Edit editSeq

module Request =
    let diffLines (req:Pair<Request<string>>) = req |> Request.diffWith String.diffLines

module Response =
    let diffLines (resp:Pair<Response<string> option>) = resp |> Response.diffWith String.diffLines

module RequestResponse =
    let diffLines (reqResp:Pair<RequestResponse<string>>) = reqResp |> RequestResponse.diffWith Request.diffLines Response.diffLines

module HttpSeq =
    let diffLines (httpSeqs:Pair<HttpSeq<string>>) = httpSeqs |> Seq.diffWith RequestResponse.diffLines

module Log =
    let diffLines (logs:Pair<Log<string>>): LogEdit<string, LinesEdit> =
        logs
        |> Seq.diffWith HttpSeq.diffLines
        |> Edit.map SeqEdit.flatten
