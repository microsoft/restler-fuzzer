// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

namespace Restler.Compiler

open System
open Restler.Grammar
open Tree
open Restler.Utilities.Operators
open Newtonsoft.Json.Linq
open NJsonSchema

type UnsupportedType (msg:string) =
    inherit Exception(msg)

type NullArraySchema (msg:string) =
    inherit Exception(msg)

type UnsupportedArrayExample (msg:string) =
    inherit Exception(msg)

type UnsupportedRecursiveExample (msg:string) =
    inherit Exception(msg)

module SchemaUtilities =

    let formatExampleValue (exampleObject:obj) = 
        Restler.Utilities.JsonSerialization.serialize exampleObject

    /// Get an example value as a string, either directly from the 'example' attribute or
    /// from the extension 'Examples' property.
    let tryGetSchemaExampleValue (schema:NJsonSchema.JsonSchema) =
        if not (isNull schema.Example) then
            Some (formatExampleValue schema.Example)
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
                            yield (formatExampleValue exampleValue)
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
                    | "date-time"
                    | "datetime "-> // Support both officially defined "date-time" and "datetime" because some specs use the latter
                         PrimitiveType.DateTime,
                         DefaultPrimitiveValues.[PrimitiveType.DateTime]
                    | "date" ->
                        PrimitiveType.Date,
                        DefaultPrimitiveValues.[PrimitiveType.Date]
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
        let primitiveType, defaultValue, exampleValue, propertyName =
            getGrammarPrimitiveTypeWithDefaultValue objectType format exampleValue propertyName trackParameters
        Fuzzable
            {
                primitiveType = primitiveType
                defaultValue = defaultValue
                exampleValue = exampleValue
                parameterName = propertyName
                dynamicObject = None
            }

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

    type CachedGrammarTree =
        {
            tree: Tree<LeafProperty, InnerProperty>
        }

    type Cycle =
        {
            root : JsonSchema
            parents : JsonSchema list
            members : JsonSchema list
        }

    type SchemaCache() =
        let cache =
            System.Collections.Concurrent.ConcurrentDictionary<NJsonSchema.JsonSchema, CachedGrammarTree>()

        let cycles =
            System.Collections.Generic.HashSet<Cycle>()

        /// Adds the specified cycle to the cache.
        member x.addCycle (schemaList:NJsonSchema.JsonSchema list) =
            let root = schemaList.[0]
            let members = schemaList |> Seq.skip 1 |> Seq.takeWhile (fun x -> x <> root) |> Seq.toList
            let members = root::members
            let length = members.Length
            let parents = schemaList |> Seq.skip (length + 1) |> Seq.toList
            let cycle =
                {
                    root = root
                    members = members
                    parents = parents
                }
            cycles.Add(cycle) |> ignore

        /// Gets the grammar element corresponding to the schema, if it exists
        member x.tryGet schema =
            match cache.TryGetValue(schema) with
            | (true, v ) -> Some v
            | (false, _ ) -> None

        /// Caches the specified schema. If an example is specified, the schema is not cached since
        /// each example is transformed to a different schema.
        member x.add schema (parents:JsonSchema list) grammarElement isExample =
            // Check if this schema is part of any cycles.
            // If yes, cache it if it is the root
            let cyclesWithSchema = cycles |> Seq.filter (fun cycle -> cycle.members |> Seq.contains schema)
            let cycleRoot =
                cyclesWithSchema
                |> Seq.filter (fun cycle -> cycle.root = schema && cycle.parents = parents)
                |> Seq.tryHead

            let shouldCache =
                not isExample && (cyclesWithSchema |> Seq.isEmpty || cycleRoot.IsSome)

            if shouldCache then
                cache.TryAdd(schema, { tree = grammarElement }) |> ignore

                // Remove the cycle from cycle tracking, since it's already been cached.
                if cycleRoot.IsSome then
                    cycles.Remove(cycleRoot.Value) |> ignore

    module GenerateGrammarElements =

        let formatJTokenProperty primitiveType (v:JToken) =
            // Use Formatting.None to avoid unintended string formatting, for example
            // https://github.com/JamesNK/Newtonsoft.Json/issues/248

            let rawValue = v.ToString(Newtonsoft.Json.Formatting.None)

            match primitiveType with
            | _ when v.Type = JTokenType.Null -> null
            | _ when rawValue.Length > 1 && (rawValue.[0] = ''' || rawValue.[0] =  '"') ->
                match rawValue.[0], rawValue.[rawValue.Length-1] with
                | '"', '"' ->
                    rawValue.[1..rawValue.Length-2]
                | '"', _
                | _, '"' ->
                    printfn "WARNING: example file contains malformed value in property %A.  The compiler does not currently support this.  Please modify the grammar manually to send the desired payload."
                            rawValue
                    rawValue
                | _ -> rawValue
            | _ -> rawValue

        /// Returns the specified property when the object contains it.
        /// Note: if the example object does not contain the property,
        let extractPropertyFromObject propertyName (objectType:NJsonSchema.JsonObjectType)
                                                   (exampleObj: JToken option)
                                                   (parents: NJsonSchema.JsonSchema list option) =
            if (String.IsNullOrWhiteSpace propertyName && objectType <> NJsonSchema.JsonObjectType.Array) then
                let message = sprintf "non-array should always have a property name.  Property type: %A" objectType
                let propertyInfo =
                    let parentPropertyNames =
                        match parents with
                        | None -> ""
                        | Some parents ->
                            parents
                            |> Seq.map (fun p -> match p with
                                                   | :? NJsonSchema.JsonSchemaProperty as jp ->
                                                        jp.Name
                                                   | _ -> "")
                            |> Seq.filter (fun x -> not (String.IsNullOrEmpty x))
                            |> String.concat "."
                    sprintf "Property name: %A, parent properties: %s" propertyName parentPropertyNames
                failwith (sprintf "%s %s" message propertyInfo)

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
            extractPropertyFromObject "" NJsonSchema.JsonObjectType.Array exampleObj None


    let getFuzzableValueForProperty propertyName (propertySchema:NJsonSchema.JsonSchema) 
                                    isRequired isReadOnly enumeration defaultValue 
                                    (exampleValue:JToken option)
                                    (trackParameters:bool) =
        let placeholderExampleValue = None

        let payload =
            match propertySchema.Type with
                | NJsonSchema.JsonObjectType.String
                | NJsonSchema.JsonObjectType.Number
                | NJsonSchema.JsonObjectType.Integer
                | NJsonSchema.JsonObjectType.Boolean ->
                    match enumeration with
                    | None -> getFuzzableValueForObjectType propertySchema.Type propertySchema.Format placeholderExampleValue (Some propertyName) trackParameters
                    | Some ev ->
                        let enumValues = ev |> Seq.map (fun e -> string e) |> Seq.toList
                        let grammarPrimitiveType,_,exv,_ = getGrammarPrimitiveTypeWithDefaultValue propertySchema.Type propertySchema.Format placeholderExampleValue (Some propertyName) trackParameters
                        let defaultFuzzableEnumValue =
                            match enumValues with
                            | [] -> "null"
                            | h::rest -> h
                        Fuzzable
                            {
                                primitiveType = PrimitiveType.Enum (propertyName, grammarPrimitiveType, enumValues, defaultValue)
                                defaultValue = defaultFuzzableEnumValue
                                exampleValue = exv
                                parameterName = None
                                dynamicObject = None
                            }
                | NJsonSchema.JsonObjectType.Object
                | NJsonSchema.JsonObjectType.None ->
                    // Example of JsonObjectType.None: "content": {} without a type specified in Swagger.
                    // Let's treat these the same as Object.
                    getFuzzableValueForObjectType NJsonSchema.JsonObjectType.Object propertySchema.Format placeholderExampleValue (Some propertyName) trackParameters
                | NJsonSchema.JsonObjectType.File ->
                    // Fuzz it as a string.
                    Fuzzable
                        {
                            primitiveType = PrimitiveType.String
                            defaultValue = "file object"
                            exampleValue = None
                            parameterName = if trackParameters then Some propertyName else None
                            dynamicObject = None
                        }
                | nst ->
                    raise (UnsupportedType (sprintf "Unsupported type formatting: %A" nst))

        let payload = 
            match payload with
            | Fuzzable fp ->
                let exv = 
                    match exampleValue with
                    | None -> None
                    | Some e ->
                        Some (GenerateGrammarElements.formatJTokenProperty fp.primitiveType e)
                Fuzzable { fp with exampleValue = exv }
            | _ -> raise (Exception "invalid case")
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
                | Fuzzable fp ->
                    let payload = Fuzzable { fp with parameterName = Some paramName }
                    LeafNode { leafProperty with LeafProperty.payload = payload }
                | x -> tree
            | InternalNode (_,_) -> tree
        else tree

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
                            (trackParameters:bool, jsonPropertyMaxDepth:int option)
                            (parents:NJsonSchema.JsonSchema list)
                            (schemaCache:SchemaCache)
                            (cont: Tree<LeafProperty, InnerProperty> -> Tree<LeafProperty, InnerProperty>) =

        let getPropertyExampleValue() = 
            // Currently, only one example value is available in NJsonSchema
            // TODO: check if multiple example values are supported through
            // extension properties.
            SchemaUtilities.tryGetSchemaExampleAsJToken (property :> NJsonSchema.JsonSchema)

        // If an example value was not specified, also check for a locally defined example
        // in the Swagger specification.
        match property.Type with
            | NJsonSchema.JsonObjectType.String
            | NJsonSchema.JsonObjectType.Number
            | NJsonSchema.JsonObjectType.Integer
            | NJsonSchema.JsonObjectType.Boolean ->

                let fuzzablePropertyPayload =
                    let propertySchema = (property :> NJsonSchema.JsonSchema)
                    let schemaExampleValue = getPropertyExampleValue()

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
                            | Fuzzable fp ->
                                let payloadValue = GenerateGrammarElements.formatJTokenProperty fp.primitiveType v
                                // Replace the default payload with the example payload, preserving type information.
                                // 'generateFuzzablePayload' is specified a schema example is found for the parent
                                // object (e.g. an array).
                                if generateFuzzablePayload then
                                    Fuzzable { fp with exampleValue = Some payloadValue }
                                else
                                    Constant (fp.primitiveType, payloadValue)
                            | _ -> raise (invalidOp(sprintf "invalid payload %A, expected fuzzable" fuzzablePropertyPayload))

                        { fuzzablePropertyPayload with payload = examplePropertyPayload }
                LeafNode propertyPayload
            | NJsonSchema.JsonObjectType.None ->
                // When the object type is 'None', simply pass through the example value ('propertyValue')
                // For example: the schema of a property whose schema is declared as a $ref will be visited here.
                // The example property value needs to be examined according to the 'ActualSchema', which
                // is passed through below.

                generateGrammarElementForSchema property.ActualSchema (propertyPayloadExampleValue, generateFuzzablePayload)
                                                (trackParameters, jsonPropertyMaxDepth)
                                                (property.IsRequired, (propertyIsReadOnly property))
                                                parents
                                                schemaCache (fun tree ->
                    let innerProperty = { InnerProperty.name = propertyName
                                          payload = None
                                          propertyType = Property
                                          isRequired = property.IsRequired
                                          isReadOnly = (propertyIsReadOnly property) }
                    InternalNode (innerProperty, stn tree)
                    |> cont
                )
            | NJsonSchema.JsonObjectType.Array ->
                let innerArrayProperty =
                    {   InnerProperty.name = propertyName
                        payload = None; propertyType = Array
                        isRequired = property.IsRequired
                        isReadOnly = (propertyIsReadOnly property) }

                let arrayWithElements =
                    generateGrammarElementForSchema property (propertyPayloadExampleValue, generateFuzzablePayload)
                                                        (trackParameters, jsonPropertyMaxDepth)
                                                        (property.IsRequired, (propertyIsReadOnly property))
                                                        parents
                                                        schemaCache (fun tree -> tree)
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
                    generateGrammarElementForSchema
                                property.ActualSchema
                                (propertyPayloadExampleValue, generateFuzzablePayload)
                                (trackParameters, jsonPropertyMaxDepth)
                                (property.IsRequired, (propertyIsReadOnly property))
                                parents
                                schemaCache (fun tree ->
                        // If the object has no properties, it should be set to its primitive type.
                        match tree with
                        | LeafNode l ->
                            LeafNode { l with name = propertyName }
                            |> cont
                        | InternalNode _ ->
                            let innerProperty = { InnerProperty.name = propertyName
                                                  payload = None
                                                  propertyType = Property // indicates presence of nested properties
                                                  isRequired = property.IsRequired
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
                                        (trackParameters:bool, jsonPropertyMaxDepth:int option)
                                        (isRequired:bool, isReadOnly:bool)
                                        (parents:NJsonSchema.JsonSchema list)
                                        (schemaCache:SchemaCache)
                                        (cont: Tree<LeafProperty, InnerProperty> -> Tree<LeafProperty, InnerProperty>) =

        // As of NJsonSchema version 10, need to walk references explicitly.
        let rec getActualSchema (s:NJsonSchema.JsonSchema) =
            // Explicitly check for null rather than use 'HasReference' because the
            // property includes AllOf/OneOf/AnyOf in addition to direct references.
            if not (isNull s.Reference) then
                getActualSchema s.Reference
            else s

        let schema = getActualSchema schema

        // Check if the schema has already been cached.  if yes, just return the result.
        let cachedProperty =
            schemaCache.tryGet schema

        // If a property is recursive, stop processing and treat the child property as an object.
        // Dependencies will use the parent, and fuzzing nested properties may be implemented later as an optimization.
        let foundCycle = parents |> List.contains schema
        if foundCycle || (jsonPropertyMaxDepth.IsSome && parents.Length >= jsonPropertyMaxDepth.Value) then

            if foundCycle && exampleValue.IsSome then
                // TODO: need test case for this example.  Raise an exception to flag these cases.
                // Most likely, the current example value should simply be used in the leaf property
                raise (UnsupportedRecursiveExample (sprintf "%A" exampleValue))

            let getValueForObjectType (s:JsonSchema) =
                match s.Type with
                | JsonObjectType.Object ->
                    // Do not insert a default fuzzable property for objects
                    Fuzzable
                        {
                            primitiveType = PrimitiveType.Object
                            defaultValue = "{ }"
                            exampleValue = None
                            parameterName = None
                            dynamicObject = None
                        }
                | JsonObjectType.Array ->
                    getFuzzableValueForObjectType s.Item.Type s.Format None None trackParameters
                | _ ->
                    getFuzzableValueForObjectType s.Type s.Format None None trackParameters
            let payload =
                match schema.Type with
                | JsonObjectType.Array ->
                    // get the type of the array element
                    if isNull schema.Item ||
                        schema.Item.Type = JsonObjectType.None ||
                        schema.Item.Type = JsonObjectType.Array then
                        // Generate an empty array
                        None
                    else
                        Some (getValueForObjectType schema.Item)
                | JsonObjectType.None ->
                    let fp =
                        {
                            primitiveType = PrimitiveType.Object
                            defaultValue = "{ }"
                            exampleValue = None
                            parameterName = None
                            dynamicObject = None
                        }
                    Some (Fuzzable fp)
                | _ ->
                    Some (getValueForObjectType schema)

            let grammarElement =
                match schema.Type with
                | JsonObjectType.Array ->
                    let leafProperties =
                        match payload with
                        | Some p ->
                            LeafNode
                                {
                                    LeafProperty.name = ""
                                    payload = p
                                    isRequired = true
                                    isReadOnly = false }
                            |> stn
                        | None ->
                            Seq.empty

                    let innerProperty =
                        {
                            InnerProperty.name = ""
                            isReadOnly = isReadOnly
                            isRequired = isRequired
                            propertyType = NestedType.Array
                            payload = None
                        }
                    InternalNode (innerProperty, leafProperties)
                | _ ->
                    let leafProperty =
                        {
                            LeafProperty.name = ""
                            payload = payload.Value
                            isRequired = isRequired
                            isReadOnly = isReadOnly }

                    LeafNode leafProperty
            if foundCycle then
                schemaCache.addCycle (schema::parents)
            grammarElement |> cont
        else if exampleValue.IsNone && cachedProperty.IsSome then
            cachedProperty.Value.tree |> cont
        else
            // If this schema has an example value, and there isn't a payload example already provided,
            // use the schema example value.
            // TODO: handle this for the cyclic case and move to the top of the function
            let exampleValue = 
                match exampleValue with
                | Some _ -> exampleValue
                | None ->
                    SchemaUtilities.tryGetSchemaExampleAsJToken schema
                    
            let declaredPropertyParameters =
                schema.Properties
                |> Seq.choose (fun item ->
                                    let name = item.Key
                                    // Just extract the property as a string.
                                    let exValue, includeProperty = GenerateGrammarElements.extractPropertyFromObject name NJsonSchema.JsonObjectType.String exampleValue (Some parents)
                                    if not includeProperty then None
                                    else
                                        Some (processProperty (name, item.Value)
                                                              (exValue, generateFuzzablePayloadsForExamples)
                                                              (trackParameters, jsonPropertyMaxDepth)
                                                              (schema::parents)
                                                              schemaCache id))
            let additionalPropertyParameters = 
                if isNull schema.AdditionalPropertiesSchema then Seq.empty
                else
                    let additionalPropertiesSchema = getActualSchema schema.AdditionalPropertiesSchema
                    additionalPropertiesSchema.Properties
                    |> Seq.choose (fun item ->
                                        let name = item.Key
                                        // Just extract the property as a string.
                                        let exValue, includeProperty = GenerateGrammarElements.extractPropertyFromObject name NJsonSchema.JsonObjectType.String exampleValue (Some parents)
                                        if not includeProperty then None
                                        else
                                            Some (processProperty (name, item.Value)
                                                                  (exValue, generateFuzzablePayloadsForExamples)
                                                                  (trackParameters, jsonPropertyMaxDepth)
                                                                  (schema::parents)
                                                                  schemaCache id))

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
                                generateGrammarElementForSchema
                                    schema.Item.ActualSchema
                                    (None, false)
                                    (trackParameters, jsonPropertyMaxDepth)
                                    (isRequired, isReadOnly)
                                    (schema::parents)
                                    schemaCache
                                    id
                                |> stn
                            | Some sae ->
                                sae |> Seq.map (fun (schemaExampleValue, generateFuzzablePayload) ->
                                                    generateGrammarElementForSchema schema.Item.ActualSchema
                                                                                    (schemaExampleValue, generateFuzzablePayload)
                                                                                    (trackParameters, jsonPropertyMaxDepth)
                                                                                    (isRequired, isReadOnly)
                                                                                    (schema::parents)
                                                                                    schemaCache
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
                                                    (Some example, true)
                                                    (trackParameters, jsonPropertyMaxDepth)
                                                    (isRequired, isReadOnly)
                                                    (schema::parents)
                                                    schemaCache
                                                    id |> stn)
                                |> Seq.concat
                            arrayElements
                else Seq.empty

            let allOfParameterSchemas =
                schema.AllOf
                |> Seq.map (fun ao -> ao, generateGrammarElementForSchema ao.ActualSchema (exampleValue, true) (trackParameters, jsonPropertyMaxDepth) (isRequired, isReadOnly) (schema::parents) schemaCache id)
                |> Seq.cache

            // For AnyOf, take the first schema.
            // Supporting multiple variants is future work.
            let anyOfParameterSchema =
                schema.AnyOf
                |> Seq.truncate 1
                |> Seq.map (fun ao -> ao, generateGrammarElementForSchema ao.ActualSchema (exampleValue, true) (trackParameters, jsonPropertyMaxDepth) (isRequired, isReadOnly) (schema::parents) schemaCache id)
                |> Seq.cache

            let getSchemaAndProperties schemas =
                let allProperties =
                    schemas
                    |> Seq.choose (fun (ao, parameterObject) ->
                                        match parameterObject with
                                        | LeafNode leafProperty ->
                                            None
                                        | InternalNode (i, children) ->
                                            Some children)
                    |> Seq.concat
                    |> Seq.cache

                // If it possible that the schema is not declared directly, but only in terms of the
                // AllOf or AnyOf.  For example:
                // allOf:
                // - type: string
                // This case needs to be handled separately.
                let schema =
                    schemas
                    |> Seq.choose (fun (ao, parameterObject) ->
                                    match parameterObject with
                                    | LeafNode leafProperty ->
                                        Some leafProperty
                                    | InternalNode (i, children) ->
                                        None)
                    |> Seq.tryHead
                allProperties, schema

            let allOfProperties, allOfSchema = getSchemaAndProperties allOfParameterSchemas
            let anyOfProperties, anyOfSchema = getSchemaAndProperties anyOfParameterSchema

            // Note: 'AdditionalPropertiesSchema' is omitted here, because it should not have any required parameters.
            // This can be included as a later optimization to improve coverage.
            // Likewise for 'AdditionalItems'.

            let internalNodes =
                seq { yield declaredPropertyParameters
                      yield additionalPropertyParameters
                      yield arrayProperties
                      yield allOfProperties
                      yield anyOfProperties
                    } |> Seq.concat |> Seq.cache

            if internalNodes |> Seq.isEmpty then
                // If there is an example, use it (constant) instead of the token
                match exampleValue with
                | None ->
                    let leafProperty =
                        if schema.Type = JsonObjectType.None && allOfSchema.IsSome then
                            allOfSchema.Value
                        else if schema.Type = JsonObjectType.None && anyOfSchema.IsSome then
                            anyOfSchema.Value
                        else
                            // Check for local examples from the Swagger spec if external examples were not specified.
                            // A fuzzable payload with a local example as the default value will be generated.
                            let specExampleValue = tryGetSchemaExampleAsJToken schema

                            getFuzzableValueForProperty
                                ""
                                schema
                                isRequired
                                isReadOnly
                                (tryGetEnumeration schema) (*enumeration*)
                                (tryGetDefault schema) (*defaultValue*)
                                specExampleValue
                                trackParameters
                    let grammarElement = LeafNode leafProperty
                    schemaCache.add schema parents grammarElement exampleValue.IsSome
                    grammarElement |> cont
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
                                FuzzingPayload.Fuzzable
                                    {
                                        primitiveType = primitiveType
                                        defaultValue = defaultValue
                                        exampleValue = Some exampleValue
                                        parameterName = None
                                        dynamicObject = None
                                    }
                            else
                                FuzzingPayload.Constant (primitiveType, exampleValue)

                        let grammarElement =
                            LeafNode ({ LeafProperty.name = ""
                                        payload = leafPayload
                                        isRequired = isRequired
                                        isReadOnly = isReadOnly })

                        schemaCache.add schema parents grammarElement exampleValue.IsSome
                        grammarElement |> cont
                    else
                        let propertyType =
                            if schema.IsArray then NestedType.Array
                            else NestedType.Object
                        // Cases like this arise when an allOf schema is visited, and the example does not contain
                        // any of the properties listed in the 'allOf'.
                        // Or, it could be due to an empty array specified as an example.
                        // Create an empty object
                        let grammarElement =
                            let innerProperty = { InnerProperty.name = ""
                                                  payload = None
                                                  propertyType = propertyType
                                                  isRequired = isRequired
                                                  isReadOnly = isReadOnly }
                            InternalNode (innerProperty, Seq.empty)
                        schemaCache.add schema parents grammarElement exampleValue.IsSome
                        grammarElement |> cont
            else
                let grammarElement =
                    let innerProperty = { InnerProperty.name = ""
                                          payload = None
                                          propertyType = if schema.IsArray then Array else Object
                                          isRequired = isRequired
                                          isReadOnly = isReadOnly }
                    // At the time this schema is added to the cache, the internalNodes above have not been traversed.
                    // Make sure they have been traversed first, for cycle detection.
                    let internalNodes = internalNodes |> Seq.toList
                    InternalNode (innerProperty, internalNodes)
                schemaCache.add schema parents grammarElement exampleValue.IsSome
                grammarElement |> cont
