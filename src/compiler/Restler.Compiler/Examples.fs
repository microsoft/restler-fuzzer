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
        exactCopy : bool
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
        reader.DateParseHandling <- Newtonsoft.Json.DateParseHandling.None
        let jObject = JObject.Load(reader)
        Some (jObject, Some filePath)
    else
        printfn "Warning: example file %s not found" filePath
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
                                                let methodName = methodProperty.Name.ToLower()

                                                let methodExamples =
                                                    methodProperty.Value.Value<JObject>().Properties()
                                                    |> Seq.choose
                                                        (fun exampleProperty ->
                                                            let examplePayload =
                                                                match exampleProperty.Value.Type with
                                                                | JTokenType.String ->
                                                                    let filePath = exampleProperty.Value.ToString()
                                                                    // Convert to absolute file path
                                                                    let absFilePath = System.IO.Path.Combine(System.IO.Path.GetDirectoryName(exampleConfigFilePath), filePath)
                                                                    ExamplePayloadKind.FilePath absFilePath
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
        {
            ExampleConfigFile.paths = paths |> Seq.toList
            exactCopy = false
        }
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

        /// Make an exact copy of this example payload, without matching with the schema
        exactCopy : bool
    }

open NSwag

/// Merges the example payloads from all of the specified config files
let getUserSpecifiedPayloadExamples (endpoint:string) (method:string) (config:ExampleConfigFile list) (discoverExamples:bool) =
    config
    |> List.map (fun payloadExamples ->
                    if discoverExamples then
                        raise (invalidOp "Only one of 'discoverExamples' or an example config file can be specified.")
                    let exampleFilePathsOrInlinedPayloads = seq {
                        match payloadExamples.paths |> List.tryFind (fun x -> x.path = endpoint) with
                        | Some epPayload ->
                            match epPayload.methods |> List.tryFind (fun x -> x.name.ToLower() = method.ToLower()) with
                            | None -> ()
                            | Some methodPayload ->
                                for ep in methodPayload.examplePayloads do
                                    yield ep.filePathOrInlinedPayload
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
                    |> List.map (fun (json, exampleFilePath) ->
                                    /// For spec examples, the schema matches the spec, so 'exactCopy' should be false.
                                    {| exampleJson = json
                                       filePath = exampleFilePath
                                       exactCopy = payloadExamples.exactCopy |}))
    |> List.concat


/// Gets the example payloads that were specified inline in the specification
/// These are the examples specified as full payloads - individual property examples are extracted in a different place, while
/// traversing the schema.
let getSpecPayloadExamples (swaggerMethodDefinition:OpenApiOperation) (examplesDirectoryPath:string) (discoverExamples:bool) =
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
                        let refString = "$ref"
                        if exampleValues.Contains(refString) then
                            yield exampleValues.[refString]
 
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
        |> List.map (fun (json, exampleFilePath) ->
                            /// For spec examples, the schema should match the spec, so 'exactCopy' should be false.
                            {| exampleJson = json
                               filePath = exampleFilePath
                               exactCopy = false |})

let getExampleConfig (endpoint:string, method:string)
                     (swaggerMethodDefinition:OpenApiOperation)
                     discoverExamples
                     (examplesDirectoryPath:string)
                     (userSpecifiedPayloads:ExampleConfigFile list)
                     (useAllExamples:bool) =
    // TODO: only do user specified if discoverExamples is false.

    // The example payloads specified in the example config file take precedence over the
    // examples in the specification.
    let userSpecifiedPayloadExampleValues = getUserSpecifiedPayloadExamples endpoint method userSpecifiedPayloads discoverExamples
    let specPayloadExamples =
        if useAllExamples || userSpecifiedPayloadExampleValues.Length = 0 then
            getSpecPayloadExamples swaggerMethodDefinition examplesDirectoryPath discoverExamples
        else []

    let examplePayloads = userSpecifiedPayloadExampleValues @ specPayloadExamples

    examplePayloads
    |> List.map (fun examplePayload ->
                    let exampleParameterValues = examplePayload.exampleJson.["parameters"].Value<JObject>()
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
                        exampleFilePath = examplePayload.filePath
                        parameterExamples = examplePayloads
                        exactCopy = examplePayload.exactCopy
                    }
                )
