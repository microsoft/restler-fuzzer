// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.CodeGenerator.Python

open System
open Restler.Grammar
open Restler.Utilities.Operators

[<Literal>]
let TAB = @"    "
let RETURN = @"\r\n"
let SPACE = @" "

exception UnsupportedAccessPath
exception UnsupportedType of string

module Types =
    type RequestPrimitiveTypeData =
        {
            defaultValue : string
            isQuoted : bool
        }

    /// RESTler grammar built-in types
    /// IMPORTANT ! All primitives must be supported in restler/engine/primitives.py
    type RequestPrimitiveType =
        | Restler_static_string_constant of string
        | Restler_static_string_variable of string
        | Restler_static_string_jtoken_delim of string
        | Restler_fuzzable_string of RequestPrimitiveTypeData
        | Restler_fuzzable_datetime of RequestPrimitiveTypeData
        | Restler_fuzzable_object of string
        | Restler_fuzzable_delim of string
        | Restler_fuzzable_uuid4 of RequestPrimitiveTypeData
        | Restler_fuzzable_group of RequestPrimitiveTypeData
        | Restler_fuzzable_bool of string
        | Restler_fuzzable_int of string
        | Restler_fuzzable_number of string
        | Restler_multipart_formdata of string
        | Restler_custom_payload of RequestPrimitiveTypeData
        | Restler_custom_payload_header of string
        | Restler_custom_payload_uuid4_suffix of string
        | Restler_refreshable_authentication_token of string
        | Shadow_values of string
        | Response_parser of string

open Types

module NameGenerators =
    let generateDynamicObjectVariableDefinition responseAccessPathParts (requestId:RequestId) =
        let varName = (generateDynamicObjectVariableName requestId (Some responseAccessPathParts) "_")
        sprintf "%s = dependencies.DynamicVariable(\"%s\")" varName varName

    let generateProducerEndpointResponseParserFunctionName (requestId:RequestId) =
        sprintf "parse_%s" (generateDynamicObjectVariableName requestId None "")

// Gets the RESTler primitive that corresponds to the specified fuzzing payload
let rec getRestlerPythonPayload (payload:FuzzingPayload) (isQuoted:bool) : RequestPrimitiveType list =
    let getPrimitivePayload p =
        match p with
        | Constant (t,v) ->
            Restler_static_string_constant v
        | Fuzzable (t,v) ->
            match t with
            | Bool -> Restler_fuzzable_bool v
            | PrimitiveType.DateTime ->
                Restler_fuzzable_datetime { defaultValue = v ; isQuoted = isQuoted }
            | PrimitiveType.String ->
                Restler_fuzzable_string { defaultValue = v ; isQuoted = isQuoted }
            | PrimitiveType.Object -> Restler_fuzzable_object v
            | Int -> Restler_fuzzable_int v
            | Number -> Restler_fuzzable_number v
            | Uuid ->
                Restler_fuzzable_uuid4 { defaultValue = v ; isQuoted = isQuoted }
            | PrimitiveType.Enum (_, enumeration, defaultValue) ->
                // TODO: should this be generating unique fuzzable group tags?  Why is one needed?
                let defaultStr =
                    match defaultValue with
                    | Some v -> sprintf ", default_enum=\"%s\"" v
                    | None -> ""
                let groupValue =
                    (sprintf "\"fuzzable_group_tag\", [%s] %s "
                             (enumeration |> List.map (fun s -> sprintf "'%s'" s) |> String.concat ",")
                             defaultStr
                    )
                Restler_fuzzable_group
                    { defaultValue = groupValue ; isQuoted = isQuoted }
        | Custom c ->
            match c.payloadType with
            | CustomPayloadType.String ->
                Restler_custom_payload { defaultValue = c.payloadValue ; isQuoted = isQuoted }
            | CustomPayloadType.UuidSuffix ->
                Restler_custom_payload_uuid4_suffix c.payloadValue
            | CustomPayloadType.Header ->
                Restler_custom_payload_header c.payloadValue  // TODO: need test
        | DynamicObject s ->
            Restler_static_string_variable (sprintf "%s.reader()" s)
        | PayloadParts p ->
            raise (invalidArg "p" "expected primitive payload")

    match payload with
    | PayloadParts parts ->
        parts |> List.map (fun part -> getRestlerPythonPayload part false (*isQuoted*))
              |> List.concat
    | p -> [ getPrimitivePayload p ]

