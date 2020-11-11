// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.AccessPaths

/// Access path for property
type AccessPath =
    {
        path : string[]
    }
    with
        member x.getPathPropertyNameParts() =
            x.path |> Array.filter (fun x -> x <> "[0]")
        member x.getPathPartsForName() =
            x.path |> Array.map (fun x -> if x = "[0]" then "0" else x)
        member x.getParentPath() =
            if x.path |> Array.isEmpty then x
            else
                { path = x.path |> Array.take(x.path.Length - 1) }
        member x.getJsonPointer() =
            if x.path.Length = 0 then
                None
            else
                x.path |> String.concat "/" |> Some
        member x.getNamePart() =
            x.path |> Array.tryLast


let EmptyAccessPath = { path = Array.empty }

// Validate JSON Pointer notation: /parent/[0]/child/name
let tryGetAccessPathFromString (str:string) : AccessPath option =
    let ap =
        if str.StartsWith("/") then
            let parts = str.Split([|"/"|], System.StringSplitOptions.RemoveEmptyEntries)

            if parts.Length = 0 then None
            else
                Some { AccessPath.path = parts }
        else
            None
    ap


