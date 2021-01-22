// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.Grammar

open System.IO
open AccessPaths

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

/// The primitive types supported by RESTler
type PrimitiveType =
    | String
    | Object
    | Number
    | Int
    | Uuid
    | Bool
    | DateTime
    /// The enum type specifies the list of possible enum values
    /// and the default value, if specified.
    | Enum of PrimitiveType * string list * string option

type NestedType =
    | Array
    | Object
    | Property

type CustomPayloadType =
    | String
    | UuidSuffix
    | Header

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
    }

/// The payload for a property specified in as a request parameter
type FuzzingPayload =
    /// Example: (Int "1")
    | Constant of PrimitiveType * string

    /// Example: (Int "1")
    | Fuzzable of PrimitiveType * string

    /// The custom payload, as specified in the fuzzing dictionary
    | Custom of CustomPayload

    | DynamicObject of string

    /// In some cases, a payload may need to be split into multiple payload parts
    | PayloadParts of FuzzingPayload list

/// The unique ID of a request.
type RequestId =
    {
        endpoint : string
        method : OperationMethod
    }

/// Object IDs are currently names, but could be extended to
/// both the name and the type (as declared in the API spec) in the future.
type ResourceId =
    {
        requestId : RequestId
        resourceName : string
    }


type AnnotationResourceReference =
    /// A resource parameter may be obtained by name only
    | ResourceName of string

    /// A resource parameter must be obtained in context, via its full path.
    | ResourcePath of AccessPath

/// Using this annotation, dependencies are resolved
/// Note: the actual producer and consumer must be present, otherwise the annotation is invalid.
type ProducerConsumerAnnotation =
    {
        producerId : ResourceId
        producerParameter : AnnotationResourceReference
        consumerParameter : AnnotationResourceReference
        exceptConsumerId: RequestId option
    }
    //with
    //    /// Given the 'consumerParameter', returns the access path or None if the consumer parameter
    //    /// is a name.
    //    member x.tryGetConsumerAccessPath =
    //        match x.consumerParameter with
    //        | ResourceName _ -> None
    //        | ResourcePath parts ->
    //            Some (parts |> String.concat ";")

    //    member x.tryGetProducerAccessPath =
    //        match x.producerParameter with
    //        | ResourceName _ -> None
    //        | ResourcePath parts ->
    //            Some (parts |> String.concat ";")


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

/// The payload for request parameters
type RequestParametersPayload =
    | ParameterList of seq<string * ParameterPayload>
    | Example of FuzzingPayload

/// All request parameters
type RequestParameters =
    {
        path: RequestParametersPayload

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


type ResponseProducerWriterVariable =
    {
        requestId : RequestId
        accessPathParts: AccessPath
    }

/// Information needed to generate a response parser
type ResponseParser =
    {
        writerVariables : ResponseProducerWriterVariable list
    }

/// The parts of a request
type RequestElement =
    | Method of OperationMethod
    | Path of FuzzingPayload list
    | QueryParameters of RequestParametersPayload
    | Body of RequestParametersPayload
    | Token of string
    | RefreshableToken
    | Headers of (string * string) list
    | HttpVersion of string
    | ResponseParser of ResponseParser option
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

        path : FuzzingPayload list

        queryParameters : (ParameterPayloadSource * RequestParametersPayload) list

        bodyParameters : (ParameterPayloadSource * RequestParametersPayload) list

        /// The token required to access the API
        token : TokenKind

        headers : (string * string) list

        httpVersion : string

        /// The generated response parser.  This is only present if there is at least
        /// one consumer for a property of the response.
        responseParser : ResponseParser option

        /// The additional properties of a request
        requestMetadata : RequestMetadata
    }

/// Definitions necessary for the RESTler algorithm
type GrammarDefinition =
    {
        Requests : Request list
    }


let generateDynamicObjectVariableName (requestId:RequestId) (accessPath:AccessPath option) delimiter =
    // split endpoint, add "id" at the end.  TBD: jobs_0 vs jobs_1 - where is the increment?
    // See restler_parser.py line 800
    let replaceTargets = [|"/"; "."; "__"; "{"; "}"; "$"; "-" |]

    let endpointParts = requestId.endpoint.Split(replaceTargets, System.StringSplitOptions.None)
                        |> Array.toList

    let objIdParts =
        match accessPath with
        | None -> Array.empty
        | Some ap -> ap.getPathPartsForName()
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
