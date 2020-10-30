// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/// Types used to identify resources in an API specification and
/// infer their types and dependencies.
module Restler.ApiResourceTypes
open System
open Restler.Grammar
open Restler.AccessPaths

type NamingConvention = Config.NamingConvention

let RegexSplitMap =
    let camelCaseRegexSplit = "(?=\p{Lu}\p{Ll})|(?<=\p{Ll})(?=\p{Lu})"
    [
        NamingConvention.CamelCase, camelCaseRegexSplit
        NamingConvention.PascalCase, camelCaseRegexSplit
        NamingConvention.HyphenSeparator, "-"
        NamingConvention.UnderscoreSeparator, "_"
    ]
    |> List.map (fun (x,y) -> (x, System.Text.RegularExpressions.Regex(y)))
    |> Map.ofList

/// Reference to a parameter passed in the body of a request or
/// or returned in a response
type JsonParameterReference =
    {
        name : string
        fullPath: AccessPath
    }

/// The path up to the parameter name
type PathParameterReference =
    {
        name : string
        pathToParameter: string []
        responsePath : AccessPath
    }

/// A resource is identified by its path, either in the path, query, or body.
/// Path: defined by the full path parts, up to the name.
/// Query: defined by the name only.
/// Body: defined by the json pointer to the resource.
///
/// Every resource is considered in the context of its API (endpoint and method).
type ResourceReference =
    /// A path parameter
    | PathResource of PathParameterReference
    /// A query parameter
    | QueryResource of string
    /// A body parameter
    | BodyResource of JsonParameterReference

let private pluralizer = Pluralize.NET.Core.Pluralizer()

