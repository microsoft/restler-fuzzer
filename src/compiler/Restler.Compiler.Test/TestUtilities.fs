// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.Test.Utilities

open System
open System.IO
open Restler.Grammar
open Tree

/// Returns the first difference found
let getLineDifferences grammar1FilePath grammar2FilePath =

    let g1 = File.ReadAllLines(grammar1FilePath)
    let g2 = File.ReadAllLines(grammar2FilePath)

    let diffElements =
        Seq.zip g1 g2
        |> Seq.filter (fun (x,y) -> x.TrimEnd() <> y.TrimEnd())

    if diffElements |> Seq.isEmpty then
        if g1.Length > g2.Length then
            Some (Some g1.[g2.Length], None)
        else if g2.Length > g1.Length then
            Some (None, Some g2.[g1.Length])
        else
            None
    else
        diffElements
        |> Seq.map (fun (x,y) -> Some (Some x, Some y))
        |> Seq.head


let rootTestOutputDirectoryPath = Path.Combine(Path.GetTempPath(), "restlerTest")
let private random = Random()
let getRandomGrammarOutputDirectoryPath() =
    Path.Combine(rootTestOutputDirectoryPath, random.Next(1000000).ToString())

module Fixtures =
    /// Fixture used to set up and clean up RESTler output directories
    type TestSetupAndCleanup() =
        let rootDirPath =
            let dirPath = getRandomGrammarOutputDirectoryPath()
            Directory.CreateDirectory(dirPath) |> ignore
            dirPath

        member x.testRootDirPath =
            rootDirPath

        interface IDisposable with
            member x.Dispose () =
                Directory.Delete(x.testRootDirPath, true)



