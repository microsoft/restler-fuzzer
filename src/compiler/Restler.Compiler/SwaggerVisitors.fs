// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

namespace Restler.Compiler

open System
open Restler.Grammar
open Tree
open Restler.Utilities.Operators

exception UnsupportedType of string
exception NullArraySchema of string
exception UnsupportedArrayExample of string
exception UnsupportedRecursiveExample of string

module SchemaUtilities =
    let getGrammarPrimitiveTypeWithDefaultValue (objectType:NJsonSchema.JsonObjectType) (format:string) =
        match objectType with
        | NJsonSchema.JsonObjectType.String ->
            let defaultStringType = PrimitiveType.String, "fuzzstring" // Note: quotes are intentionally omitted.
            if not (isNull format) then
                match (format.ToLower()) with
                | "uuid"
                | "guid" ->
                    PrimitiveType.Uuid, "566048da-ed19-4cd3-8e0a-b7e0e1ec4d72" // Note: quotes are intentionally omitted.
                | "date-time" ->
                    PrimitiveType.DateTime, "2019-06-26T20:20:39+00:00" // Note: quotes are intentionally omitted.
                | "double" ->
                    PrimitiveType.Number, "1.23" // Note: quotes are intentionally omitted.
                | _ ->
                    printfn "found unsupported format: %s" format
                    defaultStringType
            else
                defaultStringType
        | NJsonSchema.JsonObjectType.Number ->
            PrimitiveType.Number, "1.23"
        | NJsonSchema.JsonObjectType.Integer ->
            PrimitiveType.Int, "1"
        | NJsonSchema.JsonObjectType.Boolean ->
            PrimitiveType.Bool, "true"
        | NJsonSchema.JsonObjectType.Object ->
            PrimitiveType.Object, "{ \"fuzz\": false }"
        | NJsonSchema.JsonObjectType.Array
        | _ ->
            raise (UnsupportedType (sprintf "%A is not a fuzzable primitive type.  Please make sure your Swagger file is valid." objectType))

    let getFuzzableValueForObjectType (objectType:NJsonSchema.JsonObjectType) (format:string) =
        Fuzzable (getGrammarPrimitiveTypeWithDefaultValue objectType format)

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

open SchemaUtilities

