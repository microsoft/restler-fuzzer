// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.CodeGenerator.Python

open System
open Restler.Grammar
open Restler.Utilities.Operators
open Newtonsoft.Json.Linq

[<Literal>]
let TAB = @"    "
let RETURN = @"\r\n"
let SPACE = @" "

type UnsupportedType (msg:string) =
    inherit Exception(msg)

exception UnsupportedAccessPath

module Types =
    type RequestPrimitiveTypeData =
        {
            defaultValue : string
            isQuoted : bool
            exampleValue : string option
            trackedParameterName: string option
        }

    type DynamicObjectWriter =
        | DynamicObjectWriter of string

    /// RESTler grammar built-in types
    /// IMPORTANT ! All primitives must be supported in restler/engine/primitives.py
    type RequestPrimitiveType =
        | Restler_static_string_constant of string
        | Restler_static_string_variable of string * bool
        | Restler_static_string_jtoken_delim of string
        | Restler_fuzzable_string of RequestPrimitiveTypeData * DynamicObjectWriter option
        | Restler_fuzzable_datetime of RequestPrimitiveTypeData * DynamicObjectWriter option
        | Restler_fuzzable_date of RequestPrimitiveTypeData * DynamicObjectWriter option
        | Restler_fuzzable_object of RequestPrimitiveTypeData * DynamicObjectWriter option
        | Restler_fuzzable_delim of RequestPrimitiveTypeData
        | Restler_fuzzable_uuid4 of RequestPrimitiveTypeData * DynamicObjectWriter option
        | Restler_fuzzable_group of RequestPrimitiveTypeData * DynamicObjectWriter option
        | Restler_fuzzable_bool of RequestPrimitiveTypeData * DynamicObjectWriter option
        | Restler_fuzzable_int of RequestPrimitiveTypeData * DynamicObjectWriter option
        | Restler_fuzzable_number of RequestPrimitiveTypeData * DynamicObjectWriter option
        | Restler_multipart_formdata of string
        | Restler_custom_payload of RequestPrimitiveTypeData * DynamicObjectWriter option
        | Restler_custom_payload_header of string * DynamicObjectWriter option
        | Restler_custom_payload_query of string * DynamicObjectWriter option
        /// (Payload name, dynamic object writer name)
        | Restler_custom_payload_uuid4_suffix of string * bool * DynamicObjectWriter option
        | Restler_refreshable_authentication_token of string
        | Restler_basepath of string
        | Shadow_values of string
        | Response_parser of string

open Types

module NameGenerators =
    let generateDynamicObjectVariableDefinition responseAccessPathParts (requestId:RequestId) =
        let varName = (DynamicObjectNaming.generateDynamicObjectVariableName requestId (Some responseAccessPathParts) "_")
        sprintf "%s = dependencies.DynamicVariable(\"%s\")" varName varName

    let generateDynamicObjectOrderingConstraintVariableDefinition (sourceRequestId:RequestId) (targetRequestId:RequestId) =
        let varName = (DynamicObjectNaming.generateOrderingConstraintVariableName sourceRequestId targetRequestId "_")
        sprintf "%s = dependencies.DynamicVariable(\"%s\")" varName varName


    let generateProducerEndpointResponseParserFunctionName (requestId:RequestId) =
        sprintf "parse_%s" (DynamicObjectNaming.generateDynamicObjectVariableName requestId None "")

// Gets the RESTler primitive that corresponds to the specified fuzzing payload
let rec getRestlerPythonPayload (payload:FuzzingPayload) (isQuoted:bool) : RequestPrimitiveType list =
    let getPrimitivePayload p =
        match p with
        | Constant (t,v) ->
            Restler_static_string_constant v
        | Fuzzable fp ->
            let v = fp.defaultValue
            let exv = fp.exampleValue
            let parameterName = fp.parameterName
            let dynamicObject = if fp.dynamicObject.IsSome then Some (DynamicObjectWriter fp.dynamicObject.Value.variableName) else None
            match fp.primitiveType with
            | Bool ->
                Restler_fuzzable_bool ({ defaultValue = v ; isQuoted = false ; exampleValue = exv ; trackedParameterName = parameterName }, dynamicObject)
            | PrimitiveType.DateTime ->
                Restler_fuzzable_datetime ({ defaultValue = v ; isQuoted = isQuoted ; exampleValue = exv ; trackedParameterName = parameterName }, dynamicObject)
            | PrimitiveType.Date ->
                Restler_fuzzable_date ({ defaultValue = v ; isQuoted = isQuoted ; exampleValue = exv ; trackedParameterName = parameterName }, dynamicObject)

            | PrimitiveType.String ->
                Restler_fuzzable_string ({ defaultValue = v ; isQuoted = isQuoted ; exampleValue = exv ; trackedParameterName = parameterName }, dynamicObject)
            | PrimitiveType.Object -> Restler_fuzzable_object ({ defaultValue = v ; isQuoted = false ; exampleValue = exv  ; trackedParameterName = parameterName  }, dynamicObject)
            | Int -> Restler_fuzzable_int ({ defaultValue = v ; isQuoted = false; exampleValue = exv ; trackedParameterName = parameterName }, dynamicObject)

            | Number -> Restler_fuzzable_number ({ defaultValue = v ; isQuoted = false ; exampleValue = exv  ; trackedParameterName = parameterName }, dynamicObject)
            | Uuid ->
                Restler_fuzzable_uuid4 ({ defaultValue = v ; isQuoted = isQuoted ; exampleValue = exv ; trackedParameterName = parameterName }, dynamicObject)
            | PrimitiveType.Enum (enumPropertyName, _, enumeration, defaultValue) ->
                let defaultStr =
                    match defaultValue with
                    | Some v -> sprintf ", default_enum=\"%s\"" v
                    | None -> ""
                let groupValue =
                    (sprintf "\"%s\", [%s] %s "
                             enumPropertyName
                             (enumeration |> List.map (fun s -> sprintf "'%s'" s) |> String.concat ",")
                             defaultStr
                    )
                Restler_fuzzable_group (
                    { defaultValue = groupValue ; isQuoted = isQuoted ; exampleValue = exv ; trackedParameterName = parameterName }, dynamicObject)
        | Custom c ->
            let dynamicObject = if c.dynamicObject.IsSome then Some (DynamicObjectWriter c.dynamicObject.Value.variableName) else None
            match c.payloadType with
            | CustomPayloadType.String ->
                Restler_custom_payload ({ defaultValue = c.payloadValue ; isQuoted = isQuoted ; exampleValue = None ; trackedParameterName = None }, dynamicObject)
            | CustomPayloadType.UuidSuffix ->
                Restler_custom_payload_uuid4_suffix (c.payloadValue, isQuoted, dynamicObject)
            | CustomPayloadType.Header ->
                Restler_custom_payload_header (c.payloadValue, dynamicObject)
            | CustomPayloadType.Query ->
                Restler_custom_payload_query (c.payloadValue, dynamicObject)
        | DynamicObject dv ->
            Restler_static_string_variable (sprintf "%s.reader()" dv.variableName, isQuoted)
        | PayloadParts p ->
            raise (invalidArg "p" "expected primitive payload")

    match payload with
    | PayloadParts parts ->
        parts |> List.map (fun part -> getRestlerPythonPayload part false (*isQuoted*))
              |> List.concat
    | p -> [ getPrimitivePayload p ]