/// Generate the RESTler grammar for a request parameter
let generatePythonParameter includeOptionalParameters parameterKind (parameterName, parameterPayload) =
    let formatParameterName name =
        match parameterKind with
        | ParameterKind.Query ->
            Restler_static_string_constant (sprintf "%s=" name)
        | ParameterKind.Body ->
            Restler_static_string_constant (sprintf "\"%s\":" name)
        | ParameterKind.Path ->
            raise (UnsupportedType "Invalid context for Path parameters")

    let formatPropertyName name =
        if String.IsNullOrEmpty name then
            Restler_static_string_constant ""
        else
            Restler_static_string_constant (sprintf "\"%s\":" name)

    let getTabIndentedLineStart level =
        if level > 0 then
            let tabs = [1..level] |> List.map (fun x -> TAB) |> String.Concat
            Some ("\n" + tabs)
        else
            None

    let visitLeaf level (p:LeafProperty) =
        let rec isPrimitiveTypeQuoted primitiveType isNullValue =
            match primitiveType with
            | _ when isNullValue -> false
            | PrimitiveType.String
            | PrimitiveType.DateTime
            | PrimitiveType.Uuid ->
                true
            | PrimitiveType.Enum (enumType, _, _) ->
                isPrimitiveTypeQuoted enumType isNullValue
            | PrimitiveType.Object
            | PrimitiveType.Int
            | PrimitiveType.Bool
            | PrimitiveType.Number ->
                false

        if p.isRequired  || includeOptionalParameters then
            let nameSeq =
                if String.IsNullOrEmpty p.name then
                    List.empty
                else
                    [ formatPropertyName p.name ]

            let needQuotes, isFuzzable =
                match p.payload with
                | FuzzingPayload.Custom c ->
                    let isFuzzable = (c.payloadType = CustomPayloadType.String)
                    // 'needQuotes' must be based on the underlying type of the payload.
                    let needQuotes =
                        (not c.isObject) &&
                        (isPrimitiveTypeQuoted c.primitiveType false)
                    needQuotes, isFuzzable
                | FuzzingPayload.Constant (PrimitiveType.String, s) ->
                    // TODO: improve the metadata of FuzzingPayload.Constant to capture whether
                    // the constant represents an object,
                    // rather than relying on the formatting behavior of JToken.ToString.
                    not (isNull s) &&
                    not (s.Contains("\n")),
                    false
                | FuzzingPayload.Constant (primitiveType, v) ->
                    isPrimitiveTypeQuoted primitiveType (isNull v),
                    false
                | FuzzingPayload.Fuzzable (primitiveType, _) ->
                    // Note: this is a current RESTler limitation -
                    // fuzzable values may not be set to null without changing the grammar.
                    isPrimitiveTypeQuoted primitiveType false,
                    true
                | FuzzingPayload.DynamicObject (_)
                | FuzzingPayload.PayloadParts (_) ->
                    // Note: dynamic objects as the query parameter (e.g. api-version) do not need quotes.
                    // That case is handled elsewhere.
                    true, false

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
                        needQuotes && not isFuzzable && parameterKind = ParameterKind.Body
                    if needStaticStringQuotes then
                        yield Restler_static_string_constant "\""

                    let isQuoted = (needQuotes && isFuzzable && (parameterKind = ParameterKind.Body || level > 0))
                    for k in getRestlerPythonPayload p.payload isQuoted do
                        yield k

                    if needStaticStringQuotes then
                        yield Restler_static_string_constant "\""
                ]

            [ tabSeq ; nameSeq ; payloadSeq ] |> List.concat
        else
            []

    let visitInner level (p:InnerProperty) (innerProperties: RequestPrimitiveType list seq) =
        if p.isRequired || includeOptionalParameters then
            // Pretty-printing is only required for the body
            let tabSeq =
                if parameterKind = ParameterKind.Body then
                    match getTabIndentedLineStart level with
                    | None -> []
                    | Some s -> [ Restler_static_string_constant s ]
                else []

            match p.payload with
            | Some payload ->
                // Use the payload specified at this level.
                let namePayloadSeq =
                    (formatPropertyName p.name) ::
                    // Because this is a custom payload for an object, it should not be quoted.
                    (getRestlerPythonPayload payload false (*isQuoted*))
                tabSeq @ namePayloadSeq
            | None ->
                // The payload is not specified at this level, so use the one specified at lower levels.
                // The inner properties must be comma separated
                let cs = innerProperties
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
                @ [formatPropertyName p.name]
                @ tabSeq
                @ [
                    Restler_static_string_jtoken_delim
                        (match p.propertyType with
                            | Object -> "{"
                            | Array -> "["
                            | Property -> "")
                ]
                @ cs
                @ tabSeq

                @ [
                    Restler_static_string_jtoken_delim
                        (match p.propertyType with
                            | Object -> "}"
                            | Array -> "]"
                            | Property -> "")
                ]
        else
            []

    let getTreeLevel parentLevel (p:InnerProperty) =
        parentLevel + 1

    let payloadPrimitives = Tree.cataCtx visitLeaf visitInner getTreeLevel 0 parameterPayload

    match parameterKind with
    | ParameterKind.Query ->
        let payloadPrimitives =
            // Remove the beginning and ending quotes - these must not be specified for query parameters.
            if payloadPrimitives |> List.head = Restler_static_string_constant "\"" then
                let length = payloadPrimitives |> List.length
                payloadPrimitives
                |> List.skip 1 |> List.take (length - 2)
            else
                payloadPrimitives

        (formatParameterName parameterName) :: payloadPrimitives 
    | ParameterKind.Body
    | ParameterKind.Path ->
        payloadPrimitives

