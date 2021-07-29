﻿// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

namespace Restler.Compiler

open System
open Restler.Grammar
open Tree
open Restler.Utilities.Operators
open Newtonsoft.Json.Linq
open NJsonSchema

exception UnsupportedType of string
exception NullArraySchema of string
exception UnsupportedArrayExample of string
exception UnsupportedRecursiveExample of string

module SchemaUtilities =

    /// Get an example value as a string, either directly from the 'example' attribute or
    /// from the extension 'Examples' property.
    let tryGetSchemaExampleValue (schema:NJsonSchema.JsonSchema) =
        if not (isNull schema.Example) then
            Some (schema.Example.ToString())
        else if not (isNull schema.ExtensionData) then
            let extensionDataExample =
                schema.ExtensionData
                |> Seq.tryFind (fun kvp -> kvp.Key.ToLower() = "examples")

            match extensionDataExample with
            | None -> None
            | Some example ->
                let dict = example.Value :?> System.Collections.IDictionary
                let specExampleValues = seq {
                    if not (isNull dict) then
                        for exampleValue in dict.Values do
                            let valueAsJson =
                                match exampleValue with
                                | :? string -> (exampleValue.ToString())
                                | _ ->
                                    Microsoft.FSharpLu.Json.Compact.serialize exampleValue
                            yield valueAsJson
                }
                specExampleValues |> Seq.tryHead
        else None

    /// Get the example from the schema.
    /// 'None' will be returned if the example for an
    /// object or array cannot be successfully parsed.
    let tryGetSchemaExampleAsString (schema:NJsonSchema.JsonSchema) =
        tryGetSchemaExampleValue schema

    let tryParseJToken (exampleValue:String) =
        try
            JToken.Parse(exampleValue)
            |> Some
        with ex ->
            None

    let tryGetSchemaExampleAsJToken (schema:NJsonSchema.JsonSchema) =
        match tryGetSchemaExampleValue schema with
        | Some valueAsString ->
            tryParseJToken valueAsString
        | None -> None

    let getGrammarPrimitiveTypeWithDefaultValue (objectType:NJsonSchema.JsonObjectType)
                                                (format:string)
                                                (exampleValue:string option)
                                                (propertyName : string option)
                                                (trackParameters:bool) :
                                                (PrimitiveType * string * string option * string option) =
        let defaultTypeWithValue =
            match objectType with
            | NJsonSchema.JsonObjectType.String ->
                let defaultStringType =
                    PrimitiveType.String, DefaultPrimitiveValues.[PrimitiveType.String]
                if not (isNull format) then
                    match (format.ToLower()) with
                    | "uuid"
                    | "guid" ->
                        PrimitiveType.Uuid,
                        DefaultPrimitiveValues.[PrimitiveType.Uuid]
                    | "date-time" ->
                         PrimitiveType.DateTime,
                         DefaultPrimitiveValues.[PrimitiveType.DateTime]
                    | "double" ->
                        PrimitiveType.Number,
                        DefaultPrimitiveValues.[PrimitiveType.Number]
                    | _ ->
                        printfn "found unsupported format: %s" format
                        defaultStringType
                else
                    defaultStringType
            | NJsonSchema.JsonObjectType.Number ->
                PrimitiveType.Number,
                DefaultPrimitiveValues.[PrimitiveType.Number]
            | NJsonSchema.JsonObjectType.Integer ->
                PrimitiveType.Int,
                DefaultPrimitiveValues.[PrimitiveType.Int]
            | NJsonSchema.JsonObjectType.Boolean ->
                PrimitiveType.Bool,
                DefaultPrimitiveValues.[PrimitiveType.Bool]
            | NJsonSchema.JsonObjectType.Object ->
                PrimitiveType.Object,
                DefaultPrimitiveValues.[PrimitiveType.Object]
            | NJsonSchema.JsonObjectType.Array
            | _ ->
                raise (UnsupportedType (sprintf "%A is not a fuzzable primitive type.  Please make sure your Swagger file is valid." objectType))

        let (primitiveType, defaultValue) = defaultTypeWithValue
        let propertyName =
            if trackParameters then propertyName else None
        primitiveType, defaultValue, exampleValue, propertyName

    let getFuzzableValueForObjectType (objectType:NJsonSchema.JsonObjectType) (format:string) (exampleValue: string option) (propertyName: string option)
                                      (trackParameters:bool) =
        Fuzzable (getGrammarPrimitiveTypeWithDefaultValue objectType format exampleValue propertyName trackParameters)

    /// Get a boolean property from 'ExtensionData', if it exists.
    let getExtensionDataBooleanPropertyValue (extensionData:System.Collections.Generic.IDictionary<string, obj>) (extensionDataKeyName:string) =
        if isNull extensionData then
            None
        else
            match extensionData.Keys |> Seq.tryFind (fun x -> x = extensionDataKeyName) with
            | None -> None
            | Some v ->
                match Boolean.TryParse((extensionData.Item(v)).ToString()) with
                | (true, b) -> Some b
                | (false, _) ->
                    printfn "WARNING: property %s has invalid value for field %A, expected boolean" extensionDataKeyName v
                    None
    /// Determine whether a property is declared as 'readOnly'
    /// 'isReadOnly' is not exposed in NJsonSchema.  Instead, it appears
    /// in ExtensionData
    let propertyIsReadOnly (property:JsonSchemaProperty) =
        match getExtensionDataBooleanPropertyValue property.ExtensionData "readOnly" with
        | None -> property.IsReadOnly
        | Some v -> v