/// Generate the RESTler grammar for a request parameter
let generatePythonParameter includeOptionalParameters parameterSource parameterKind (requestParameter:RequestParameter) =
    let (parameterName, parameterPayload, parameterSerialization) =
        requestParameter.name, requestParameter.payload, requestParameter.serialization

    let formatPropertyName name =
        if String.IsNullOrEmpty name then
            Restler_static_string_constant ""
        else
            Restler_static_string_constant (sprintf "\"%s\":" name)

    let formatQueryParameterName name =
        Restler_static_string_constant (sprintf "%s=" name)

    let formatHeaderParameterName name =
        Restler_static_string_constant (sprintf "%s: " name)

    let getTabIndentedLineStart level =
        if level > 0 then
            let tabs = [1..level] |> List.map (fun x -> TAB) |> String.Concat
            Some ("\n" + tabs)
        else
            None

    let formatJsonBodyParameter (propertyName:string)
                                (propertyType:NestedType)
                                (namePayloadSeq:RequestPrimitiveType list option)
                                (innerProperties:RequestPrimitiveType list seq)
                                (tabLevel:int) =
        // Pretty-printing is only required for the body
        let tabSeq =
            match getTabIndentedLineStart tabLevel with
            | None -> []
            | Some s -> [ Restler_static_string_constant s ]
        match namePayloadSeq with
        | Some nps ->
            tabSeq @ nps
        | None ->
            // The payload is not specified at this level, so use the one specified at lower levels.
            // The inner properties must be comma separated
            let cs = innerProperties
                     // Filter empty elements, which are the result of filtered child properties
                     |> Seq.filter (fun p -> p.Length > 0)
                     |> Seq.mapi (fun i s ->
                                      if i > 0 && not (s |> List.isEmpty) then
                                          [
                                            [ Restler_static_string_jtoken_delim "," ]
                                            s
                                          ]
                                          |> List.concat
                                      else s)
                     |> Seq.concat
                     |> List.ofSeq
            tabSeq
            @ [formatPropertyName propertyName]
            @ tabSeq
            @ [
                Restler_static_string_jtoken_delim
                    (match propertyType with
                        | Object -> "{"
                        | Array -> "["
                        | Property -> "")
            ]
            @ cs
            @ tabSeq
            @ [
                Restler_static_string_jtoken_delim
                    (match propertyType with
                        | Object -> "}"
                        | Array -> "]"
                        | Property -> "")
            ]

    let formatQueryObjectParameters (parameterName:string) (innerProperties:RequestPrimitiveType list seq) =
        raise (NotImplementedException("Objects in query parameters are not supported yet."))

    let formatHeaderObjectParameters (parameterName:string) (innerProperties:RequestPrimitiveType list seq) =
        // The default is "style: simple, explode: false"
        raise (NotImplementedException("Objects in header parameters are not supported yet."))

    let formatHeaderArrayParameters (parameterName:string) (innerProperties:RequestPrimitiveType list seq) =
        let cs =
            innerProperties
            |> Seq.filter (fun ip -> ip.Length > 0)
            |> Seq.mapi (fun i arrayItemPrimitives ->
                            [
                                if i > 0 then
                                    match requestParameter.serialization with
                                    | None ->
                                        [ Restler_static_string_constant "," ]
                                    | Some ps when ps.style = Simple ->
                                        [ Restler_static_string_constant "," ]
                                    | Some s ->
                                        raise (NotImplementedException (sprintf "Serialization type %A is not implemented yet." s))
                                arrayItemPrimitives
                            ]
                            |> List.concat)
            |> Seq.concat
            |> List.ofSeq
        [
            [ formatHeaderParameterName parameterName ]
            cs
        ]
        |> List.concat

    let formatQueryArrayParameters (parameterName:string) (innerProperties:RequestPrimitiveType list seq) =
        // The default is "style: form, explode: true"
        let expOption =
            match requestParameter.serialization with
            | None -> true
            | Some eo -> eo.explode

        let cs =
            innerProperties
            |> Seq.filter (fun ip -> ip.Length > 0)
            |> Seq.mapi (fun i arrayItemPrimitives ->
                            [
                                // If 'explode': true is specified, the array name is printed before each array item
                                if expOption then
                                    if i > 0 then
                                        [ Restler_static_string_constant "&" ]
                                    [ formatQueryParameterName parameterName ]
                                    arrayItemPrimitives
                                else
                                    if i > 0 then
                                        match requestParameter.serialization with
                                        | None ->
                                            [ Restler_static_string_constant "," ]
                                        | Some ps when ps.style = Form ->
                                            [ Restler_static_string_constant "," ]
                                        | Some s ->
                                            raise (NotImplementedException (sprintf "Serialization type %A is not implemented yet." s))
                                    arrayItemPrimitives
                            ]
                            |> List.concat)
            |> Seq.concat
            |> List.ofSeq
        if (not expOption) || cs |> List.isEmpty then
            [
                [ formatQueryParameterName parameterName ]
                cs
            ]
            |> List.concat
        else
            cs

    /// Format a header parameter that is either an array or object
    /// See https://swagger.io/docs/specification/serialization/#query.
    /// Any other type of serialization (e.g. encoding and passing complex json objects)
    /// will need to be added as a config option for RESTler.
    let formatNestedHeaderParameter (parameterName:string)
                                    (propertyType:NestedType)
                                    (namePayloadSeq:RequestPrimitiveType list option)
                                    (innerProperties:RequestPrimitiveType list seq) =
        match namePayloadSeq with
        | Some nps -> nps
        | None ->
            match propertyType with
                | Object ->
                    formatHeaderObjectParameters parameterName innerProperties
                | Array ->
                    formatHeaderArrayParameters parameterName innerProperties
                | Property ->
                    raise (ArgumentException("Invalid context for property type."))

    /// Format a query parameter that is either an array or object
    /// See https://swagger.io/docs/specification/serialization/#query.
    /// Any other type of serialization (e.g. encoding and passing complex json objects)
    /// will need to be added as a config option for RESTler.
    let formatNestedQueryParameter (parameterName:string)
                                   (propertyType:NestedType)
                                   (namePayloadSeq:RequestPrimitiveType list option)
                                   (innerProperties:RequestPrimitiveType list seq) =
        match namePayloadSeq with
        | Some nps -> nps
        | None ->
            match propertyType with
                | Object ->
                    formatQueryObjectParameters parameterName innerProperties
                | Array ->
                    formatQueryArrayParameters parameterName innerProperties
                | Property ->
                    let message = sprintf "Nested properties in query parameters are not supported yet. Property name: %s." parameterName
                    raise (NotImplementedException(message))

    let visitLeaf level (p:LeafProperty) =
        let rec isPrimitiveTypeQuoted primitiveType isNullValue =
            match primitiveType with
            | _ when isNullValue -> false
            | PrimitiveType.String
            | PrimitiveType.DateTime
            | PrimitiveType.Date
            | PrimitiveType.Uuid ->
                true
            | PrimitiveType.Enum (_, enumType, _, _) ->
                isPrimitiveTypeQuoted enumType isNullValue
            | PrimitiveType.Object
            | PrimitiveType.Int
            | PrimitiveType.Bool
            | PrimitiveType.Number ->
                false

        let includeProperty =
            // Exclude 'readonly' parameters
            not p.isReadOnly && (p.isRequired || includeOptionalParameters)
        // Parameters from an example payload are always included
        if parameterSource = ParameterPayloadSource.Examples || includeProperty then
            let nameSeq =
                if String.IsNullOrEmpty p.name then
                    if level = 0 && parameterKind = ParameterKind.Query then
                        [ formatQueryParameterName requestParameter.name ]
                    else if level = 0 && parameterKind = ParameterKind.Header then
                        [ formatHeaderParameterName requestParameter.name ]
                    else
                        List.empty
                else
                    [ formatPropertyName p.name ]

            let needQuotes, isFuzzable, isDynamicObject =
                match p.payload with
                | FuzzingPayload.Custom c ->
                    let isFuzzable = true
                    // 'needQuotes' must be based on the underlying type of the payload.
                    let needQuotes =
                        (not c.isObject) &&
                        (isPrimitiveTypeQuoted c.primitiveType false)
                    needQuotes, isFuzzable, false
                | FuzzingPayload.Constant (PrimitiveType.String, s) ->
                    // TODO: improve the metadata of FuzzingPayload.Constant to capture whether
                    // the constant represents an object,
                    // rather than relying on the formatting behavior of JToken.ToString.
                    not (isNull s) &&
                    not (s.Contains("\n")),
                    false, false
                | FuzzingPayload.Constant (primitiveType, v) ->
                    isPrimitiveTypeQuoted primitiveType (isNull v),
                    false, false
                | FuzzingPayload.Fuzzable fp ->
                    // Note: this is a current RESTler limitation -
                    // fuzzable values may not be set to null without changing the grammar.
                    isPrimitiveTypeQuoted fp.primitiveType false,
                    true, false
                | FuzzingPayload.DynamicObject dv ->
                    isPrimitiveTypeQuoted dv.primitiveType false,
                    false, true
                | FuzzingPayload.PayloadParts (_) ->
                    false, false, false

            let tabSeq =
                if parameterKind = ParameterKind.Body then
                    match getTabIndentedLineStart level with
                    | None -> []
                    | Some s -> [ Restler_static_string_constant s ]
                else
                    []

            let payloadSeq =
                [
                    // If the value is a constant, quotes are inserted at compile time.
                    // If the value is a fuzzable, quotes are inserted at run time, because
                    // the user may choose to fuzz with quoted or unquoted values.
                    let needStaticStringQuotes =
                        parameterKind = ParameterKind.Body &&
                        needQuotes && not isFuzzable && not isDynamicObject
                    if needStaticStringQuotes then
                        yield Restler_static_string_constant "\""

                    let isQuoted = parameterKind = ParameterKind.Body && needQuotes &&
                                    (isFuzzable || isDynamicObject)
                    for k in getRestlerPythonPayload p.payload isQuoted do
                        yield k

                    if needStaticStringQuotes then
                        yield Restler_static_string_constant "\""
                ]

            [ tabSeq ; nameSeq ; payloadSeq ] |> List.concat
        else
            []

    let visitInner level (p:InnerProperty) (innerProperties: RequestPrimitiveType list seq) =
        let includeProperty =
            // Exclude 'readonly' parameters
            not p.isReadOnly && (p.isRequired || includeOptionalParameters)
        // Parameters from an example payload are always included
        if parameterSource = ParameterPayloadSource.Examples || includeProperty then
            // Check for the custom payload
            let nameAndCustomPayloadSeq =
                match p.payload with
                | Some payload ->
                    // Use the payload specified at this level.
                    let namePayloadSeq =
                        (formatPropertyName p.name) ::
                        // Because this is a custom payload for an object, it should not be quoted.
                        (getRestlerPythonPayload payload false (*isQuoted*))
                    Some namePayloadSeq
                | None -> None

            match parameterKind with
            | ParameterKind.Body ->
                formatJsonBodyParameter p.name p.propertyType nameAndCustomPayloadSeq innerProperties level
            | ParameterKind.Query ->
                formatNestedQueryParameter parameterName p.propertyType nameAndCustomPayloadSeq innerProperties
            | ParameterKind.Header ->
                formatNestedHeaderParameter parameterName p.propertyType nameAndCustomPayloadSeq innerProperties

            | ParameterKind.Path ->
                raise (InvalidOperationException("Path parameters must not be formatted here."))
        else
            []

    let getTreeLevel parentLevel (p:InnerProperty) =
        parentLevel + 1

    let payloadPrimitives = Tree.cataCtx visitLeaf visitInner getTreeLevel 0 parameterPayload
    payloadPrimitives