/// Generates the python restler grammar definitions corresponding to the request
let generatePythonFromRequestElement includeOptionalParameters (e:RequestElement) =
    match e with
    | Method m ->
        [Restler_static_string_constant (sprintf "%s%s" (m.ToString().ToUpper()) SPACE)]
    | RequestElement.Path parts ->
        let x = parts
                |> List.map (fun p -> getRestlerPythonPayload p false (*isQuoted*))
                |> (fun xs ->
                    [
                        for primitive in xs do
                            yield Restler_static_string_constant "/"
                            yield! primitive
                    ]
                )
        x
    | QueryParameters qp ->
        match qp with
        | ParameterList bp ->
            let parameters =
                bp |> List.ofSeq
                   |> List.map (fun p -> generatePythonParameter includeOptionalParameters ParameterKind.Query p)
                   |> List.mapi (fun i primitive ->
                                    if i > 0 then
                                        [
                                            yield Restler_static_string_constant "&"
                                            yield! primitive 
                                        ]
                                        
                                    else primitive
                               )
                   |> List.concat
            if parameters |> List.isEmpty then
                []
            else
                [
                    yield Restler_static_string_constant "?"
                    yield! parameters 
                ]
        | _ ->
            raise (UnsupportedType (sprintf "This request parameters payload type is not supported: %A" qp))
    | Body b ->
        match b with
        | ParameterList bp ->
            let parameters =
                bp |> List.ofSeq
                   |> List.map (fun p -> generatePythonParameter includeOptionalParameters ParameterKind.Body p)
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
        | _ ->
            raise (UnsupportedType (sprintf "This request parameters payload type is not supported: %A." b))

    | Token t->
        match t with
        | tokStr ->
            [Restler_static_string_constant (sprintf "%s%s" tokStr RETURN)]
    | RefreshableToken ->
        [Restler_refreshable_authentication_token "authentication_token_tag"]
    | Headers h ->
        h |> List.map (fun (name, content) -> Restler_static_string_constant (sprintf "%s: %s%s" name content RETURN))
    | HttpVersion v->
        [Restler_static_string_constant (sprintf "%sHTTP/%s%s" SPACE v RETURN)]
    | ResponseParser r ->
        match r with
        | None -> []
        | Some responseParser ->
            let generateWriterStatement var =
               sprintf "%s.writer()" var

            let postSend =
                let writerVariablesList =
                    responseParser.writerVariables
                    // TODO: generate this ID only once if possible.
                    |> List.map (fun producerWriter ->
                                      let stmt = generateWriterStatement (generateDynamicObjectVariableName producerWriter.requestId (Some producerWriter.accessPathParts) "_")
                                      let indent = Seq.init 4 (fun _ -> TAB) |> String.concat ""
                                      sprintf "%s%s" indent stmt
                                      )
                    |> String.concat ",\n"
                sprintf @"
    {
        'post_send':
        {
            'parser': %s,
            'dependencies':
            [
%s
            ]
        }
    }"
                    (NameGenerators.generateProducerEndpointResponseParserFunctionName responseParser.writerVariables.Head.requestId)
                    writerVariablesList

            [Response_parser postSend]
    | Delimiter ->
        [Restler_static_string_constant RETURN]

