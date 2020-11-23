// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.SwaggerSpecPreprocessor

open Microsoft.FSharpLu.File
open System.IO
open Newtonsoft.Json.Linq
open System.Linq
open System.Collections.Generic
open Restler.Utilities.Operators

type RefResolution =
| FileRefs
| AllRefs

type Ref =
| FileRef of string
| LocalDefinitionRef of string
| FileDefinitionRef of string * string

let normalizeFilePath x =
    Path.GetFullPath(x)

type SpecFormat =
    | Json
    | Yaml

let getSpecFormat (specFilePath:string) =
    let specExtension = System.IO.Path.GetExtension(specFilePath)

    match specExtension with
    | ".json" ->
        SpecFormat.Json
    | ".yml"
    | ".yaml" ->
        SpecFormat.Yaml
    | _ ->
        raise (invalidArg specExtension "This specification format extension is not supported")

module Yaml =
    open YamlDotNet.Serialization
    let convertYamlToJson (yamlFilePath:string) =
        use specReader = new StreamReader(yamlFilePath)
        let deserializer = YamlDotNet.Serialization.Deserializer()
        let yamlObject = deserializer.Deserialize(specReader)
        let serializer = (SerializerBuilder()).JsonCompatible().Build()
        let json = serializer.Serialize(yamlObject)
        json

let getJsonSpec filePath =
    let specFormat = getSpecFormat filePath
    match specFormat with
    | Json -> System.IO.File.ReadAllText(filePath)
    | Yaml -> Yaml.convertYamlToJson filePath

module SpecCache =

    let findSpec filePath (jsonSpecs:Dictionary<string, JObject>) =
        let normalizedPath = normalizeFilePath filePath

        if not (jsonSpecs.ContainsKey(normalizedPath)) then
            let jsonSpecText = getJsonSpec normalizedPath

            let spec = JObject.Parse(jsonSpecText)
            jsonSpecs.Add(normalizedPath, spec)
        jsonSpecs.[normalizedPath]

/// Find the object at 'refPath' in the specified file.
let getObjInFile filePath (refPath:string) (jsonSpecs:Dictionary<string, JObject>) =
    if not (File.Exists(filePath)) then
        raise (FileNotFoundException(sprintf "Referenced file %s does not exist" filePath))
    let jsonSpec = SpecCache.findSpec filePath jsonSpecs

    let refPathForSelectToken = refPath.Replace("/", ".")
    let tok = jsonSpec.SelectToken(refPathForSelectToken)
    if isNull tok then
        raise (invalidOp(sprintf "Referenced property %s does not exist in file %s" refPath filePath))
    tok


/// Parses the value of a $ref property and returns the type of reference.
let getDefinitionRef (refLocation:string) =
    let s = refLocation.Split([|'#'|], System.StringSplitOptions.RemoveEmptyEntries)
    match (s |> Seq.tryItem 0), (s|> Seq.tryItem 1) with
    | Some a, None ->
        if refLocation.StartsWith("#") then
            // Local reference to a type definition
            LocalDefinitionRef a
        else
            // Just a file reference (e.g. specifies an example object)
            FileRef a
    | Some a, Some b ->
        // Type definition in another file
        FileDefinitionRef (a, b)
    | None, _ ->
        raise (invalidOp(sprintf "Invalid Ref found: %s" refLocation))