/// Generates the python restler grammar definitions corresponding to the request
let generatePythonFromRequestElement includeOptionalParameters (requestId:RequestId) (e:RequestElement) =
    match e with
    | Method m ->
        [Restler_static_string_constant (sprintf "%s%s" (m.ToString().ToUpper()) SPACE)]
    | RequestElement.BasePath bp ->
        [ Restler_basepath bp ]
    | RequestElement.Path parts ->
        let queryStartIndex =
            match requestId.xMsPath with
            | None -> parts.Length
            | Some _ -> parts |> List.findIndex(fun x -> x = Constant (PrimitiveType.String, "?"))
        let x = parts
                |> List.map(fun p -> getRestlerPythonPayload p false (*isQuoted*))
                |> List.concat
        // Handle the case of '/'
        if x |> List.isEmpty || queryStartIndex = 0 then
            [ Restler_static_string_constant "/" ] @ x
        else
            x
    | HeaderParameters (parameterSource, hp) ->
        match hp with
        | ParameterList hp ->
            let parameters =
                hp |> List.ofSeq
                   |> List.map (fun p ->
                                  let pythonElementList = generatePythonParameter includeOptionalParameters
                                                                                  parameterSource ParameterKind.Header p
                                  if pythonElementList.Length > 0 then
                                      pythonElementList @
                                      [ Restler_static_string_constant RETURN ]
                                  else
                                    []
                                )
                   |> List.concat
            parameters
        | _ ->
            raise (UnsupportedType (sprintf "This request parameters payload type is not supported: %A" hp))
    | QueryParameters (parameterSource, qp) ->
        match qp with
        | ParameterList qp ->
            let parameters =
                qp |> List.ofSeq
                   |> List.map (fun p -> generatePythonParameter includeOptionalParameters parameterSource ParameterKind.Query p)
                   |> List.filter (fun primitives -> primitives.Length > 0)
                   |> List.mapi (fun i primitives ->
                                    if i > 0 then
                                        [
                                            yield Restler_static_string_constant "&"
                                            yield! primitives
                                        ]
                                    else primitives
                               )
                   |> List.concat
            if parameters |> List.isEmpty then
                []
            else
                [
                    // Special case: if the path of this request already contains a query (for example,
                    // if the endpoint source is from x-ms-paths), then append rather than start the query list
                    //
                    if requestId.xMsPath.IsSome then
                        yield Restler_static_string_constant "&"
                    else
                        yield Restler_static_string_constant "?"
                    yield! parameters
                ]
        | _ ->
            raise (UnsupportedType (sprintf "This request parameters payload type is not supported: %A" qp))
    | Body (parameterSource, b) ->
        match b with
        | ParameterList bp ->
            let parameters =
                bp |> List.ofSeq
                   |> List.map (fun p -> generatePythonParameter includeOptionalParameters parameterSource ParameterKind.Body p)
                   |> List.filter (fun primitives -> primitives.Length > 0)
                   |> List.mapi (fun i primitive->
                                    if i > 0 then
                                        (Restler_static_string_jtoken_delim ",") :: primitive
                                    else
                                        primitive
                               )
                   |> List.concat
            if parameters |> List.isEmpty then []
            else
                (Restler_static_string_constant RETURN) :: parameters
        | Example (FuzzingPayload.Constant (PrimitiveType.String, exString)) ->
            if String.IsNullOrEmpty exString then []
            else
                [
                    Restler_static_string_constant RETURN
                    Restler_static_string_constant exString
                ]
        | Example (FuzzingPayload.Custom customBodyPayload) ->
            (Restler_static_string_constant RETURN)::
            getRestlerPythonPayload (FuzzingPayload.Custom customBodyPayload) false
        | _ ->
            raise (UnsupportedType (sprintf "This request parameters payload type is not supported: %A." b))

    | Token t->
        match t with
        | tokStr ->
            [Restler_static_string_constant (sprintf "%s%s" tokStr RETURN)]
    | RefreshableToken ->
        [Restler_refreshable_authentication_token "authentication_token_tag"]
    | Headers h ->
        h |> List.map (fun (name, content) ->
            Restler_static_string_constant (sprintf "%s: %s%s" name content RETURN))
    | HttpVersion v->
        [Restler_static_string_constant (sprintf "%sHTTP/%s%s" SPACE v RETURN)]
    | RequestDependencyData rd ->
        if rd.IsSome then
            let responseParser = rd.Value.responseParser
            let generateWriterStatement var =
               sprintf "%s.writer()" var
            let generateReaderStatement var =
               sprintf "%s.reader()" var

            let variablesReferencedInParser =
                match responseParser with
                | Some rp -> rp.writerVariables @ rp.headerWriterVariables
                | None -> []
            let parserStatement =
                match variablesReferencedInParser with
                | [] -> ""
                | writerVariable::rest ->
                   sprintf @"'parser': %s,"
                        (NameGenerators.generateProducerEndpointResponseParserFunctionName writerVariable.requestId)
            let postSend =
                let allWriterVariableStatements =
                    let writerVariableStatements =
                        variablesReferencedInParser @ rd.Value.inputWriterVariables
                        |> List.map (fun producerWriter ->
                                         generateWriterStatement (DynamicObjectNaming.generateDynamicObjectVariableName producerWriter.requestId (Some producerWriter.accessPathParts) "_"))

                    let orderingConstraintVariableStatements =
                        rd.Value.orderingConstraintWriterVariables
                        |> List.map (fun constraintVariable ->
                                           generateWriterStatement (DynamicObjectNaming.generateOrderingConstraintVariableName constraintVariable.sourceRequestId constraintVariable.targetRequestId "_"))

                    writerVariableStatements @ orderingConstraintVariableStatements

                let readerVariablesList =
                    let allReaderVariableStatements =
                        rd.Value.orderingConstraintReaderVariables
                        |> List.map (fun constraintVariable ->
                                           generateReaderStatement (DynamicObjectNaming.generateOrderingConstraintVariableName constraintVariable.sourceRequestId constraintVariable.targetRequestId "_"))

                    allReaderVariableStatements
                    // TODO: generate this ID only once if possible.
                    |> List.map (fun stmt ->
                                      let indent = Seq.init 4 (fun _ -> TAB) |> String.concat ""
                                      sprintf "%s%s" indent stmt
                                      )
                    |> String.concat ",\n"

                let writerVariablesList =
                    allWriterVariableStatements
                    // TODO: generate this ID only once if possible.
                    |> List.map (fun stmt ->
                                      let indent = Seq.init 4 (fun _ -> TAB) |> String.concat ""
                                      sprintf "%s%s" indent stmt
                                      )
                    |> String.concat ",\n"

                let preSendElement =
                    if readerVariablesList.Length > 0 then
                        sprintf @"
        'pre_send':
        {
            'dependencies':
            [
%s
            ]
        }
