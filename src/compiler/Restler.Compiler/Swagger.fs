// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.Swagger

open Microsoft.FSharpLu.File
open NSwag

exception UnexpectedSwaggerParameter of string
exception UnsupportedParameterSchema of string
exception ParameterTypeNotFound of string

let at x = Async.AwaitTask(x)

let getSwaggerDocumentAsync (path:string) = async {
    let! swaggerDoc = OpenApiDocument.FromFileAsync(path) |> at
    return swaggerDoc
}

let getYamlSwaggerDocumentAsync (path:string) = async {
    let! swaggerDoc = OpenApiYamlDocument.FromFileAsync(path) |> at
    return swaggerDoc
}

let getSwaggerDocument (swaggerPath:string) (workingDirectory:string) =
    async {
        let specExtension = System.IO.Path.GetExtension(swaggerPath)

        let specName = sprintf "%s%s%s" (System.IO.Path.GetFileNameWithoutExtension(swaggerPath))
                                         "_preprocessed"
                                         specExtension
        let preprocessedSpecPath = workingDirectory ++ specName
        let preprocessingResult =
            SwaggerSpecPreprocessor.preprocessApiSpec swaggerPath preprocessedSpecPath
        match preprocessingResult with
        | Ok _ ->
            return! getSwaggerDocumentAsync preprocessedSpecPath
        | Error e ->
            printfn "API spec preprocessing failed (%s).  Please check that your specification is valid.  \
                        Attempting to compile Swagger document without preprocessing. " e
            return! getSwaggerDocumentAsync swaggerPath
    }
    |> Async.RunSynchronously