/// Returns a list of properties with all file $refs inlined.
// TODO: this doesn't catch recursion in local refs (within a file) yet.
let rec private inlineFileRefs2
                    (properties:seq<JProperty>)
                    (normalizedDocumentFilePath:string)
                    (parentPropertyPath:string)
                    (refResolution:RefResolution)
                    (jsonSpecs:Dictionary<string, JObject>)
                    refStack =

    let resolveRefs normalizedFullRefFilePath definitionPath jsonSpecs refStack propertyName =
        // Get the referenced object from the file
        let (foundObj:JObject) =
            let tok = getObjInFile normalizedFullRefFilePath definitionPath jsonSpecs
            // We are replacing the single "$ref": "Path" with a potentially
            // list of properties in that type definition.
            tok.Value<JObject>()

        if foundObj.HasValues then
            // Check for recursive references.
            let fullTokenPath = normalizedFullRefFilePath, foundObj.Path
            let recursionFound = refStack |> List.contains fullTokenPath
            if recursionFound then
                //printfn "Recursion detected! Referenced %O, reference chain: %O" fullTokenPath refStack
                // Just end the recursion with an object instead of the ref.
                // { "type": "object", "description": "Restler: recursion limit reached" }
                seq {
                    yield JProperty("type", "object")
                    yield JProperty( "description", "Restler: recursion limit reached")
                }
            else
                inlineFileRefs2 (foundObj.Properties())
                                normalizedFullRefFilePath
                                (sprintf "%s/%s" parentPropertyPath propertyName)
                                RefResolution.AllRefs
                                jsonSpecs
                                (fullTokenPath::refStack)
                |> Seq.concat
        else
            foundObj.Properties() |> Seq.map (fun p -> p)


    properties
    |> Seq.map (fun x ->
                        if x.Name = "$ref" then
                            let refLocation = x.Value.ToString()
                            match getDefinitionRef refLocation with
                            | LocalDefinitionRef definitionRef ->
                                match refResolution with
                                | RefResolution.FileRefs ->
                                    // IF this is a local definition in the top-level Swagger, keep as is.
                                    x |> stn
                                | RefResolution.AllRefs ->
                                    resolveRefs normalizedDocumentFilePath definitionRef jsonSpecs refStack x.Name
                            | FileRef fileRef ->
                                // Need to make it an absolute file path because the preprocessed spec
                                // is not in the same directory as the original spec.
                                let fullRefFilePath = normalizeFilePath (Path.GetDirectoryName(normalizedDocumentFilePath) ++ fileRef)
                                let p = JProperty(x.Name, fullRefFilePath)
                                p |> stn
                            | FileDefinitionRef (fileRef, definitionRef) ->
                                // Note: fileRef *must* be normalized below
                                let normalizedFullRefFilePath =
                                     normalizeFilePath (Path.GetDirectoryName(normalizedDocumentFilePath) ++ fileRef)
                                resolveRefs normalizedFullRefFilePath definitionRef jsonSpecs refStack x.Name
                        else
                            if not (isNull(x.Value)) && x.Value.HasValues then
                                let newProperty =
                                    match x.Value.Type with
                                    | JTokenType.Object ->
                                        let obj = x.Value.Value<JObject>()
                                        let childProperties =
                                            // Special case: if the child properties are a ref and a description,
                                            // skip the description of the ref.
                                            let ref = obj.Properties().Where(fun x -> x.Name="$ref")
                                            if ref.Count() > 0 then
                                                ref
                                            else
                                                // TODO: Temporary workaround for issue #61 - NSWag failure to parse
                                                // required boolean in Headers.  Remove this when the NSWag bug is fixed.
                                                // The workaround is to remove the required property.
                                                // This is fine for now, since RESTler does not currently fuzz or
                                                // learn from header values.
                                                let headerInPath = sprintf "%s.%s" "headers" x.Name
                                                if obj.Path.EndsWith(headerInPath) then
                                                    obj.Properties() |> Seq.filter (fun o -> o.Name <> "required")
                                                else
                                                    obj.Properties()
                                        let newChildProperties =
                                            inlineFileRefs2 childProperties
                                                            normalizedDocumentFilePath
                                                            (sprintf "%s/%s" parentPropertyPath x.Name)
                                                            refResolution
                                                            jsonSpecs
                                                            refStack
                                                    |> Seq.concat

                                        let o = new JObject()
                                        newChildProperties
                                        |> Seq.iter (fun p -> o.Add(p.Name, p.Value))
                                        JProperty(x.Name, o)
                                    | JTokenType.Array ->
                                        // Inline each of the array elements
                                        let objectArrayElements =
                                            x.Value.Children() |> Seq.filter( fun x -> x.Type = JTokenType.Object)
                                        let nonObjectArrayElements =
                                            x.Value.Children() |> Seq.filter( fun x -> x.Type <> JTokenType.Object)

                                        let newObjectArrayElements =
                                            let objectArrayElements = objectArrayElements |> Seq.cast<JObject>
                                            objectArrayElements
                                            |> Seq.map (fun (o:JObject) ->
                                                            let newProperties =
                                                                inlineFileRefs2 (o.Properties())
                                                                                normalizedDocumentFilePath
                                                                                (sprintf "%s/%s" parentPropertyPath "[]")
                                                                                refResolution
                                                                                jsonSpecs
                                                                                refStack
                                                                |> Seq.concat
                                                            JObject(newProperties)
                                            )
                                        // Add the simple and resolved array objects
                                        let arr = JArray()
                                        newObjectArrayElements
                                        |> Seq.iter (fun elem -> arr.Add(elem))
                                        nonObjectArrayElements
                                        |> Seq.iter (fun elem -> arr.Add(elem))
                                        JProperty(x.Name, arr)
                                    | _ ->
                                        raise (invalidOp(sprintf "Token type not supported! %O" x.Value.Type))
                                newProperty |> stn
                            else
                                x |> stn
                    )


let inlineFileRefs (jsonObj:JObject)
                   (documentFilePath:string) =
    let jsonSpecs = Dictionary<string, JObject>()

    let newObj = JObject()
    inlineFileRefs2 (jsonObj.Properties())
                    (normalizeFilePath documentFilePath)
                    ""
                    RefResolution.FileRefs
                    jsonSpecs List.empty
    |> Seq.concat
    |> Seq.iter (fun p -> newObj.Add(p.Name, p.Value))
    newObj

/// Preprocesses the document to inline all file references in type definitions (excluding examples).
let preprocessApiSpec specPath outputSpecPath =
    let jsonSpecText = getJsonSpec specPath
    let jsonSpec = JObject.Parse(jsonSpecText)

    let jsonSpec =
        let newObject = inlineFileRefs jsonSpec specPath
        newObject.ToString(Newtonsoft.Json.Formatting.None)

    File.WriteAllText(outputSpecPath, jsonSpec)
    Ok()