"
                            readerVariablesList
                    else
                        ""

                let postSendElement =
                    if writerVariablesList.Length > 0 then
                        sprintf @"
        'post_send':
        {
            %s
            'dependencies':
            [
%s
            ]
        }
"
                            parserStatement
                            writerVariablesList
                    else
                        ""

                sprintf @"
    {
%s
    }"
                    ([ preSendElement ; postSendElement ]
                     |> List.filter (fun x -> not (String.IsNullOrWhiteSpace x))
                     |> String.concat ",\n")

            [Response_parser postSend]
        else
            []
    | Delimiter ->
        [Restler_static_string_constant RETURN]

/// Generates the python restler grammar definitions corresponding to the request
let generatePythonFromRequest (request:Request) includeOptionalParameters mergeStaticStrings =
    /// Gets either the schema or examples payload present in the list
    let getParameterPayload queryOrBodyParameters =
        match queryOrBodyParameters
              |> List.tryFind (fun (payloadSource, _) ->
                                 payloadSource = ParameterPayloadSource.Examples || payloadSource = ParameterPayloadSource.Schema) with
        | Some (payloadSource, ParameterList pList) -> payloadSource, pList
        | _ -> ParameterPayloadSource.Schema, Seq.empty

    /// Merges all the dictionary custom payloads present in the list and returns them
    let getCustomParameterPayload (queryOrBodyParameters:(ParameterPayloadSource * RequestParametersPayload) list) =
        queryOrBodyParameters
        |> List.fold (fun (currentPList) (payloadSource, pList) ->
                            let parameterList =
                                if payloadSource = ParameterPayloadSource.DictionaryCustomPayload then
                                    match pList with
                                    | ParameterList pl -> pl
                                    | Example _ ->
                                        // filter out the example here ; it will be handled elsewhere.
                                        Seq.empty
                                else
                                    Seq.empty
                            [parameterList ; currentPList] |> Seq.concat)
                        Seq.empty

    /// Gets the parameter list payload for query, header, or body parameters
    let getParameterListPayload (parameters:(ParameterPayloadSource * RequestParametersPayload) list) =
        let payloadSource, declaredPayload = getParameterPayload parameters
        let injectedPayload = getCustomParameterPayload parameters
        payloadSource, ParameterList ([declaredPayload ; injectedPayload] |> Seq.concat)

    let getExamplePayload (queryOrBodyParameters:(ParameterPayloadSource * RequestParametersPayload) list) =
        queryOrBodyParameters
        |> Seq.choose (fun (payloadSource, payloadValue) ->
                            if payloadSource = ParameterPayloadSource.DictionaryCustomPayload then
                                match payloadValue with
                                | ParameterList _ -> None
                                | Example example ->
                                    Some example
                            else None)
        |> Seq.tryHead

    let getMergedStaticStringSeq (strList:string seq) =

        let str =
            strList
            |> Seq.map (fun s ->
                            if isNull s then
                                "null"
                            else s)
            |> Seq.mapi (fun i line -> if i < Seq.length strList - 1 &&
                                            // If both this and the next entry are blank lines,
                                            // the current one is not needed for indentation. Remove it.
                                            line.StartsWith("\n") &&
                                            String.IsNullOrWhiteSpace (Seq.item (i+1) strList) then ""
                                        else line)
            |> String.concat ""
        // Special handling is needed for the ending quote, because
        // it cannot appear in the last line of a triple-quoted Python multi-line string.
        // Example:
        //   Not valid: "id":"""");
        //   Transformed below to valid:
        //               "id":""");
        //      static_string('"');
        if str.EndsWith("\"") then
            [
                yield (str.[0..str.Length-2]
                       |> RequestPrimitiveType.Restler_static_string_constant)
                yield ("\"" |> RequestPrimitiveType.Restler_static_string_constant)
            ]
        else
            [str |> RequestPrimitiveType.Restler_static_string_constant]

    let requestElements = [
        Method request.method
        BasePath request.basePath
        Path request.path
        QueryParameters (getParameterListPayload request.queryParameters)
        HttpVersion request.httpVersion
        Headers request.headers
        HeaderParameters (getParameterListPayload request.headerParameters)
        (match request.token with
            | TokenKind.Refreshable -> RefreshableToken
            | (TokenKind.Static token) -> Token (token))
        Body (let payloadSource, parameterListPayload = getParameterListPayload request.bodyParameters
              let examplePayload = getExamplePayload request.bodyParameters
              // Either an example or parameter list should be present, but not both.
              // For example, additional parameters will not be combined with an 'Example' payload which
              // the user expects to be used without modification.
              match examplePayload with
              | Some p -> payloadSource, Example p  // TODO: it's unclear what the 'source' of this example is
              | None -> payloadSource, parameterListPayload)
        Delimiter
        RequestDependencyData request.dependencyData
    ]

    requestElements
    |> List.map (fun requestElement ->
                    let primitives = generatePythonFromRequestElement includeOptionalParameters request.id requestElement
                    match requestElement with
                    | Body _ when mergeStaticStrings && primitives |> List.length > 1 ->
                        let filteredPrimitives =
                            primitives
                            // Filter empty strings
                            |> List.filter (fun requestPrimitive ->
                                                match requestPrimitive with
                                                | RequestPrimitiveType.Restler_static_string_jtoken_delim s ->
                                                    not (String.IsNullOrEmpty s)
                                                | RequestPrimitiveType.Restler_static_string_constant s ->
                                                    // Note: do not filter null strings, which indicate a 'null'
                                                    // payload value
                                                    isNull s || not (String.IsNullOrEmpty s)
                                                | _ -> true
                                            )

                        let newPrimitiveSeq, nextList =
                            filteredPrimitives
                            // WARNING: Do not combine the first two elements (RETURN and {) in order for the payload
                            // body checker to recognize the start of the body
                            // TODO: this should be removed and a special element for the start of the body should be
                            // used
                            |> List.skip 2
                            // Combine static strings
                            |> List.fold (fun (newPrimitiveSeq: RequestPrimitiveType ResizeArray, nextList: string ResizeArray) requestPrimitive ->
                                            match nextList |> Seq.tryLast with
                                            | None ->
                                                match requestPrimitive with
                                                | RequestPrimitiveType.Restler_static_string_jtoken_delim s
                                                | RequestPrimitiveType.Restler_static_string_constant s ->
                                                    let newList = ResizeArray<_>()
                                                    newList.Add(s)
                                                    (newPrimitiveSeq, newList)
                                                | _ ->
                                                    newPrimitiveSeq.Add(requestPrimitive)
                                                    (newPrimitiveSeq, ResizeArray<_>())
                                            | Some prev ->
                                                match requestPrimitive with
                                                | RequestPrimitiveType.Restler_static_string_jtoken_delim currentDelim ->
                                                    nextList.Add(currentDelim)
                                                    (newPrimitiveSeq, nextList)
                                                | RequestPrimitiveType.Restler_static_string_constant currentStr ->
                                                    // The two strings should be combined.
                                                    nextList.Add(currentStr)
                                                    (newPrimitiveSeq, nextList)
                                                | _ ->
                                                    // Merge the list and append to the sequence
                                                    // Also append the current element
                                                    let mergedStaticStringSeq = getMergedStaticStringSeq nextList
                                                    newPrimitiveSeq.AddRange(mergedStaticStringSeq)
                                                    newPrimitiveSeq.Add(requestPrimitive)
                                                    (newPrimitiveSeq, ResizeArray())

                                        ) (ResizeArray<_>(), ResizeArray<_>())
                        // Process the remaining elements in the body
                        let mergedStaticStringSeq = getMergedStaticStringSeq nextList

                        // Add back the first two elements
                        (filteredPrimitives |> List.take 2)
                        @ (newPrimitiveSeq |> List.ofSeq)
                        @ mergedStaticStringSeq

                    | _ ->
                        primitives
               )
    |> List.concat

