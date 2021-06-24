// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.Examples

open Newtonsoft.Json.Linq

/// Types describing the format of the user-specified example config file
/// The format is the same as the paths section in OpenAPI specification to
/// increase readability for the user.

type ExamplePayloadKind =
    | InlineExample of JToken
    | FilePath of string

type ExamplePayload =
    {
        name : string
        filePathOrInlinedPayload : ExamplePayloadKind
    }

type ExampleMethod =
    {
        /// (exampleName, example)
        name : string
        examplePayloads : ExamplePayload list
    }

type ExamplePath =
    {
        path : string
        methods : ExampleMethod list
    }

type ExampleConfigFile =
    {
        paths : ExamplePath list
    }

/// Deserialize the example config file
(*
"paths": {
  "/.../": {
     "get": {
        "one": "/path/to/1",
        "two": "/path/to/2"
     },
     "put": {},
     ...
}
*)

let tryDeserializeJObjectFromFile filePath =
    if System.IO.File.Exists filePath then
        use stream = System.IO.File.OpenText(filePath)
        use reader = new Newtonsoft.Json.JsonTextReader(stream)
        let jObject = JObject.Load(reader)
        Some (jObject, Some filePath)
    else
        printfn "example file %s not found" filePath
        None

let tryDeserializeJObjectFromToken (inlinedExampleObject:JToken) =
    try
        let json = inlinedExampleObject.Value<JObject>()
        Some (json, None)
    with e ->
        printfn "example is not a valid object. %A" inlinedExampleObject
        None

let serializeExampleConfigFile filePath (examplePaths:seq<ExamplePath>) =
    let paths =
        examplePaths
        |> Seq.toList
        |> List.map (fun p ->
                        let exampleMethods =
                            p.methods
                            |> Seq.map (fun m ->
                                            let examplePayloads =
                                                m.examplePayloads
                                                |> Seq.map (fun e ->
                                                                let exValue =
                                                                    match e.filePathOrInlinedPayload with
                                                                    | FilePath fp -> fp :> obj
                                                                    | ExamplePayloadKind.InlineExample ex -> ex :> obj

                                                                JProperty(e.name, exValue))

                                            JProperty(m.name, JObject(examplePayloads)))
                        JProperty(p.path, JObject(exampleMethods))
                    )
    let pathProperty = JProperty("paths", JObject(paths))
    let rootObject = JObject(pathProperty)
    use stream = System.IO.File.CreateText(filePath)
    use writer = new Newtonsoft.Json.JsonTextWriter(stream)

    rootObject.WriteTo(writer)

let tryDeserializeExampleConfigFile exampleConfigFilePath =
    match tryDeserializeJObjectFromFile exampleConfigFilePath with
    | Some (jObject, _) ->
        let pathsObj = jObject.["paths"].Value<JObject>()
        let paths =
            pathsObj.Properties()
            |> Seq.map (fun pathProperty ->
                            let pathName = pathProperty.Name
                            let methods =
                                pathProperty.Value.Value<JObject>().Properties()
                                |> Seq.map (fun methodProperty ->
                                                let methodName = methodProperty.Name

                                                let methodExamples =
                                                    methodProperty.Value.Value<JObject>().Properties()
                                                    |> Seq.choose
                                                        (fun exampleProperty ->
                                                            let examplePayload =
                                                                match exampleProperty.Value.Type with
                                                                | JTokenType.String ->
                                                                    ExamplePayloadKind.FilePath (exampleProperty.Value.ToString())
                                                                | JTokenType.Object ->
                                                                    ExamplePayloadKind.InlineExample (exampleProperty.Value)
                                                                | _ ->
                                                                    raise (invalidArg exampleProperty.Name (sprintf "Invalid token found in example file: %A" exampleProperty.Value))
                                                            {   ExamplePayload.name = exampleProperty.Name
                                                                ExamplePayload.filePathOrInlinedPayload = examplePayload }
                                                            |> Some
                                                        )
                                                { ExampleMethod.name = methodName
                                                  examplePayloads = methodExamples |> Seq.toList }
                                            )
                            { ExamplePath.path = pathName
                              methods = methods |> Seq.toList }
            )
        { ExampleConfigFile.paths = paths |> Seq.toList }
        |> Some
    | None -> None

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

open NSwag

let getExampleConfig (endpoint:string, method:string)
                     (swaggerMethodDefinition:OpenApiOperation)
                     discoverExamples
                     (examplesDirectoryPath:string)
                     (userSpecifiedPayloadExamples:ExampleConfigFile option) =
    // TODO: only do user specified if discoverExamples is false.

    // The example payloads specified in the example config file take precedence over the
    // examples in the specification.
    let userSpecifiedPayloadExampleValues =
        match userSpecifiedPayloadExamples with
        | Some payloadExamples ->
            if discoverExamples then
                raise (invalidOp "Only one of 'discoverExamples' or an example config file can be specified.")
            let exampleFilePathsOrInlinedPayloads = seq {
                match payloadExamples.paths |> List.tryFind (fun x -> x.path = endpoint) with
                | Some epPayload ->
                    match epPayload.methods |> List.tryFind (fun x -> x.name = method) with
                    | None -> ()
                    | Some methodPayload ->
                        match methodPayload.examplePayloads |> Seq.tryHead with
                        | Some h ->
                            yield h.filePathOrInlinedPayload
                        | None -> ()
                | None -> ()
            }
            exampleFilePathsOrInlinedPayloads
            |> Seq.toList
            |> List.choose (fun ep ->
                                match ep with
                                | ExamplePayloadKind.FilePath fp ->
                                    tryDeserializeJObjectFromFile fp
                                | ExamplePayloadKind.InlineExample ie ->
                                    tryDeserializeJObjectFromToken ie)
        | None -> List.empty

    let exampleValues =
        if userSpecifiedPayloadExampleValues.Length > 0 then
            userSpecifiedPayloadExampleValues
        else
            let extensionData =
                if isNull swaggerMethodDefinition.ExtensionData then None
                else swaggerMethodDefinition.ExtensionData
                        |> Seq.tryFind (fun kvp -> kvp.Key = "x-ms-examples" || kvp.Key.ToLower() = "examples")

            // Get example if it exists.  If not, fall back on the parameter list.
            match extensionData with
            | None -> List.empty
            | Some example ->
                let dict = example.Value :?> System.Collections.IDictionary
                let specExampleValues =
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

                    let swaggerExampleFilePath = System.IO.Path.Combine(swaggerDocDirectory, relativePathFromSwagger)
                    // When discovering examples, use the swaggerDoc directory, otherwise check the local directory
                    // and use that example first.
                    if discoverExamples then
                        swaggerExampleFilePath
                    else
                        let localFilePath = System.IO.Path.Combine(examplesDirectoryPath, System.IO.Path.GetFileName(swaggerExampleFilePath))
                        if System.IO.File.Exists localFilePath then
                            localFilePath
                        else
                            swaggerExampleFilePath

                specExampleValues
                |> List.choose (fun relativeExampleFilePathOrRaw ->
                                    match relativeExampleFilePathOrRaw with
                                    | :? string as relativeExampleFilePath ->
                                        let exampleFilePath = getExampleFilePath relativeExampleFilePath
                                        tryDeserializeJObjectFromFile exampleFilePath
                                    | rawExample ->
                                        // Warning: NJsonSchema does not support x-ms-examples or Examples - it reads
                                        // the JSON as a schema, which should not be used here.
                                        // Instead, retrieve the raw json from the original Swagger file using
                                        // the path.
                                        // Note: An empty entry will not be included in this JSON by default.
                                        // For example, if the dictionary contains ("Properties": {}, the properties
                                        // key will be excluded from the json
                                        try
                                            // BUG: [external] in a few cases, the example JSON objects cannot be round-tripped
                                            // through the schema (for instance, if the example contains a 'type' property).
                                            // A workaround for users is to extract the example to a file and
                                            // use a $ref to refer to it.
                                            let json = JObject.FromObject(rawExample)
                                            Some (json, None)
                                        with e ->
                                            printfn "example %O is invalid. %O" rawExample e
                                            None
                                )
    exampleValues
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
