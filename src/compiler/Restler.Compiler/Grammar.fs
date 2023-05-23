// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.Grammar

open System.IO
open AccessPaths
open Restler.XMsPaths

/// Tree utilities.
/// Reference: https://fsharpforfunandprofit.com/posts/recursive-types-and-folds/
module Tree =
    type Tree<'LeafData,'INodeData> =
        | LeafNode of 'LeafData
        | InternalNode of 'INodeData * Tree<'LeafData,'INodeData> seq


    /// Same as cata, but allows passing a parent context
    let cataCtx fLeaf fNode fCtx ctx (tree:Tree<'LeafData,'INodeData>) :'r =
        let rec contMap newCtx (trees: seq<Tree<'LeafData,'INodeData>>) (conts: seq<'r> -> 'r): 'r =
            if Seq.isEmpty trees then
                conts []
            else
                let h = Seq.head trees
                contMap newCtx (Seq.tail trees) (fun ts ->
                    processTree newCtx h (fun s -> conts (Seq.append [s] ts))
                )
        and processTree ctx tree cont =
            match tree with
            | LeafNode leafInfo ->
                cont(fLeaf ctx leafInfo)
            | InternalNode (nodeInfo,subtrees) ->
                let newCtx = fCtx ctx nodeInfo
                contMap newCtx subtrees (fun ts ->
                    cont (fNode ctx nodeInfo ts)
                )
        processTree ctx tree id

    let cata fLeaf fNode (tree:Tree<'LeafData,'INodeData>) :Tree<'LeafData,'INodeData> =
        cataCtx fLeaf fNode (fun () _ -> ()) () tree

    let rec fold fLeaf fNode acc (tree:Tree<'LeafData,'INodeData>) :'r =
        let recurse = fold fLeaf fNode
        match tree with
        | LeafNode leafInfo ->
            fLeaf acc leafInfo
        | InternalNode (nodeInfo,subtrees) ->
            // determine the local accumulator at this level
            let localAccum = fNode acc nodeInfo
            // thread the local accumulator through all the subitems using Seq.fold
            let finalAccum = subtrees |> Seq.fold recurse localAccum
            // ... and return it
            finalAccum

    /// Iterate over the tree, passing a parent context
    let rec iterCtx fLeaf fNode fCtx ctx (tree:Tree<'LeafData,'INodeData>) : unit =
        let recurse = iterCtx fLeaf fNode fCtx
        match tree with
        | LeafNode leafInfo ->
            fLeaf ctx leafInfo
        | InternalNode (nodeInfo,subtrees) ->
            let newCtx = fCtx ctx nodeInfo
            subtrees |> Seq.iter (recurse newCtx)
            fNode ctx nodeInfo

    /// Iterate over the tree, and visit each tree node
    let rec iterTree fNode (tree:Tree<'LeafData,'INodeData>) : unit =
        let recurse = iterTree fNode
        match tree with
        | LeafNode _ ->
            fNode tree
        | InternalNode (_,subtrees) ->
            subtrees |> Seq.iter (recurse)
            fNode tree

type OperationMethod =
    | Get
    | Post
    | Put
    | Delete
    | Patch
    | Options
    | Head
    | Trace
    | NotSupported

let getOperationMethodFromString (m:string) =
    match (m.ToUpper()) with
    | "GET" -> OperationMethod.Get
    | "POST" -> OperationMethod.Post
    | "PUT" -> OperationMethod.Put
    | "DELETE" -> OperationMethod.Delete
    | "PATCH" -> OperationMethod.Patch
    | "OPTIONS" -> OperationMethod.Options
    | "HEAD" -> OperationMethod.Head
    | "TRACE" -> OperationMethod.Trace
    | _ -> OperationMethod.NotSupported

type ParameterKind =
    | Path
    | Body
    | Query
    | Header

/// The primitive types supported by RESTler
type PrimitiveType =
    | String
    | Object
    | Number
    | Int
    | Uuid
    | Bool
    | DateTime
    | Date
    /// The enum type specifies the list of possible enum values
    /// and the default value, if specified.
    /// (tag, data type, possible values, default value if present)
    | Enum of string * PrimitiveType * string list * string option

type NestedType =
    | Array
    | Object
    | Property

type CustomPayloadType =
    | String

    | UuidSuffix

    | Header

    /// Used to inject query parameters that are not part of the specification.
    | Query