/// The definitions required for the RESTler python grammar.
/// Note: the purpose of this type is to aid in generating the grammar file.
/// This is not intended to be able to represent arbitrary python.
type PythonGrammarElement =
    /// Definition of a python import statement
    /// from <A> import <B>
    | Import of (string option * string)

    /// Definitions of the dynamic objects
    /// _api_blog_posts_id = dependencies.DynamicVariable("_api_blog_posts_id")
    | DynamicObjectDefinition of string

    /// The response parsing functions
    | ResponseParserDefinition of string

    /// Definition of the request collection
    | RequestCollectionDefinition of string

    /// Requests that will be fuzzed
    | Requests of string list

    /// Comment
    | Comment of string

let getDynamicObjectDefinitions (writerVariables:seq<DynamicObjectWriterVariable>) =
    seq {
        // First, define the dynamic variables initialized by the response parser
        for writerVariable in writerVariables do
            yield PythonGrammarElement.DynamicObjectDefinition
                    (NameGenerators.generateDynamicObjectVariableDefinition writerVariable.accessPathParts writerVariable.requestId)
    }
    |> Seq.toList

let getOrderingConstraintDynamicObjectDefinitions (writerVariables:seq<OrderingConstraintVariable>) =
    seq {
        // First, define the dynamic variables initialized by the response parser
        for writerVariable in writerVariables do
            yield PythonGrammarElement.DynamicObjectDefinition
                    (NameGenerators.generateDynamicObjectOrderingConstraintVariableDefinition writerVariable.sourceRequestId writerVariable.targetRequestId)
    }
    |> Seq.distinct
    |> Seq.toList


type ResponseVariableKind =
    | Body
    | Header

