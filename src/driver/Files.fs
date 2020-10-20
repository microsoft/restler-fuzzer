module Restler.Driver.Files

open System
open System.IO
open Microsoft.FSharpLu.File
open Restler.Driver.Types

let rec createDirectoryWithRetries targetPath retryCount exceptions (delay:TimeSpan) (checkIfExists:bool) =
    if retryCount <= 0 then
        exceptions
        |> List.last
        |> raise
    if checkIfExists && (Directory.Exists(targetPath)) then
        ()
    else
        try
            Directory.CreateDirectory targetPath |> ignore
        with
        | :? UnauthorizedAccessException
        | :? IOException as ex ->
            let remainingRetries = retryCount - 1
            Logging.logInfo <| sprintf "Failed to create directory %s.  Re-trying for %d more attempts..." targetPath remainingRetries
            System.Threading.Thread.Sleep(delay)
            createDirectoryWithRetries targetPath remainingRetries (ex::exceptions) delay checkIfExists

let rec copyFileWithRetries sourcePath targetPath retryCount exceptions (delay:TimeSpan) =
    if retryCount <= 0 then
        exceptions
        |> List.last
        |> raise

    try
        File.Copy(sourcePath, targetPath)
    with
    | :? UnauthorizedAccessException
    | :? IOException as ex ->
        let remainingRetries = retryCount - 1
        Logging.logInfo <| sprintf "Failed to copy file to target path %s.  Re-trying for %d more attempts..." targetPath remainingRetries
        System.Threading.Thread.Sleep(delay)
        copyFileWithRetries sourcePath targetPath remainingRetries (ex::exceptions) delay


/// Creates a zip archive of a directory and uploads it.
let uploadDirectory workingDirectory contentDirectoryPath targetPath logFileName retryCount (retryDelay:TimeSpan) =
    let zipPath = workingDirectory ++ (sprintf "%s.zip" logFileName)
    if File.Exists zipPath then
        File.Delete zipPath

    System.IO.Compression.ZipFile.CreateFromDirectory(contentDirectoryPath, zipPath)

    copyFileWithRetries zipPath (targetPath ++ Path.GetFileName(zipPath))
                        retryCount [] retryDelay
    File.Delete zipPath

let createZip zipPath (fileList:seq<string>) =
    let addFileToZip fileName (fileStream:System.IO.Stream) (zipArchive:System.IO.Compression.ZipArchive) =
        use entryStream = zipArchive.CreateEntry(fileName).Open()
        fileStream.CopyTo(entryStream)

    use fileStream = File.Open(zipPath, FileMode.CreateNew)
    use zipArchive = new System.IO.Compression.ZipArchive(fileStream, System.IO.Compression.ZipArchiveMode.Create, true)
    for filePath in fileList do
        let fileName = System.IO.Path.GetFileName(filePath)
        let fileStream = File.OpenRead(filePath)
        addFileToZip fileName fileStream zipArchive

/// Creates a zip archive from files in the 'fileList' and uploads it to the target path.
let zipFilesAndUpload workingDirectory (fileList:seq<string>) targetPath zipFileName retryCount delay =

    let zipPath = workingDirectory ++ (sprintf "%s.zip" zipFileName)
    if File.Exists zipPath then
        File.Delete zipPath

    createZip zipPath fileList

    copyFileWithRetries zipPath (targetPath ++ Path.GetFileName(zipPath))
                        retryCount [] delay
    File.Delete zipPath