type DynamicObject =
    {
        /// The primitive type of the parameter, as declared in the specification
        /// The primitive type is assigned to be the type of the initially written value
        //  whenever possible.
        primitiveType : PrimitiveType

        /// The variable name of the dynamic object
        variableName : string

        /// 'True' if this is an assignment, otherwise a read of the dynamic object
        isWriter : bool
    }

type CustomPayload =
    {
        /// The type of custom payload
        payloadType: CustomPayloadType

        /// The primitive type of the payload, as declared in the specification
        primitiveType : PrimitiveType

        /// The value of the payload
        payloadValue : string

        /// 'True' if the value is an object
        isObject : bool

        /// This identifier may have an associated dynamic object, whose value should be
        /// assigned to the value generated from this payload
        dynamicObject: DynamicObject option
    }

type FuzzablePayload =
    {
        /// The primitive type of the payload, as declared in the specification
        primitiveType : PrimitiveType

        /// The default value of the payload
        defaultValue : string

        /// The example value specified in the spec, if any
        exampleValue : string option

        /// The parameter name, if available.
        parameterName : string option

        /// The associated dynamic object, whose value should be
        /// assigned to the value generated from this payload.
        /// For example, an input value from a request body property.
        dynamicObject: DynamicObject option
    }

/// The payload for a property specified in as a request parameter
type FuzzingPayload =
    /// Example: (Int "1")
    | Constant of PrimitiveType * string

    /// (data type, default value, example value, parameter name)
    /// Example: (Int "1", "2")
    | Fuzzable of FuzzablePayload

    /// The custom payload, as specified in the fuzzing dictionary
    | Custom of CustomPayload

    | DynamicObject of DynamicObject

    /// In some cases, a payload may need to be split into multiple payload parts
    | PayloadParts of FuzzingPayload list



/// The unique ID of a request.
type RequestId =
    {
        endpoint : string

        /// If a request is declared with an x-ms-path, 'xMsPath' contains the original path
        /// from the specification.  The 'endpoint' above contains a transformed path for
        /// so that the OpenAPI specification can be compiled with standard 'paths'.
        xMsPath : XMsPath option

        method : OperationMethod
    }

type AnnotationResourceReference =
    /// A resource parameter may be obtained by name only
    | ResourceName of string

    /// A resource parameter must be obtained in context, via its full path.
    | ResourcePath of AccessPath

type ProducerConsumerAnnotation =
    {
        producerId : RequestId
        consumerId : RequestId option
        producerParameter : AnnotationResourceReference option
        consumerParameter : AnnotationResourceReference option
        exceptConsumerId: RequestId list option
    }

/// A property that does not have any nested properties
type LeafProperty =
    {
        name : string
        payload : FuzzingPayload
        isRequired : bool
        isReadOnly : bool
    }

// A property that has nested properties
// Such an inner property can have a fuzzing payload (e.g., an entire json object, specified
// directly or as a reference to the custom dictionary) or instead specify
// individual elements for fuzzing (concrete values will be specified later, e.g. at the leaf level)
type InnerProperty =
    {
        name : string
        payload : FuzzingPayload option
        propertyType : NestedType
        isRequired: bool
        isReadOnly : bool
    }

/// The response properties
type ResponseProperties = Tree.Tree<LeafProperty, InnerProperty>

/// The object assigned to a parameter (which may include nested properties)
type ParameterPayload = Tree.Tree<LeafProperty, InnerProperty>

/// The source of parameters for this grammar element.
type ParameterPayloadSource =
    /// Parameters were defined in the Swagger definition schema
    | Schema
    /// Parameters were defined in a payload example
    | Examples
    /// Parameters were defined as a custom payload
    | DictionaryCustomPayload

/// The parameter serialization style
type StyleKind =
    | Form
    | Simple

/// Information related to how to serialize the parameter
type ParameterSerialization =
    {
        /// Defines how multiple values are delimited
        style : StyleKind

        /// Specifies whether arrays and objects should generate
        /// separate parameters for each array item or object property
        explode : bool
    }

type RequestParameter =
    {
        name: string
        payload: ParameterPayload
        serialization: ParameterSerialization option
    }

/// The payload for request parameters
type RequestParametersPayload =
    | ParameterList of seq<RequestParameter>
    | Example of FuzzingPayload