let getResponseParsers (requests: Request list) =

    let random = System.Random(0)

    let dependencyData = requests |> Seq.choose (fun r -> r.dependencyData)
    let responseParsers = dependencyData |> Seq.choose (fun d -> d.responseParser)

    // First, define the dynamic variables initialized by the response parser
    let dynamicObjectDefinitionsFromBodyResponses =
        getDynamicObjectDefinitions (responseParsers |> Seq.map (fun r -> r.writerVariables |> seq) |> Seq.concat)

    let dynamicObjectDefinitionsFromHeaderResponses =
        getDynamicObjectDefinitions (responseParsers |> Seq.map (fun r -> r.headerWriterVariables |> seq) |> Seq.concat)

    let dynamicObjectDefinitionsFromInputParameters =
        getDynamicObjectDefinitions (dependencyData |> Seq.map (fun d -> d.inputWriterVariables |> seq) |> Seq.concat)

    let dynamicObjectDefinitionsFromOrderingConstraints =
        getOrderingConstraintDynamicObjectDefinitions (dependencyData |> Seq.map (fun d -> d.orderingConstraintWriterVariables |> seq) |> Seq.concat)

    let formatParserFunction (parser:ResponseParser) =
        let functionName =
            let writerVariables = parser.writerVariables @ parser.headerWriterVariables
            NameGenerators.generateProducerEndpointResponseParserFunctionName writerVariables.[0].requestId

        // Go through the producer fields and parse them all out of the response
        // STOPPED HERE:
        // also do 'if true' for header parsing and body parsing where 'true' is if there are actually variables to parse out of there.
        let getResponseParsingStatements (writerVariables:DynamicObjectWriterVariable list) (variableKind:ResponseVariableKind) =
            [
                for w in writerVariables do
                    let dynamicObjectVariableName = DynamicObjectNaming.generateDynamicObjectVariableName w.requestId (Some w.accessPathParts) "_"
                    let tempVariableName = sprintf "temp_%d" (random.Next(10000))
                    let emptyInitStatement = sprintf "%s = None" tempVariableName
                    let getPath (part:string) =
                        if part.StartsWith("[") then
                            // TODO: how should subsequent elements be accessed?  Random access
                            // may be desirable in fuzz mode.
                            "[0]"
                        else
                            sprintf "[\"%s\"]" part

                    let parsingStatement =
                        let dataSource, accessPath =
                            match variableKind with
                            | ResponseVariableKind.Body -> "data", w.accessPathParts.path
                            | ResponseVariableKind.Header -> "headers", w.accessPathParts.path |> Array.truncate 1

                        let extractData =
                            accessPath
                            |> Array.map getPath
                            |> String.concat ""

                        sprintf "%s = str(%s%s)" tempVariableName dataSource extractData
                    let initCheck = sprintf "if %s:" tempVariableName
                    let initStatement = sprintf "dependencies.set_variable(\"%s\", %s)"
                                            dynamicObjectVariableName
                                            tempVariableName
                    let booleanConversionStatement =
                        if w.primitiveType = PrimitiveType.Bool then
                            sprintf "%s = %s.lower()" tempVariableName tempVariableName
                            |> Some
                        else None
                    yield (emptyInitStatement, parsingStatement, initCheck, initStatement, tempVariableName, booleanConversionStatement)
            ]

        let responseBodyParsingStatements = getResponseParsingStatements parser.writerVariables ResponseVariableKind.Body
        let responseHeaderParsingStatements = getResponseParsingStatements parser.headerWriterVariables ResponseVariableKind.Header

        let parsingStatementWithTryExcept parsingStatement (booleanConversionStatement:string option) =
            sprintf "
        try:
            %s
            %s
        except Exception as error:
            # This is not an error, since some properties are not always returned
            pass
"                parsingStatement
                (if booleanConversionStatement.IsSome then booleanConversionStatement.Value else "")


        let getParseBodyStatement() =
            """
        try:
            data = json.loads(data)
        except Exception as error:
            raise ResponseParsingException("Exception parsing response, data was not valid json: {}".format(error))"""

        let getHeaderParsingStatements responseHeaderParsingStatements =
            let parsingStatements =
                responseHeaderParsingStatements
                 |> List.map(fun (_,parsingStatement,_,_,_,booleanConversionStatement) ->
                                parsingStatementWithTryExcept parsingStatement booleanConversionStatement)
                 |> String.concat "\n"

            sprintf """
    if headers:
        # Try to extract dynamic objects from headers
%s
        pass
        """
                parsingStatements

        let functionDefinition = sprintf "
def %s(data, **kwargs):
    \"\"\" Automatically generated response parser \"\"\"
    # Declare response variables
%s
%s
    if 'headers' in kwargs:
        headers = kwargs['headers']


    # Parse body if needed
    if data:
%s
        pass

    # Try to extract each dynamic object
%s