/// The resource id.
/// The type name is inferred during construction.
/// Note: resource IDs may use several naming conventions in the same one.  This is not currently supported.
/// For example: "/admin/pre-receive-environments/{pre_receive_environment_id}"
type ApiResource(requestId:RequestId,
                 resourceReference:ResourceReference,
                 namingConvention:NamingConvention option,
                 primitiveType:PrimitiveType) =
    let endpointParts = requestId.endpoint.Split([|'/'|], StringSplitOptions.RemoveEmptyEntries)

    // Gets the first non path parameter of this endpoint
    let getContainerPartFromPath (pathParts:string[]) =
        let getContainer (pathPart:string option) =
            match pathPart with
            | None -> None
            | Some p ->
                if p.StartsWith("{") then None
                else pathPart

        // The last part may be a container (e.g. for POST)
        // If not, then try to find it in the second part.
        seq {
            yield getContainer (pathParts |> Array.tryLast)
            yield getContainer (pathParts |> Array.tryItem (pathParts.Length - 2))
        }
        |> Seq.choose (fun x -> x)
        |> Seq.tryHead

    let getContainerPartFromBody (jsonPointer:AccessPath) =
        let propertiesOnly =
            jsonPointer.path
            // Remove array indexes
            |> Array.filter (fun x -> not (x.StartsWith("[") && x.EndsWith("]")))
        propertiesOnly |> Array.tryItem (propertiesOnly.Length - 2)

    let getBodyContainerName() =
        match resourceReference with
        | PathResource pr ->
            getContainerPartFromBody pr.responsePath
        | QueryResource qr ->
            None
        | BodyResource br ->
            getContainerPartFromBody br.fullPath

    let resourceName =
        match resourceReference with
        | PathResource pr ->
            pr.name
        | QueryResource qr ->
            qr
        | BodyResource br ->
            br.name

    let isNestedBodyResource =
        match resourceReference with
        | PathResource pr ->
            false
        | QueryResource qr ->
            false
        | BodyResource br ->
            br.fullPath.getPathPropertyNameParts().Length > 1

    let getContainerName() =
        let containerNamePart =
            match resourceReference with
            | PathResource pr ->
                getContainerPartFromPath pr.pathToParameter
            | QueryResource qr ->
                getContainerPartFromPath endpointParts
            | BodyResource br ->
                // If the path to property contains at least 2 identifiers, then it has a body container.
                if isNestedBodyResource then
                    getContainerPartFromBody br.fullPath
                else
                    getContainerPartFromPath endpointParts

        containerNamePart

    let containerName = getContainerName()
    let bodyContainerName = getBodyContainerName()
    let pathContainerName = getContainerPartFromPath endpointParts

    /// Infer the naming convention.
    // The naming convention is inferred from the container if present.
    // Otherwise, infer it from the resource name.
    // If not possible to infer, the default (camel case) is used.
    let getConvention (str:string) =
        let hasUpper = str |> Seq.exists (fun x -> Char.IsUpper x)
        let hasLower = str |> Seq.exists (fun x -> Char.IsLower x)
        let hasUnderscores = str.Contains("_")
        let hasHyphens = str.Contains("-")
        let startsWithUpper = Char.IsUpper(str.[0])

        if hasUpper && hasLower then
            if startsWithUpper then
                NamingConvention.PascalCase
            else
                NamingConvention.CamelCase
        else if hasUnderscores then
            NamingConvention.UnderscoreSeparator
        else if hasHyphens then
            NamingConvention.HyphenSeparator
        else
            // Use CamelCase as the default
            NamingConvention.CamelCase

    let getTypeWords name =
        // Infer the convention if it is not already set.
        // Each name (e.g. container vs. resource names) may have a different convention.
        // For example: the-accounts/{the_account_id}
        let typeNamingConvention =
            match namingConvention with
            | None -> getConvention name
            | Some c -> c
        let nameRegexSplit = RegexSplitMap.[typeNamingConvention]
        nameRegexSplit.Split(name)
        |> Array.filter (fun x -> not (String.IsNullOrEmpty x))

    let resourceNameWords = getTypeWords resourceName

    /// Gets the candidate type names for this resource, based on its container.
    /// This function currently uses heuristics to infer a set of possible type names
    /// based on the word parts of the container name, as determined by naming convention.
    /// Note: this function normalizes the original identifier names after splitting the names
    /// based on naming convention.  Make sure producer-consumer inference
    /// uses only the normalized type names.
    let getCandidateTypeNames() =
        let normalizedSeparator = "__"
        // Candidate types based on the container
        match containerName with
        | Some c ->
            let containerNameWithoutPlural = pluralizer.Singularize(c)
            let containerWords = getTypeWords containerNameWithoutPlural

            match bodyContainerName with
            | None ->
                // The top-level container should be just the container name
                [containerWords |> String.concat normalizedSeparator]
            | Some _ ->
                // Heuristic: try all of the suffixes and
                // removing the last suffix, in addition to the full name.
                let candidateTypeNames = seq {
                    for i in 0..containerWords.Length - 1 do
                        yield containerWords.[i..containerWords.Length-1] |> String.concat normalizedSeparator
                    if containerWords.Length > 2 then
                        let removeSuffix = containerWords.[0..containerWords.Length-2] |> String.concat normalizedSeparator
                        yield pluralizer.Singularize(removeSuffix)
                }
                candidateTypeNames |> Seq.toList
        | None ->
            // Candidate types based on the resource name, in case the container is empty
            let primaryParameterName =
                match resourceNameWords with
                | [||] ->
                    raise (Exception("The resource name must be non-empty."))
                | [|w|] ->
                    w
                | words ->
                    // accountId -> account
                    words.[0..words.Length - 2] |> String.concat normalizedSeparator
            [ primaryParameterName ]

    let candidateTypeNames = getCandidateTypeNames() |> List.map (fun x -> x.ToLower())

    let typeName = candidateTypeNames |> List.head

    /// The request ID in which this resource is declared in the API spec
    member x.RequestId = requestId

    /// The reference identifying the resource
    member x.ResourceReference = resourceReference

    /// The name of the resource container, if it exists.
    /// The container is the static parent of this resource - if the immediate parent
    /// is a path parameter, this is considered as container not defined.
    member x.ContainerName = containerName
    member x.BodyContainerName = bodyContainerName
    member x.PathContainerName = pathContainerName

    /// The inferred type name of the resource
    /// These are expected to be sorted in order of most specific to least specific type
    member x.CandidateTypeNames = candidateTypeNames

    /// The naming convention.  (Required for serialization.)
    member x.NamingConvention = namingConvention

    member x.AccessPath =
        match resourceReference with
        | BodyResource b -> b.fullPath.getJsonPointer()
        | PathResource p ->
            p.responsePath.getJsonPointer()
        | QueryResource q -> None

    member x.AccessPathParts =
        match resourceReference with
        | BodyResource b -> b.fullPath
        | PathResource p -> p.responsePath
        | QueryResource q -> { AccessPath.path = Array.empty }

    member x.getParentAccessPath() =
        match resourceReference with
        | BodyResource b -> b.fullPath.getParentPath()
        | PathResource p -> p.responsePath.getParentPath()
        | QueryResource q -> { path = Array.empty }

    member x.ResourceName =
        match resourceReference with
        | BodyResource b -> b.name
        | PathResource p -> p.name
        | QueryResource q -> q

    // Gets the variable name that should be present in the response
    // Example: /api/accounts/{accountId}
    //   * the var name is "Id" --> "id"
    member x.ProducerParameterName =
        let p = resourceNameWords |> Array.last
        p.ToLower()

    member x.IsNestedBodyResource = isNestedBodyResource

    member x.PrimitiveType = primitiveType

    override x.ToString() =
        sprintf "%A %s %A"
                x.RequestId x.ResourceName x.AccessPath

/// A consumer resource.  For example, the 'accountId' path parameter in the below request
/// 'accountId', '/api/accounts/{accountId}', GET
type Consumer =
    {
        id: ApiResource

        /// The parameter type of the consumer
        parameterKind : ParameterKind

        /// The annotation for this consumer, if specified
        annotation: ProducerConsumerAnnotation option
    }

type ResponseProducer =
    {
        id : ApiResource
    }

type BodyPayloadInputProducer = ResponseProducer

/// A producer resource.  For example, the 'accountId' property returned in the response of
/// the below request.
/// '/api/userInfo', GET
type Producer =
    /// A resource value specified as a payload in the custom dictionary.
    /// (payloadType, consumerResourceName, isObject)
    /// To be converted to 'consumerResourcePath' in VSTS#7191
    | DictionaryPayload of CustomPayloadType * PrimitiveType * string * bool

    /// A resource value produced in a response of the specified request.
    | ResponseObject of ResponseProducer

    /// A resource value that comes from the same body payload.
    | SameBodyPayload of ResponseProducer

type ProducerConsumerDependency =
    {
        /// The consumer of the resource.
        /// Any consumer, as described by the 'Consumer' type above, is valid in this context.
        /// For example: 'accountId', '/api/accounts/{accountId}/users', PUT
        consumer : Consumer
        /// The producer of the resource.  Any producer, as described by the 'Producer' type
        /// above, is valid in this context.
        /// '/api/userInfo', GET,
        producer : Producer option
    }