/// All request parameters
type RequestParameters =
    {
        path: RequestParametersPayload

        header: (ParameterPayloadSource * RequestParametersPayload) list

        /// List of several possible parameter sets that may be used to invoke a request.
        /// The payload source is not expected to be unique. For example, there may be several schemas
        /// from different examples.
        query: (ParameterPayloadSource * RequestParametersPayload) list

        /// List of several possible parameter sets that may be used to invoke a request.
        /// The payload source is not expected to be unique. For example, there may be several schemas
        /// from different examples.
        body: (ParameterPayloadSource * RequestParametersPayload) list
    }


/// The type of token required to access the API
type TokenKind =
    | Static of string
    | Refreshable

/// The type of dynamic object variable
type DynamicObjectVariableKind =
    /// Dynamic object assigned from a body response property
    | BodyResponseProperty

    /// Dynamic object assigned from a response header
    | Header

    /// Dynamic object assigned from an input parameter or property value
    | InputParameter

    /// A variable specifically created for an ordering constraint,
    /// which is not included as part of the payload.  (TODO: maybe this is not needed?)
    | OrderingConstraint

type DynamicObjectWriterVariable =
    {
        /// The ID of the request
        requestId : RequestId

        /// The access path to the parameter associated with this dynamic object
        accessPathParts: AccessPath

        /// The type of the variable
        primitiveType : PrimitiveType

        /// The kind of the variable (e.g. header or response property)
        kind : DynamicObjectVariableKind
    }

type OrderingConstraintVariable =
    {
        /// The ID of the producer request
        sourceRequestId : RequestId
        targetRequestId : RequestId
    }

/// Information needed to generate a response parser
type ResponseParser =
    {
        /// The writer variables returned in the response
        writerVariables : DynamicObjectWriterVariable list

        /// The writer variables returned in the response headers
        headerWriterVariables : DynamicObjectWriterVariable list
    }

/// Information needed for dependency management
type RequestDependencyData =
    {
        /// The generated response parser.  This is only present if there is at least
        /// one consumer for a property of the response.
        responseParser : ResponseParser option

        /// The writer variables that are written when the request is sent, and which
        /// are not returned in the response
        inputWriterVariables : DynamicObjectWriterVariable list

        /// The writer variables used for ordering constraints
        orderingConstraintWriterVariables : OrderingConstraintVariable list

        /// The reader variables used for ordering constraints
        orderingConstraintReaderVariables : OrderingConstraintVariable list
    }

/// The parts of a request
type RequestElement =
    | Method of OperationMethod
    | BasePath of string
    | Path of FuzzingPayload list
    | QueryParameters of ParameterPayloadSource * RequestParametersPayload
    | HeaderParameters of ParameterPayloadSource * RequestParametersPayload
    | Body of ParameterPayloadSource * RequestParametersPayload
    | Token of string
    | RefreshableToken
    | Headers of (string * string) list
    | HttpVersion of string
    | RequestDependencyData of RequestDependencyData option
    | Delimiter

/// The additional metadata of a request that may be used during fuzzing.
type RequestMetadata =
    {
        /// Request is declared as a long-running operation via x-ms-long-running-operation
        isLongRunningOperation : bool
    }

/// Definition of a request according to how it should be fuzzed and
/// how to parse the response
/// Note: this does not match the paper, where a request type does not
/// include any information about the response, but it seems appropriate here.
type Request =
    {
        /// The request ID.  This is used to associate requests in the grammar with
        /// per-request definitions in the RESTler engine configuration.
        id : RequestId

        /// The request method, e.g. GET
        method : OperationMethod

        /// The basepath, or an empty string if not specified.
        basePath : string

        path : FuzzingPayload list

        queryParameters : (ParameterPayloadSource * RequestParametersPayload) list

        bodyParameters : (ParameterPayloadSource * RequestParametersPayload) list

        headerParameters : (ParameterPayloadSource * RequestParametersPayload) list

        /// The token required to access the API
        token : TokenKind

        headers : (string * string) list

        httpVersion : string

        dependencyData : RequestDependencyData option

        /// The additional properties of a request
        requestMetadata : RequestMetadata
    }

/// Definitions necessary for the RESTler algorithm
type GrammarDefinition =
    {
        Requests : Request list
    }

