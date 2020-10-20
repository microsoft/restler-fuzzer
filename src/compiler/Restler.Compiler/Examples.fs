// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.Examples

/// The format of an example payload.
/// Currently, all examples are valid JSON and are represented as
/// a JToken for convenience
type PayloadFormat =
    | JToken of Newtonsoft.Json.Linq.JToken

/// Parameter payload from an example
type ExampleParameterPayload =
    {
        /// The name of the parameter
        parameterName : string

        /// The content of the payload
        payload : PayloadFormat
    }

/// Request payload contents obtained from an example payload
type ExampleRequestPayload =
    {
        /// Path of the file containing this payload
        exampleFilePath : string option

        /// The payloads for each parameter
        parameterExamples : ExampleParameterPayload list
    }

open Newtonsoft.Json.Linq
open NSwag

let getExampleConfig (swaggerMethodDefinition:OpenApiOperation)
                     discoverExamples
                     examplesDirectory : ExampleRequestPayload list =
    let extensionData =
        if isNull swaggerMethodDefinition.ExtensionData then None
        else swaggerMethodDefinition.ExtensionData
                |> Seq.tryFind (fun kvp -> kvp.Key = "x-ms-examples" || kvp.Key.ToLower() = "examples")

    // Get example if it exists.  If not, fall back on the parameter list.
    match extensionData with
    | None -> List.empty
    | Some example ->
        let dict = example.Value :?> System.Collections.IDictionary
        let exampleValues =
            let filesOrRawExamples = seq {
                for i in dict.Values do
                    let exampleValues = i :?> System.Collections.IDictionary
                    if exampleValues.Count < 1 then
                        printfn "Invalid example specification found: %A" exampleValues
                    else
                        // The examples may be file references or inlined
                        // simply return the object.
                        if exampleValues.Contains("__referencePath") then
                            yield exampleValues.["__referencePath"]

                        if exampleValues.Contains("parameters") then
                            yield exampleValues :> obj
            }
            filesOrRawExamples |> Seq.toList

        let getExampleFilePath relativePathFromSwagger =
            let swaggerDocDirectory =
                System.IO.Path.GetDirectoryName(swaggerMethodDefinition.Parent.Parent.DocumentPath)
            let localDirectory = examplesDirectory

            let swaggerExampleFilePath = System.IO.Path.Combine(swaggerDocDirectory, relativePathFromSwagger)
            // When discovering examples, use the swaggerDoc directory, otherwise check the local directory
            // and use that example first.
            if discoverExamples then
                swaggerExampleFilePath
            else
                let localFilePath = System.IO.Path.Combine(localDirectory, System.IO.Path.GetFileName(swaggerExampleFilePath))
                if System.IO.File.Exists localFilePath then
                    localFilePath
                else
                    swaggerExampleFilePath

        exampleValues
        |> List.choose (fun relativeExampleFilePathOrRaw ->
                            match relativeExampleFilePathOrRaw with
                            | :? string as relativeExampleFilePath ->
                                let exampleFilePath = getExampleFilePath relativeExampleFilePath
                                if System.IO.File.Exists exampleFilePath then
                                    let text = System.IO.File.ReadAllText(exampleFilePath)
                                    // The example file contains all parameters and possible responses
                                    // Parse the example file and extract only the parameters matching
                                    // the body parameter names
                                    let json = JObject.Parse(text)
                                    Some (json, Some exampleFilePath)
                                else
                                    printfn "example file %s not found" exampleFilePath
                                    None
                            | rawExample ->
                                // Warning: NJsonSchema does not support x-ms-examples or Examples - it reads
                                // the JSON as a schema, which should not be used here.
                                // Instead, retrieve the raw json from the original Swagger file using
                                // the path.
                                // Note: An empty entry will not be included in this JSON by default.
                                // For example, if the dictionary contains ("Properties": {}, the properties
                                // key will be excluded from the json
                                try
                                    // BUG: in a few cases, the example JSON objects cannot be round-tripped
                                    // through the schema (for instance, if the example contains a 'type' property).
                                    // A workaround for users is to extract the example to a file and
                                    // use a $ref to refer to it.
                                    let json = JObject.FromObject(rawExample)
                                    Some (json, None)
                                with e ->
                                    printfn "example %O is invalid. %O" rawExample e
                                    None
                        )
        |> List.map (fun (json, exampleFilePath) ->
                        let exampleParameterValues = json.["parameters"].Value<JObject>()
                        let examplePayloads =
                            exampleParameterValues.Properties()
                            |> Seq.map (fun exampleParameter ->
                                            {
                                                parameterName = exampleParameter.Name
                                                payload = PayloadFormat.JToken exampleParameter.Value
                                            }
                                        )
                            |> Seq.toList
                        {
                            exampleFilePath = exampleFilePath
                            parameterExamples = examplePayloads
                        }
                    )