%s
    # If no dynamic objects were extracted, throw.
    if not (%s):
        raise ResponseParsingException(\"Error: all of the expected dynamic objects were not present in the response.\")

    # Set dynamic variables
%s
"
                                        functionName
                                        // Response variable declarations (body and header)
                                        (responseBodyParsingStatements
                                         |> List.map(fun (emptyInitStatement,_,_,_,_,_) -> (TAB + emptyInitStatement)) |> String.concat "\n")
                                        (responseHeaderParsingStatements
                                         |> List.map(fun (emptyInitStatement,_,_,_,_,_) -> (TAB + emptyInitStatement)) |> String.concat "\n")

                                        // Statement to parse the body
                                        (if parser.writerVariables.Length > 0 then getParseBodyStatement() else "")

                                        (responseBodyParsingStatements
                                         |> List.map(fun (_,parsingStatement,_,_,_,booleanConversionStatement) ->
                                                        parsingStatementWithTryExcept parsingStatement booleanConversionStatement)
                                         |> String.concat "\n")

                                        (if parser.headerWriterVariables.Length > 0 then getHeaderParsingStatements responseHeaderParsingStatements else "")

                                        (responseBodyParsingStatements @ responseHeaderParsingStatements
                                         |> List.map(fun (_,_,_,_,tempVariableName,_) ->
                                                        tempVariableName)
                                        |> String.concat " or ")

                                        (responseBodyParsingStatements @ responseHeaderParsingStatements
                                         |> List.map(fun (_,_,initCheck,initStatement,_,_) ->
                                                        (TAB + initCheck + "\n" + TAB + TAB + initStatement)) |> String.concat "\n")

        PythonGrammarElement.ResponseParserDefinition functionDefinition

    let responseParsersWithParserFunction =
        responseParsers |> Seq.filter (fun rp -> rp.writerVariables.Length + rp.headerWriterVariables.Length > 0)
    [
        yield! dynamicObjectDefinitionsFromBodyResponses
        yield! dynamicObjectDefinitionsFromHeaderResponses
        yield! dynamicObjectDefinitionsFromInputParameters
        yield! dynamicObjectDefinitionsFromOrderingConstraints
        yield! (responseParsersWithParserFunction |> Seq.map (fun r -> formatParserFunction r) |> Seq.toList)
    ]

let getRequests(requests:Request list) includeOptionalParameters =
    let quoteStringForPythonGrammar (s:string) =
        let s, delim =
            if s.Contains("\n") then s, "\"\"\""
            else if s.StartsWith("\"") then
                // For grammar readability, a double quoted string or single double quote
                // is enclosed in single quotes rather than escaped.
                //
                // Escape single quotes
                if s.Length > 1 then
                    s.Replace("'", "\\'"), "'"
                else s, "'"
            // Special case already escaped quoted strings (this will be the case for example values).
            // Assume the entire string is quoted in this case.
            else if s.Contains("\\\"") then
                s, "\"\"\""
            else if s.Contains("\"") then
                s.Replace("\"", "\\\""), "\""
            else s, "\""
        s, delim

    let formatRestlerPrimitive p =
        let getExamplePrimitiveParameter exv =
            match exv with
            | None -> ""
            | Some str ->
                if isNull str then
                    sprintf ", examples=[None]"
                else
                    let exStr, exDelim = quoteStringForPythonGrammar str
                    let quotedStr = sprintf "%s%s%s" exDelim exStr exDelim
                    sprintf ", examples=[%s]" quotedStr

        let getTrackedParamPrimitiveParameter paramName =
            match paramName with
            | None -> ""
            | Some str ->
                let exStr, exDelim = quoteStringForPythonGrammar str
                let quotedStr = sprintf "%s%s%s" exDelim exStr exDelim
                sprintf ", param_name=%s" quotedStr

        let formatDynamicObjectVariable (dynamicObject:DynamicObjectWriter option) =
            match dynamicObject with
            | None -> ""
            | Some (DynamicObjectWriter v) ->
                sprintf ", writer=%s.writer()" v

        let str =
            match p with
            | Restler_static_string_jtoken_delim s ->
                if not (isNull s) && String.IsNullOrEmpty s then ""
                else
                    let s, delim = quoteStringForPythonGrammar s
                    sprintf "primitives.restler_static_string(%s%s%s)" delim s delim
            | Restler_static_string_constant s ->
                // Filter out any empty strings that were generated, since they are a no-op in the Python grammar.

                if not (isNull s) && String.IsNullOrEmpty s then ""
                else
                    let s, delim =
                        let rawValue =
                            if isNull s then
                                "null"
                            else s
                        quoteStringForPythonGrammar rawValue
                    sprintf "primitives.restler_static_string(%s%s%s)" delim s delim
            | Restler_static_string_variable (s, isQuoted) ->
                sprintf "primitives.restler_static_string(%s, quoted=%s)"
                        s
                        (if isQuoted then "True" else "False")
            | Restler_fuzzable_string (s, dynamicObject) ->
                if String.IsNullOrEmpty s.defaultValue then
                    printfn "ERROR: fuzzable strings should not be empty.  Skipping."
                    ""
                else
                    let str, delim = quoteStringForPythonGrammar s.defaultValue
                    let quotedDefaultString =
                        sprintf "%s%s%s" delim str delim
                    let exampleParameter = getExamplePrimitiveParameter s.exampleValue
                    let trackedParamName = getTrackedParamPrimitiveParameter s.trackedParameterName
                    sprintf "primitives.restler_fuzzable_string(%s, quoted=%s%s%s)"
                             quotedDefaultString
                             (if s.isQuoted then "True" else "False")
                             exampleParameter
                             trackedParamName
            | Restler_fuzzable_group (s, dynamicObject) ->
                sprintf "primitives.restler_fuzzable_group(%s,quoted=%s%s)"
                        s.defaultValue
                        (if s.isQuoted then "True" else "False")
                        (getExamplePrimitiveParameter s.exampleValue)
            | Restler_fuzzable_int (s, dynamicObject) ->
                sprintf "primitives.restler_fuzzable_int(\"%s\"%s%s%s)"
                        s.defaultValue
                        (getExamplePrimitiveParameter s.exampleValue)
                        (getTrackedParamPrimitiveParameter s.trackedParameterName)
                        (formatDynamicObjectVariable dynamicObject)
            | Restler_fuzzable_number (s, dynamicObject) ->
                sprintf "primitives.restler_fuzzable_number(\"%s\"%s%s%s)"
                        s.defaultValue
                        (getExamplePrimitiveParameter s.exampleValue)
                        (getTrackedParamPrimitiveParameter s.trackedParameterName)
                        (formatDynamicObjectVariable dynamicObject)
            | Restler_fuzzable_bool (s, dynamicObject) ->
                sprintf "primitives.restler_fuzzable_bool(\"%s\"%s%s%s)"
                        s.defaultValue
                        (getExamplePrimitiveParameter s.exampleValue)
                        (getTrackedParamPrimitiveParameter s.trackedParameterName)
                        (formatDynamicObjectVariable dynamicObject)
            | Restler_fuzzable_datetime (s, dynamicObject) ->
                sprintf "primitives.restler_fuzzable_datetime(\"%s\", quoted=%s%s%s%s)"
                        s.defaultValue
                        (if s.isQuoted then "True" else "False")
                        (getExamplePrimitiveParameter s.exampleValue)
                        (getTrackedParamPrimitiveParameter s.trackedParameterName)
                        (formatDynamicObjectVariable dynamicObject)
            | Restler_fuzzable_date (s, dynamicObject) ->
                sprintf "primitives.restler_fuzzable_date(\"%s\", quoted=%s%s%s%s)"
                        s.defaultValue
                        (if s.isQuoted then "True" else "False")
                        (getExamplePrimitiveParameter s.exampleValue)
                        (getTrackedParamPrimitiveParameter s.trackedParameterName)
                        (formatDynamicObjectVariable dynamicObject)
            | Restler_fuzzable_object (s, dynamicObject) ->
                if String.IsNullOrEmpty s.defaultValue then
                    printfn "ERROR: fuzzable objects should not be empty.  Skipping."
                    ""
                else
                    let str, delim = quoteStringForPythonGrammar s.defaultValue
                    let quotedDefaultString =
                        sprintf "%s%s%s" delim str delim
                    let exampleParameter = getExamplePrimitiveParameter s.exampleValue
                    sprintf "primitives.restler_fuzzable_object(%s%s%s%s)"
                            quotedDefaultString
                            exampleParameter
                            (getTrackedParamPrimitiveParameter s.trackedParameterName)
                            (formatDynamicObjectVariable dynamicObject)
            | Restler_fuzzable_uuid4 (s, dynamicObject) ->
                sprintf "primitives.restler_fuzzable_uuid4(\"%s\", quoted=%s%s%s%s)"
                        s.defaultValue
                        (if s.isQuoted then "True" else "False")
                        (getExamplePrimitiveParameter s.exampleValue)
                        (getTrackedParamPrimitiveParameter s.trackedParameterName)
                        (formatDynamicObjectVariable dynamicObject)
            | Restler_custom_payload (p, dynamicObject) ->
                sprintf "primitives.restler_custom_payload(\"%s\", quoted=%s%s)"
                        p.defaultValue
                        (if p.isQuoted then "True" else "False")
                        (formatDynamicObjectVariable dynamicObject)
            | Restler_custom_payload_uuid4_suffix (p, isQuoted, dynamicObject) ->
                sprintf "primitives.restler_custom_payload_uuid4_suffix(\"%s\"%s, quoted=%s)"
                        p
                        (formatDynamicObjectVariable dynamicObject)
                        (if isQuoted then "True" else "False")
            | Restler_custom_payload_header (p, dynamicObject) ->
                sprintf "primitives.restler_custom_payload_header(\"%s\"%s)"
                        p
                        (formatDynamicObjectVariable dynamicObject)
            | Restler_custom_payload_query (q, dynamicObject) ->
                sprintf "primitives.restler_custom_payload_query(\"%s\"%s)"
                        q
                        (formatDynamicObjectVariable dynamicObject)
            | Restler_refreshable_authentication_token tok ->
                sprintf "primitives.restler_refreshable_authentication_token(\"%s\")" tok
            | Restler_basepath bp ->
                sprintf "primitives.restler_basepath(\"%s\")" bp
            | Response_parser s -> s
            | p ->
                raise (UnsupportedType (sprintf "Primitive not yet implemented: %A" p))
        str

    let generatePythonRequest (request:Request) =
        let definition =
                generatePythonFromRequest request includeOptionalParameters true
        let definition =
                definition
                |> List.map formatRestlerPrimitive
                |> List.filter (fun s -> not <| String.IsNullOrWhiteSpace s)
                |> List.map (fun str -> sprintf "%s%s,\n" TAB str)
                |> String.concat ""

        let requestIdComment = sprintf "# Endpoint: %s, method: %A" request.id.endpoint request.id.method
        let grammarRequestId = sprintf "requestId=\"%s\"" request.id.endpoint

        let assignAndAdd =
            [
                requestIdComment
                "request = requests.Request(["
                definition
                "],"
                grammarRequestId
                ")"
                "req_collection.add_request(request)\n"
            ]

        let reqTxt = assignAndAdd |> String.concat "\n"
        reqTxt

    requests
    |> List.map (fun r -> generatePythonRequest r)

let generatePythonGrammar (grammar:GrammarDefinition) includeOptionalParameters =
    let getImportStatements() =
        [
            yield PythonGrammarElement.Import (Some "__future__", "print_function")
            yield PythonGrammarElement.Import (None, "json")
            yield PythonGrammarElement.Import (Some "engine", "primitives")
            yield PythonGrammarElement.Import (Some "engine.core", "requests")
            yield PythonGrammarElement.Import (Some "engine.errors", "ResponseParsingException")
            yield PythonGrammarElement.Import (Some "engine", "dependencies")
        ]

    [
        yield PythonGrammarElement.Comment "\"\"\" THIS IS AN AUTOMATICALLY GENERATED FILE!\"\"\""
        yield! getImportStatements()

        yield! getResponseParsers (grammar.Requests)

        yield PythonGrammarElement.RequestCollectionDefinition "req_collection = requests.RequestCollection([])"

        Restler.Utilities.Logging.logTimingInfo "Get requests"
        let requests = getRequests grammar.Requests includeOptionalParameters
        Restler.Utilities.Logging.logTimingInfo "Done get requests"

        yield PythonGrammarElement.Requests requests
    ]

let codeGenElement element =
    match element with
    | PythonGrammarElement.Comment str -> str
    | PythonGrammarElement.Import (a,b) ->
        let from = match a with
                   | Some importSource -> sprintf "from %s " importSource
                   | None -> ""
        sprintf "%simport %s" from b
    | PythonGrammarElement.DynamicObjectDefinition str ->
        "\n" + str
    | PythonGrammarElement.RequestCollectionDefinition str -> str
    | PythonGrammarElement.ResponseParserDefinition str -> str
    | PythonGrammarElement.Requests requests ->
        requests |> String.concat "\n"


let generateCode (grammar:GrammarDefinition) includeOptionalParameters (write : string -> unit) =

    let grammar = generatePythonGrammar grammar includeOptionalParameters

    grammar
    |> Seq.iteri (fun i x ->
        let element = codeGenElement x
        if i = (Seq.length grammar) - 1 then
            write(element)
        else
            write(element + "\n")
    )

/// Takes the mutations dictionary json, and generates a value generator python template file
/// The contents of the file are as follows:
/// <import statements and constants>
/// <sample value generator function for restler_fuzzable_string> - referenced and will be
///  used if the template is specified in the engine settings.
/// <template functions for every dictionary entry> - all unused.
/// <For each key in the dictionary:
///    dictionary entry for the value generator, initialized to 'None'>
let generateCustomValueGenTemplate dictionaryText =
    // Go through the json properties and modify all leaf values to None, then
    // add the sample function for fuzzable string.
    let imports = ["typing"; "random"; "time"; "string"; "itertools"]
    let constants = """
EXAMPLE_ARG = "examples"
"""

    let dictionaryJson = JObject.Parse(dictionaryText)
    // Go through all the properties.  For any fuzzable primitive or custom payloads, create
    // a function and add this to the new object.
    let dictionaryLines = System.Collections.Generic.List<string>()
    let functionNames = System.Collections.Generic.List<string>()

    dictionaryLines.Add("value_generators = {")
    dictionaryJson.Properties()
    |> Seq.iter (fun p ->
                    if p.Name.Contains("_fuzzable_") then
                        let functionName = sprintf "gen_%s" p.Name
                        let referencedFunction = if p.Name = "restler_fuzzable_string" then functionName else "None"
                        dictionaryLines.Add(sprintf "\t\"%s\": %s," p.Name referencedFunction)
                        functionNames.Add(functionName)
                    else if p.Name.Contains("_custom_payload") && not (p.Name.Contains("suffix")) then
                        dictionaryLines.Add(sprintf "\t\"%s\": {" p.Name)
                        let customPayloads = p.Value.Value<JObject>()
                        for cp in customPayloads.Properties() do
                            let functionName =
                                let filteredName = DynamicObjectNaming.generatePythonFunctionNameFromString cp.Name "_"
                                sprintf "gen_%s_%s" p.Name filteredName
                            dictionaryLines.Add(sprintf "\t\t\"%s\": %s," cp.Name "None")
                            functionNames.Add(functionName)

                        dictionaryLines.Add("\t},")
                )
    dictionaryLines.Add("}")
    let dictionaryText = dictionaryLines |> seq |> String.concat "\n"

    // Add sample function for fuzzable string.
    functionNames.Remove("gen_restler_fuzzable_string") |> ignore
    let sampleFunction = """
def gen_restler_fuzzable_string(**kwargs):
    example_values=None
    if EXAMPLE_ARG in kwargs:
        example_values = kwargs[EXAMPLE_ARG]

    if example_values:
        for exv in example_values:
            yield exv
        example_values = itertools.cycle(example_values)

    i = 0
    while True:
        i = i + 1
        size = random.randint(i, i + 10)
        if example_values:
            ex = next(example_values)
            ex_k = random.randint(1, len(ex) - 1)
            new_values=''.join(random.choices(ex, k=ex_k))
            yield ex[:ex_k] + new_values + ex[ex_k:]

        yield ''.join(random.choices(string.ascii_letters + string.digits, k=size))
        yield ''.join(random.choices(string.printable, k=size)).replace("\r\n", "")

def placeholder_value_generator():
    while True:
        yield str(random.randint(-10, 10))
        yield ''.join(random.choices(string.ascii_letters + string.digits, k=1))
    """

    let getFunctionText functionName =
        sprintf """
def %s(**kwargs):
    example_value=None
    if EXAMPLE_ARG in kwargs:
        example_value = kwargs[EXAMPLE_ARG]

    # Add logic here to generate values
    return placeholder_value_generator()
    """
                functionName

    let functionDefinitions =
        functionNames
        |> Seq.map (fun functionName -> getFunctionText functionName)
        |> String.concat "\n\n"

    seq {
        for i in imports do
            yield sprintf "import %s" i

        yield "random_seed=time.time()"
        yield """print(f"Value generator random seed: {random_seed}")"""
        yield "random.seed(random_seed)"
        yield constants

        yield sampleFunction
        yield functionDefinitions
        yield dictionaryText
    }