module SwaggerVisitors =
    open Newtonsoft.Json.Linq
    open NJsonSchema

    let getFuzzableValueForProperty propertyName (propertySchema:NJsonSchema.JsonSchema) isRequired isReadOnly enumeration defaultValue =

        let payload =
            match propertySchema.Type with
                | NJsonSchema.JsonObjectType.String
                | NJsonSchema.JsonObjectType.Number
                | NJsonSchema.JsonObjectType.Integer
                | NJsonSchema.JsonObjectType.Boolean ->
                    match enumeration with
                    | None -> getFuzzableValueForObjectType propertySchema.Type propertySchema.Format
                    | Some ev ->
                        let enumValues = ev |> Seq.map (fun e -> string e) |> Seq.toList
                        let grammarPrimitiveType, _ = getGrammarPrimitiveTypeWithDefaultValue propertySchema.Type propertySchema.Format
                        let defaultFuzzableEnumValue =
                            match enumValues with
                            | [] -> "null"
                            | h::rest -> h
                        Fuzzable (PrimitiveType.Enum (grammarPrimitiveType, enumValues, defaultValue), defaultFuzzableEnumValue)
                | NJsonSchema.JsonObjectType.Object
                | NJsonSchema.JsonObjectType.None ->
                    // Example of JsonObjectType.None: "content": {} without a type specified in Swagger.
                    // Let's treat these the same as Object.
                    getFuzzableValueForObjectType NJsonSchema.JsonObjectType.Object propertySchema.Format
                | NJsonSchema.JsonObjectType.File ->
                    // Fuzz it as a string.
                    Fuzzable (PrimitiveType.String, "file object")
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



    module GenerateGrammarElements =
        /// Returns the specified property when the object contains it.
        /// Note: if the example object does not contain the property,
        let extractPropertyFromObject propertyName (objectType:NJsonSchema.JsonObjectType) (exampleObj: JToken option) =
            if (String.IsNullOrWhiteSpace propertyName && objectType <> NJsonSchema.JsonObjectType.Array) then
                failwith "non-array should always have a property name"
            let pv, includeProperty =
                match exampleObj with
                | Some ex ->
                    let exampleValue =
                        match objectType with
                        | NJsonSchema.JsonObjectType.Array ->
                            // For array examples, extract the first element if it exists.
                            if ex.HasValues then ex.First
                            else ex
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
            | PrimitiveType.Enum (PrimitiveType.String, _, _)
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



    let rec processProperty (propertyName, property:NJsonSchema.JsonSchemaProperty)
                        (propertyValue: JToken option)
                        (parents:NJsonSchema.JsonSchema list)
                        (cont: Tree<LeafProperty, InnerProperty> -> Tree<LeafProperty, InnerProperty>) =
        // 'isReadOnly' is not correctly initialized in NJsonSchema.  Instead, it appears
        // in ExtensionData
        let propertyIsReadOnly (property:NJsonSchema.JsonSchemaProperty) =
            match getExtensionDataBooleanPropertyValue property.ExtensionData "readOnly" with
            | None -> property.IsReadOnly
            | Some v -> v

        match property.Type with
            | NJsonSchema.JsonObjectType.String
            | NJsonSchema.JsonObjectType.Number
            | NJsonSchema.JsonObjectType.Integer
            | NJsonSchema.JsonObjectType.Boolean ->
                let propertyPayload =
                    let propertySchema = (property :> NJsonSchema.JsonSchema)

                    getFuzzableValueForProperty propertyName
                             propertySchema
                             property.IsRequired
                             (propertyIsReadOnly property)
                             (tryGetEnumeration propertySchema)
                             (tryGetDefault propertySchema)

                match propertyValue with
                | None -> 
                    LeafNode propertyPayload
                    |> cont
                | Some v ->
                    let examplePayload =
                        match propertyPayload.payload with
                        | Fuzzable (primitiveType, _) ->
                            // Replace the default payload with the example payload, preserving type information.
                            Constant (primitiveType, GenerateGrammarElements.formatJTokenProperty primitiveType v)
                        | _ -> raise (invalidOp(sprintf "invalid payload %A, expected fuzzable" propertyValue))

                    LeafNode { propertyPayload with payload = examplePayload }
                    |> cont

            | NJsonSchema.JsonObjectType.None ->
                // When the object type is 'None', simply pass through the example value ('propertyValue')
                // For example: the schema of a property whose schema is declared as a $ref will be visited here.
                // The example property value needs to be examined according to the 'ActualSchema', which
                // is passed through below.

                generateGrammarElementForSchema property.ActualSchema propertyValue parents (fun tree ->
                    let innerProperty = { InnerProperty.name = propertyName
                                          payload = None
                                          propertyType = Property
                                          isRequired = true
                                          isReadOnly = (propertyIsReadOnly property) }
                    InternalNode (innerProperty, stn tree)
                    |> cont
                )
            | NJsonSchema.JsonObjectType.Array ->
                let pv, includeProperty = GenerateGrammarElements.extractPropertyFromObject propertyName property.Type propertyValue
                if not includeProperty then
                    // TODO: need test case for this example.  Raise an exception to flag these cases.
                    raise (UnsupportedArrayExample (sprintf "Property name: %s" propertyName))
                else
                    // If the example is an empty array, just create a leaf property for it.
                    if propertyValue.IsSome && not propertyValue.Value.HasValues then
                        let leafProperty = { LeafProperty.name = propertyName
                                             payload = Constant (PrimitiveType.Object, GenerateGrammarElements.formatJTokenProperty PrimitiveType.Object pv.Value)
                                             isRequired = true
                                             isReadOnly = (propertyIsReadOnly property) }
                        LeafNode leafProperty
                        |> cont
                    else
                        // Exit gracefully in case the Swagger is not valid and does not declare the array schema
                        if isNull property.Item then
                            raise (NullArraySchema "Make sure the array definition has an element type in Swagger.")
                        generateGrammarElementForSchema property.Item.ActualSchema pv parents (fun tree ->
                            let innerProperty = { InnerProperty.name = propertyName; payload = None; propertyType = Array
                                                  isRequired = true
                                                  isReadOnly = (propertyIsReadOnly property) }
                            InternalNode (innerProperty, stn tree)
                            |> cont
                        )
            | NJsonSchema.JsonObjectType.Object ->
                // This object may or may not have nested properties.
                // Similar to type 'None', just pass through the object and it will be taken care of downstream.
                generateGrammarElementForSchema property.ActualSchema propertyValue parents (fun tree ->
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
            | nst ->
                raise (UnsupportedType (sprintf "Found unsupported type in body parameters: %A" nst))

    and generateGrammarElementForSchema (schema:NJsonSchema.JsonSchema)
                                            (exampleValue:JToken option)
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
            let leafProperty = { LeafProperty.name = ""; payload = Fuzzable (PrimitiveType.String, ""); isRequired = true ; isReadOnly = false }
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
                                        Some (processProperty (name, item.Value) exValue (schema::parents) id))

            let arrayProperties =
                if schema.IsArray then
                    // An example of this is an array type query parameter.
                    // TODO: still need a way to include all array elements, as a config option.
                    let exValue, includeProperty = GenerateGrammarElements.extractPropertyFromArray exampleValue
                    if not includeProperty then Seq.empty
                    else
                        generateGrammarElementForSchema schema.Item.ActualSchema exValue (schema::parents) id |> stn
                else Seq.empty

            let allOfParameterSchemas =
                schema.AllOf
                |> Seq.map (fun ao -> ao, generateGrammarElementForSchema ao.ActualSchema exampleValue (schema::parents) id)

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
                    if schema.Type = JsonObjectType.None && allOfSchema.IsSome then
                        LeafNode allOfSchema.Value
                        |> cont
                    else
                        LeafNode (getFuzzableValueForProperty
                                        ""
                                        schema
                                        true (*IsRequired*)
                                        false (*IsReadOnly*)
                                        (tryGetEnumeration schema) (*enumeration*)
                                        (tryGetDefault schema) (*defaultValue*))
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

                        let primitiveType,_ = getGrammarPrimitiveTypeWithDefaultValue schemaType schema.Format

                        LeafNode ({ LeafProperty.name = ""
                                    payload = FuzzingPayload.Constant (primitiveType, GenerateGrammarElements.formatJTokenProperty primitiveType v)
                                    isRequired = true
                                    isReadOnly = false })
                        |> cont
                    else

                        // Cases like this arise when an allOf schema is visited, and the example does not contain
                        // any of the properties listed in the 'allOf'.
                        // Create an empty object
                        let innerProperty = { InnerProperty.name = ""
                                              payload = None
                                              propertyType = NestedType.Object
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