/// Generates the python restler grammar definitions corresponding to the request
let generatePythonFromRequest (request:Request) includeOptionalParameters mergeStaticStrings =
    let getParameterPayload queryOrBodyParameters =
        queryOrBodyParameters |> List.head |> snd

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
        Path request.path
        QueryParameters (getParameterPayload request.queryParameters)
        HttpVersion request.httpVersion
        Headers request.headers
        (match request.token with
            | TokenKind.Refreshable -> RefreshableToken
            | (TokenKind.Static token) -> Token (token))
        Body (getParameterPayload request.bodyParameters)
        Delimiter
        ResponseParser request.responseParser
    ]

    requestElements
    |> List.map (fun requestElement ->
                    let primitives = generatePythonFromRequestElement includeOptionalParameters requestElement
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

let getResponseParsers (responseParsers:ResponseParser list) =

    let random = System.Random(0)

    // First, define the dynamic variables initialized by the response parser
    let dynamicObjectDefinitions = 
        [
            for r in responseParsers do
                for writerVariable in r.writerVariables do
                    yield PythonGrammarElement.DynamicObjectDefinition
                            (NameGenerators.generateDynamicObjectVariableDefinition writerVariable.accessPathParts writerVariable.requestId)
        ]

    let formatParserFunction (parser:ResponseParser) =
        let functionName = NameGenerators.generateProducerEndpointResponseParserFunctionName
                                parser.writerVariables.[0].requestId

        // Go through the producer fields and parse them all out of the response
        let responseParsingStatements =
            [
                for w in parser.writerVariables do
                    let dynamicObjectVariableName = generateDynamicObjectVariableName w.requestId (Some w.accessPathParts) "_"
                    let tempVariableName = sprintf "temp_%d" (random.Next(10000))
                    let emptyInitStatement = sprintf "%s = None" tempVariableName
                    let getPath (part:string) =
                        if part.StartsWith("[") then
                            // TODO: how should subsequent elements be accessed?  Random access
                            // may be desirable in fuzz mode.
                            "[0]"
                        else
                            sprintf "[\"%s\"]" part

                    let extractData =
                        w.accessPathParts.path |> Array.map getPath
                        |> String.concat ""
                    let parsingStatement = sprintf "%s = str(data%s)" tempVariableName extractData
                    let initCheck = sprintf "if %s:" tempVariableName
                    let initStatement = sprintf "dependencies.set_variable(\"%s\", %s)"
                                            dynamicObjectVariableName
                                            tempVariableName
                    yield (emptyInitStatement, parsingStatement, initCheck, initStatement, tempVariableName)
            ]

        let parsingStatementWithTryExcept parsingStatement =
            sprintf "
    try:
        %s
    except Exception as error:
        # This is not an error, since some properties are not always returned
        pass
"
                parsingStatement


        let functionDefinition = sprintf "
def %s(data):
    \"\"\" Automatically generated response parser \"\"\"
    # Declare response variables
%s
    # Parse the response into json
    try:
        data = json.loads(data)
    except Exception as error:
        raise ResponseParsingException(\"Exception parsing response, data was not valid json: {}\".format(error))

    # Try to extract each dynamic object

%s

    # If no dynamic objects were extracted, throw.
    if not (%s):
        raise ResponseParsingException(\"Error: all of the expected dynamic objects were not present in the response.\")

    # Set dynamic variables
%s
"
                                        functionName
                                        (responseParsingStatements
                                         |> List.map(fun (emptyInitStatement,_,_,_,_) -> (TAB + emptyInitStatement)) |> String.concat "\n")

                                        (responseParsingStatements
                                         |> List.map(fun (_,parsingStatement,_,_,_) ->
                                                        parsingStatementWithTryExcept parsingStatement)
                                         |> String.concat "\n")

                                        (responseParsingStatements
                                        |> List.map(fun (_,_,_,_,tempVariableName) ->
                                                        tempVariableName)

                                        |> String.concat " or ")

                                        (responseParsingStatements
                                         |> List.map(fun (_,_,initCheck,initStatement,_) ->
                                                        (TAB + initCheck + "\n" + TAB + TAB + initStatement)) |> String.concat "\n")

        PythonGrammarElement.ResponseParserDefinition functionDefinition

    [
        yield! dynamicObjectDefinitions
        yield! (responseParsers |> List.map (fun r -> formatParserFunction r))
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
            else if s.Contains("\"") then s.Replace("\"", "\\\""), "\""
            else s, "\""
        s, delim

    let formatRestlerPrimitive p =
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
            | Restler_static_string_variable s ->
                sprintf "primitives.restler_static_string(%s)" s
            | Restler_fuzzable_string s ->
                if String.IsNullOrEmpty s.defaultValue then
                    printfn "ERROR: fuzzable strings should not be empty.  Skipping."
                    ""
                else
                    let str, delim = quoteStringForPythonGrammar s.defaultValue
                    sprintf "primitives.restler_fuzzable_string(%s%s%s, quoted=%s)"
                             delim str delim
                             (if s.isQuoted then "True" else "False")
            | Restler_fuzzable_group s ->
                sprintf "primitives.restler_fuzzable_group(%s,quoted=%s)"
                        s.defaultValue
                        (if s.isQuoted then "True" else "False")
            | Restler_fuzzable_int s ->
                sprintf "primitives.restler_fuzzable_int(\"%s\")" s
            | Restler_fuzzable_number s ->
                sprintf "primitives.restler_fuzzable_number(\"%s\")" s
            | Restler_fuzzable_bool s ->
                sprintf "primitives.restler_fuzzable_bool(\"%s\")" s
            | Restler_fuzzable_datetime s ->
                sprintf "primitives.restler_fuzzable_datetime(\"%s\", quoted=%s)"
                        s.defaultValue
                        (if s.isQuoted then "True" else "False")
            | Restler_fuzzable_object s ->
                if String.IsNullOrEmpty s then
                    printfn "ERROR: fuzzable objects should not be empty.  Skipping."
                    ""
                else
                    let s, delim = quoteStringForPythonGrammar s
                    sprintf "primitives.restler_fuzzable_object(%s%s%s)" delim s delim
            | Restler_fuzzable_uuid4 s ->
                sprintf "primitives.restler_fuzzable_uuid4(\"%s\", quoted=%s)"
                        s.defaultValue
                        (if s.isQuoted then "True" else "False")

            | Restler_custom_payload p ->
                sprintf "primitives.restler_custom_payload(\"%s\", quoted=%s)"
                        p.defaultValue
                        (if p.isQuoted then "True" else "False")

            | Restler_custom_payload_uuid4_suffix p ->
                sprintf "primitives.restler_custom_payload_uuid4_suffix(\"%s\")" p
            | Restler_refreshable_authentication_token tok ->
                sprintf "primitives.restler_refreshable_authentication_token(\"%s\")" tok
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

        yield! getResponseParsers (grammar.Requests |> List.choose (fun req -> req.responseParser))

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