open SchemaUtilities

module SwaggerVisitors =

    let getFuzzableValueForProperty propertyName (propertySchema:NJsonSchema.JsonSchema) isRequired isReadOnly enumeration defaultValue (exampleValue:string option)
                                    (trackParameters:bool) =
        let payload =
            match propertySchema.Type with
                | NJsonSchema.JsonObjectType.String
                | NJsonSchema.JsonObjectType.Number
                | NJsonSchema.JsonObjectType.Integer
                | NJsonSchema.JsonObjectType.Boolean ->
                    match enumeration with
                    | None -> getFuzzableValueForObjectType propertySchema.Type propertySchema.Format exampleValue (Some propertyName) trackParameters
                    | Some ev ->
                        let enumValues = ev |> Seq.map (fun e -> string e) |> Seq.toList
                        let grammarPrimitiveType,_,exv,_ = getGrammarPrimitiveTypeWithDefaultValue propertySchema.Type propertySchema.Format exampleValue (Some propertyName) trackParameters
                        let defaultFuzzableEnumValue =
                            match enumValues with
                            | [] -> "null"
                            | h::rest -> h
                        Fuzzable (PrimitiveType.Enum (propertyName, grammarPrimitiveType, enumValues, defaultValue), defaultFuzzableEnumValue, exv, None)
                | NJsonSchema.JsonObjectType.Object
                | NJsonSchema.JsonObjectType.None ->
                    // Example of JsonObjectType.None: "content": {} without a type specified in Swagger.
                    // Let's treat these the same as Object.
                    getFuzzableValueForObjectType NJsonSchema.JsonObjectType.Object propertySchema.Format exampleValue (Some propertyName) trackParameters
                | NJsonSchema.JsonObjectType.File ->
                    // Fuzz it as a string.
                    Fuzzable (PrimitiveType.String, "file object", None, if trackParameters then Some propertyName else None)
                | nst ->
                    raise (UnsupportedType (sprintf "Unsupported type formatting: %A" nst))
        { LeafProperty.name = propertyName; payload = payload ;isRequired = isRequired ; isReadOnly = isReadOnly }

    let tryGetEnumeration (property:NJsonSchema.JsonSchema) =
        if property.IsEnumeration then
            // This must be converted to a list to make sure it is available for the duration of the compilation.
            Some (property.Enumeration |> Seq.map (id) |> Seq.toList) else None

    let tryGetDefault (property:NJsonSchema.JsonSchema) =
        if isNull property.Default || String.IsNullOrWhiteSpace (property.Default.ToString())
        then None
        else Some (property.Default.ToString())

    /// Add property name to the fuzzable payload
    /// This is used to track fuzzed parameter values
    let addTrackedParameterName (tree:Tree<LeafProperty, InnerProperty>) paramName trackParameters =
        if trackParameters then
            match tree with
            | LeafNode leafProperty ->
                let payload = leafProperty.payload
                match payload with
                | Fuzzable(a, b, c, _) ->
                    let payload = Fuzzable (a, b, c, Some paramName)
                    LeafNode { leafProperty with LeafProperty.payload = payload }
                | x -> tree
            | InternalNode (_,_) -> tree
        else tree

    module GenerateGrammarElements =

        /// Returns the specified property when the object contains it.
        /// Note: if the example object does not contain the property,
        let extractPropertyFromObject propertyName (objectType:NJsonSchema.JsonObjectType)
                                                   (exampleObj: JToken option) =
            if (String.IsNullOrWhiteSpace propertyName && objectType <> NJsonSchema.JsonObjectType.Array) then
                failwith (sprintf "non-array should always have a property name.  Property type: %A" objectType)

            let pv, includeProperty =
                match exampleObj with
                | Some ex ->
                    let exampleValue =
                        match objectType with
                        | NJsonSchema.JsonObjectType.Array ->
                            ex
                        | NJsonSchema.JsonObjectType.Object
                        | NJsonSchema.JsonObjectType.None
                        | NJsonSchema.JsonObjectType.String
                        | NJsonSchema.JsonObjectType.Number
                        | NJsonSchema.JsonObjectType.Integer
                        | NJsonSchema.JsonObjectType.Boolean ->
                            ex.SelectToken(propertyName)
                        | _ -> failwith "extractpropertyfromobject: invalid usage"
                    if isNull exampleValue then
                        // If the example is not found, ignore the property
                        None, false
                    else
                        (Some exampleValue), true
                | None ->
                    // This is the case when no example is provided.  TODO: assert this should never happen when 'useExamples' is true
                    // In such cases, all properties are included
                    None, true
            pv, includeProperty

        let extractPropertyFromArray (exampleObj: JToken option) =
            extractPropertyFromObject "" NJsonSchema.JsonObjectType.Array exampleObj

        let formatJTokenProperty primitiveType (v:JToken) =
            // Use Formatting.None to avoid unintended string formatting, for example
            // https://github.com/JamesNK/Newtonsoft.Json/issues/248

            let rawValue = v.ToString(Newtonsoft.Json.Formatting.None)

            match primitiveType with
            | _ when v.Type = JTokenType.Null -> null
            | PrimitiveType.String
            | PrimitiveType.DateTime
            | PrimitiveType.Enum (_, PrimitiveType.String, _, _)
            | PrimitiveType.Uuid ->
                // Remove the start and end quotes, which are preserved with 'Formatting.None'.
                if rawValue.Length > 1 then
                    match rawValue.[0], rawValue.[rawValue.Length-1] with
                    | '"', '"' ->
                        rawValue.[1..rawValue.Length-2]
                    | '"', _
                    | _, '"' ->
                        printfn "WARNING: example file contains malformed value in property %A.  The compiler does not currently support this.  Please modify the grammar manually to send the desired payload."
                                rawValue
                        rawValue
                    | _ -> rawValue
                else rawValue
            | _ -> rawValue

    module ExampleHelpers =

        /// Given a JSON array, returns the example value that should be used.
        let getArrayExamples (pv:JToken option) =
            match pv with
            | Some exv ->
                let maxArrayElementsFromExample = 5
                exv.Children() |> seq
                |> Seq.truncate maxArrayElementsFromExample
                |> Some
            | None -> None


        let tryGetArraySchemaExample (schema:NJsonSchema.JsonSchema) =
            // Check for local examples from the Swagger spec if external examples were not specified.
            let schemaExampleValue = tryGetSchemaExampleAsJToken schema
            let schemaArrayExamples = getArrayExamples schemaExampleValue

            if schemaArrayExamples.IsNone || schemaArrayExamples.Value |> Seq.isEmpty then
                None
            else
                schemaArrayExamples.Value
                |> Seq.map (fun example -> (Some example, true))
                |> Some

    let rec processProperty (propertyName, property:NJsonSchema.JsonSchemaProperty)
                            (propertyPayloadExampleValue: JToken option, generateFuzzablePayload:bool)
                            (trackParameters:bool)
                            (parents:NJsonSchema.JsonSchema list)
                            (cont: Tree<LeafProperty, InnerProperty> -> Tree<LeafProperty, InnerProperty>) =

        // If an example value was not specified, also check for a locally defined example
        // in the Swagger specification.
        match property.Type with
            | NJsonSchema.JsonObjectType.String
            | NJsonSchema.JsonObjectType.Number
            | NJsonSchema.JsonObjectType.Integer
            | NJsonSchema.JsonObjectType.Boolean ->
                let fuzzablePropertyPayload =
                    let propertySchema = (property :> NJsonSchema.JsonSchema)
                    let schemaExampleValue = SchemaUtilities.tryGetSchemaExampleAsString property
                    getFuzzableValueForProperty propertyName
                             propertySchema
                             property.IsRequired
                             (propertyIsReadOnly property)
                             (tryGetEnumeration propertySchema)
                             (tryGetDefault propertySchema)
                             schemaExampleValue
                             trackParameters
                let propertyPayload =
                    match propertyPayloadExampleValue with
                    | None ->
                        // If a payload example is not specified, generate a fuzzable payload.
                        fuzzablePropertyPayload
                    | Some v ->
                        let examplePropertyPayload =
                            match fuzzablePropertyPayload.payload with
                            | Fuzzable (primitiveType, defaultValue, _, propertyName) ->
                                let payloadValue = GenerateGrammarElements.formatJTokenProperty primitiveType v
                                // Replace the default payload with the example payload, preserving type information.
                                // 'generateFuzzablePayload' is specified a schema example is found for the parent
                                // object (e.g. an array).
                                if generateFuzzablePayload then
                                    Fuzzable (primitiveType, defaultValue, Some payloadValue, propertyName)
                                else
                                    Constant (primitiveType, payloadValue)
                            | _ -> raise (invalidOp(sprintf "invalid payload %A, expected fuzzable" fuzzablePropertyPayload))

                        { fuzzablePropertyPayload with payload = examplePropertyPayload }
                LeafNode propertyPayload
            | NJsonSchema.JsonObjectType.None ->
                // When the object type is 'None', simply pass through the example value ('propertyValue')
                // For example: the schema of a property whose schema is declared as a $ref will be visited here.
                // The example property value needs to be examined according to the 'ActualSchema', which
                // is passed through below.

                generateGrammarElementForSchema property.ActualSchema (propertyPayloadExampleValue, generateFuzzablePayload)
                                                trackParameters
                                                (property.IsRequired, (propertyIsReadOnly property))
                                                parents (fun tree ->
                    let innerProperty = { InnerProperty.name = propertyName
                                          payload = None
                                          propertyType = Property
                                          isRequired = true
                                          isReadOnly = (propertyIsReadOnly property) }
                    InternalNode (innerProperty, stn tree)
                    |> cont
                )
            | NJsonSchema.JsonObjectType.Array ->
                let innerArrayProperty =
                    {   InnerProperty.name = propertyName
                        payload = None; propertyType = Array
                        isRequired = true
                        isReadOnly = (propertyIsReadOnly property) }

                let arrayWithElements =
                    generateGrammarElementForSchema property (propertyPayloadExampleValue, generateFuzzablePayload)
                                                        trackParameters
                                                        (property.IsRequired, (propertyIsReadOnly property))
                                                        parents (fun tree -> tree)
                                                        |> cont
                // For tracked parameters, it is required to add the name to the fuzzable primitives
                // This name will not be added if the array elements are leaf nodes that do not have inner properties.
                match arrayWithElements with
                | InternalNode (n, tree) ->
                    let tree =
                        tree
                        |> Seq.map (fun elem -> addTrackedParameterName elem propertyName trackParameters)
                    InternalNode (innerArrayProperty, tree)
                | LeafNode _ ->
                    raise (invalidOp("An array should be an internal node."))
            | NJsonSchema.JsonObjectType.Object ->
                let objTree =
                    // This object may or may not have nested properties.
                    // Similar to type 'None', just pass through the object and it will be taken care of downstream.
                    generateGrammarElementForSchema property.ActualSchema (propertyPayloadExampleValue, generateFuzzablePayload) trackParameters
                                                    (property.IsRequired, (propertyIsReadOnly property))
                                                    parents (fun tree ->
                        // If the object has no properties, it should be set to its primitive type.
                        match tree with
                        | LeafNode l ->
                            LeafNode { l with name = propertyName }
                            |> cont
                        | InternalNode _ ->
                            let innerProperty = { InnerProperty.name = propertyName
                                                  payload = None
                                                  propertyType = Property // indicates presence of nested properties
                                                  isRequired = true
                                                  isReadOnly = (propertyIsReadOnly property) }
                            InternalNode (innerProperty, stn tree)
                            |> cont
                    )
                // For tracked parameters, it is required to add the name to the fuzzable primitives
                // This name will not be added if the object elements are leaf nodes that do not have inner properties.
                let objTree = addTrackedParameterName objTree propertyName trackParameters
                objTree
            | nst ->
                raise (UnsupportedType (sprintf "Found unsupported type in body parameters: %A" nst))

    and generateGrammarElementForSchema (schema:NJsonSchema.JsonSchema)
                                        (exampleValue:JToken option, generateFuzzablePayloadsForExamples:bool)
                                        (trackParameters:bool)
                                        (isRequired:bool, isReadOnly:bool)
                                        (parents:NJsonSchema.JsonSchema list)
                                        (cont: Tree<LeafProperty, InnerProperty> -> Tree<LeafProperty, InnerProperty>) =

        // As of NJsonSchema version 10, need to walk references explicitly.
        let rec getActualSchema (s:NJsonSchema.JsonSchema) =
            // Explicitly check for null rather than use 'HasReference' because the
            // property includes AllOf/OneOf/AnyOf in addition to direct references.
            if not (isNull s.Reference) then
                getActualSchema s.Reference
            else s

        let schema = getActualSchema schema

        // If a property is recursive, stop processing and treat the child property as an object.
        // Dependencies will use the parent, and fuzzing nested properties may be implemented later as an optimization.
        if parents |> List.contains schema then
            if exampleValue.IsSome then
                // TODO: need test case for this example.  Raise an exception to flag these cases.
                // Most likely, the current example value should simply be used in the leaf property
                raise (UnsupportedRecursiveExample (sprintf "%A" exampleValue))
            let leafProperty = { LeafProperty.name = ""; payload = Fuzzable (PrimitiveType.String, "", None, None); isRequired = true ; isReadOnly = false }
            LeafNode leafProperty
            |> cont
        else

            let declaredPropertyParameters =
                schema.Properties
                |> Seq.choose (fun item ->
                                    let name = item.Key
                                    // Just extract the property as a string.
                                    let exValue, includeProperty = GenerateGrammarElements.extractPropertyFromObject name NJsonSchema.JsonObjectType.String exampleValue
                                    if not includeProperty then None
                                    else
                                        Some (processProperty (name, item.Value)
                                                              (exValue, generateFuzzablePayloadsForExamples)
                                                              trackParameters
                                                              (schema::parents) id))
            let arrayProperties =
                if schema.IsArray then
                    // OpenAPI parsing succeeds when the array does not have an element type declared
                    // Check this here, and fail with an error.
                    if isNull schema.Item then
                        raise (ArgumentException("Invalid array schema: found array property without a declared element"))

                    // An example of this is an array type query parameter.
                    let arrayPayloadExampleValue, includeProperty = GenerateGrammarElements.extractPropertyFromArray exampleValue
                    if not includeProperty then
                        Seq.empty
                    else
                        let payloadArrayExamples = ExampleHelpers.getArrayExamples arrayPayloadExampleValue
                        match payloadArrayExamples with
                        | None ->
                            let schemaArrayExamples = ExampleHelpers.tryGetArraySchemaExample schema
                            match schemaArrayExamples with
                            | None ->
                                generateGrammarElementForSchema schema.Item.ActualSchema (None, false) trackParameters (isRequired, isReadOnly) (schema::parents) id
                                |> stn
                            | Some sae ->
                                sae |> Seq.map (fun (schemaExampleValue, generateFuzzablePayload) ->
                                                    generateGrammarElementForSchema schema.Item.ActualSchema
                                                                                    (schemaExampleValue, generateFuzzablePayload)
                                                                                    trackParameters
                                                                                    (isRequired, isReadOnly)
                                                                                    (schema::parents)
                                                                                    id
                                                )
                        | Some payloadArrayExamples when payloadArrayExamples |> Seq.isEmpty ->
                            Seq.empty
                        | Some payloadArrayExamples ->
                            let arrayElements =
                                payloadArrayExamples
                                |> Seq.map (fun example ->
                                                generateGrammarElementForSchema
                                                    schema.Item.ActualSchema
                                                    (Some example, false)
                                                    trackParameters
                                                    (isRequired, isReadOnly)
                                                    (schema::parents)
                                                    id |> stn)
                                |> Seq.concat
                            arrayElements
                else Seq.empty

            let allOfParameterSchemas =
                schema.AllOf
                |> Seq.map (fun ao -> ao, generateGrammarElementForSchema ao.ActualSchema (exampleValue, false) trackParameters (isRequired, isReadOnly) (schema::parents) id)

            let allOfProperties =
                allOfParameterSchemas
                |> Seq.choose (fun (ao, parameterObject) ->
                                    match parameterObject with
                                    | LeafNode leafProperty ->
                                        // If it possible that the schema is not declared directly, but only in terms of the
                                        // AllOf.  For example:
                                        // allOf:
                                        // - type: string
                                        // This case should be handled separately.
                                        None
                                    | InternalNode (i, children) ->
                                        Some children)
                |> Seq.concat

            let allOfSchema =
                allOfParameterSchemas
                |> Seq.choose (fun (ao, parameterObject) ->
                                match parameterObject with
                                | LeafNode leafProperty ->
                                    Some leafProperty
                                | InternalNode (i, children) ->
                                    None)
                |> Seq.tryHead

            // Note: 'AdditionalPropertiesSchema' is omitted here, because it should not have any required parameters.
            // This can be included as a later optimization to improve coverage.
            // Likewise for 'AdditionalItems'.

            let internalNodes =
                seq { yield declaredPropertyParameters
                      yield arrayProperties
                      yield allOfProperties
                    } |> Seq.concat

            if internalNodes |> Seq.isEmpty then
                // If there is an example, use it (constant) instead of the token
                match exampleValue with
                | None ->
                    let leafProperty =
                        if schema.Type = JsonObjectType.None && allOfSchema.IsSome then
                            allOfSchema.Value
                        else
                            // Check for local examples from the Swagger spec if external examples were not specified.
                            // A fuzzable payload with a local example as the default value will be generated.
                            let specExampleValue = tryGetSchemaExampleAsString schema
                            getFuzzableValueForProperty
                                ""
                                schema
                                isRequired
                                isReadOnly
                                (tryGetEnumeration schema) (*enumeration*)
                                (tryGetDefault schema) (*defaultValue*)
                                specExampleValue
                                trackParameters
                    LeafNode leafProperty
                    |> cont
                | Some v ->
                    // Either none of the above properties matched, or there are no properties and
                    // this is a leaf object.
                    let isLeafObject = (schema.Properties |> Seq.isEmpty &&
                                        not schema.IsArray &&
                                        schema.AllOf |> Seq.isEmpty)
                    if isLeafObject then
                        // If the schema type is undeclared here, set it to 'object'.
                        let schemaType =
                            if schema.Type = JsonObjectType.None then JsonObjectType.Object
                            else schema.Type
                        // Note: since the paramName is not available here, set it to 'None'.
                        // This will be fixed up from the parent level.
                        let primitiveType, defaultValue, _ , _ = getGrammarPrimitiveTypeWithDefaultValue schemaType schema.Format None None trackParameters

                        let leafPayload =
                            let exampleValue = GenerateGrammarElements.formatJTokenProperty primitiveType v
                            if generateFuzzablePayloadsForExamples then
                                FuzzingPayload.Fuzzable (primitiveType, defaultValue, Some exampleValue, None)
                            else
                                FuzzingPayload.Constant (primitiveType, exampleValue)

                        LeafNode ({ LeafProperty.name = ""
                                    payload = leafPayload
                                    isRequired = true
                                    isReadOnly = false })
                        |> cont
                    else
                        let propertyType =
                            if schema.IsArray then NestedType.Array
                            else NestedType.Object
                        // Cases like this arise when an allOf schema is visited, and the example does not contain
                        // any of the properties listed in the 'allOf'.
                        // Or, it could be due to an empty array specified as an example.
                        // Create an empty object
                        let innerProperty = { InnerProperty.name = ""
                                              payload = None
                                              propertyType = propertyType
                                              isRequired = true
                                              isReadOnly = false }
                        InternalNode (innerProperty, Seq.empty)
                        |> cont
            else
                let innerProperty = { InnerProperty.name = ""
                                      payload = None
                                      propertyType = if schema.IsArray then Array else Object
                                      isRequired = true
                                      isReadOnly = false }
                InternalNode (innerProperty, internalNodes)
                |> cont