module DynamicObjectNaming =
    let ReplaceTargets = [|"/"; "."; "__"; "{"; "}"; "$"; "-"; ":" |]

    /// Returns the string with all characters that are invalid in
    /// a Python function replaced with 'delimiter'
    let generatePythonFunctionNameFromString (str:string) delimiter =
        str.Split(ReplaceTargets, System.StringSplitOptions.None)
        |> seq
        |> String.concat delimiter

    let generateOrderingConstraintVariableName (sourceRequestId:RequestId) (targetRequestId:RequestId) delimiter =

        let sourceEndpointParts = sourceRequestId.endpoint.Split(ReplaceTargets, System.StringSplitOptions.None)

        let targetEndpointParts = targetRequestId.endpoint.Split(ReplaceTargets, System.StringSplitOptions.None)

        let commonEndpointParts, distinctEndpointParts =
            let zipped = Seq.zip sourceEndpointParts targetEndpointParts
            zipped |> Seq.takeWhile (fun (x,y) -> x = y) |> Seq.map (fun (x,_) -> x) |> Seq.toList,
            zipped |> Seq.skipWhile (fun (x,y) -> x = y) |> Seq.toList |> List.unzip

        ["__ordering__"] @ commonEndpointParts @ (fst distinctEndpointParts) @ (snd distinctEndpointParts)
        |> String.concat delimiter

    let generateDynamicObjectVariableName (requestId:RequestId) (accessPath:AccessPath option) delimiter =
        // split endpoint, add "id" at the end.  TBD: jobs_0 vs jobs_1 - where is the increment?
        // See restler_parser.py line 800

        let endpointParts = requestId.endpoint.Split(ReplaceTargets, System.StringSplitOptions.None)
                            |> Array.toList

        let objIdParts =
            match accessPath with
            | None -> Array.empty
            | Some ap -> ap.getPathPartsForName()
        let objIdParts =
            objIdParts
            |> Seq.map (fun part -> part.Split(ReplaceTargets, System.StringSplitOptions.None))
            |> Seq.concat
        let parts = endpointParts
                    @ [(requestId.method.ToString().ToLower())]
                    @ (objIdParts |> Seq.toList)
        parts |> String.concat delimiter

    let generateIdForCustomUuidSuffixPayload containerName propertyName =
        let container =
            if System.String.IsNullOrEmpty(containerName) then
                ""
            else
                sprintf "%s_" containerName
        sprintf "%s%s" container propertyName

    /// Because some services have a strict naming convention on identifiers,
    /// this function attempts to generate a variable name to avoid violating such constraints
    /// Note: the unique UUID suffix may still cause problems, which will need to be addressed
    /// differently in the engine.
    let generatePrefixForCustomUuidSuffixPayload (suffixPayloadId:string) =
        /// Use all-lowercase values with at most 10 characters and only letter characters
        let suffixPayloadIdRestricted =
            suffixPayloadId
            |> Seq.filter (fun ch -> System.Char.IsLetter(ch))
            |> Seq.map (fun ch -> System.Char.ToLower(ch))
            |> Seq.truncate 10
        if suffixPayloadIdRestricted |> Seq.isEmpty then
            // No letter or digit found in variable name.  This is very rare, just use the payload ID in such cases.
            sprintf "%s" suffixPayloadId
        else
            sprintf "%s" (suffixPayloadIdRestricted |> Seq.map string |> String.concat "")


/// This map lists the default primitive values for fuzzable primitives
/// These will be used both in the grammar and dictionary file.
let DefaultPrimitiveValues =
    [
        PrimitiveType.String, "fuzzstring" // Note: quotes are intentionally omitted.
        PrimitiveType.Uuid, "566048da-ed19-4cd3-8e0a-b7e0e1ec4d72" // Note: quotes are intentionally omitted.
        PrimitiveType.DateTime, "2019-06-26T20:20:39+00:00" // Note: quotes are intentionally omitted.
        PrimitiveType.Date, "2019-06-26" // Note: quotes are intentionally omitted.
        PrimitiveType.Number, "1.23" // Note: quotes are intentionally omitted.
        PrimitiveType.Int, "1"
        PrimitiveType.Bool, "true"
        PrimitiveType.Object, "{ \"fuzz\": false }"
    ]
    |> Map.ofSeq

