// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.Swagger

open Microsoft.FSharpLu.File
open NSwag

type UnexpectedSwaggerParameter (msg:string) =
    inherit System.Exception(msg)
type UnsupportedParameterSchema (msg:string) =
    inherit System.Exception(msg)
type ParameterTypeNotFound (msg:string) =
    inherit System.Exception(msg)

let at x = Async.AwaitTask(x)

let getSwaggerDocumentAsync (path:string) = async {
    let! swaggerDoc = OpenApiDocument.FromFileAsync(path) |> at
    return swaggerDoc
}

let getYamlSwaggerDocumentAsync (path:string) = async {
    let! swaggerDoc = OpenApiYamlDocument.FromFileAsync(path) |> at
    return swaggerDoc
}

let preprocessSwaggerDocument (swaggerPath:string) (workingDirectory:string) =
    async {
        // When a spec is preprocessed, it is converted to json
        let specExtension = ".json"
        let preprocessedSpecsDirPath = workingDirectory ++ "preprocessed"
        let specName = sprintf "%s%s%s" (System.IO.Path.GetFileNameWithoutExtension(swaggerPath))
                                         "_preprocessed"
                                         specExtension
        createDirIfNotExists preprocessedSpecsDirPath
        let preprocessedSpecPath = preprocessedSpecsDirPath ++ specName
        let preprocessingResult =
            SwaggerSpecPreprocessor.preprocessApiSpec swaggerPath preprocessedSpecPath
        return preprocessedSpecPath, preprocessingResult
    }

let getSwaggerDocument (swaggerPath:string) (workingDirectory:string) =
    async {
        let! preprocessedSpecPath, preprocessingResult = preprocessSwaggerDocument swaggerPath workingDirectory
        match preprocessingResult with
        | Ok pr ->
            let! swaggerDoc = getSwaggerDocumentAsync preprocessedSpecPath
            return swaggerDoc, Some pr
        | Error e ->
            printfn "API spec preprocessing failed (%s).  Please check that your specification is valid.  \
                        Attempting to compile Swagger document without preprocessing. " e
            let! swaggerDoc = getSwaggerDocumentAsync swaggerPath
            return swaggerDoc, None
    }
    |> Async.RunSynchronously

let getSwaggerDocumentStats (swaggerPath:string) =
    use stream = System.IO.File.OpenRead(swaggerPath)
    let swaggerHash = Restler.Utilities.String.deterministicShortStreamHash stream 
    let swaggerSize = stream.Length
    [("size", swaggerSize.ToString())
     ("content_hash", swaggerHash)]
    