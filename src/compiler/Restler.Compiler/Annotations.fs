// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.Annotations

open System.Collections.Generic
open Restler.Grammar
open System
open System.IO
open Restler.Utilities.Dict
open Newtonsoft.Json.Linq
open Restler.Utilities.JsonParse

type ExceptConsumerUserAnnotation =
    {
       consumer_endpoint : string
       consumer_method : string
    }

type ProducerConsumerUserAnnotation =
    {
        producer_endpoint : string
        producer_method : string
        producer_resource_name : string
        consumer_param : string
        except : ExceptConsumerUserAnnotation option
    }

let parseAnnotation (ann:JToken) =
    let annJson = ann.ToString(Newtonsoft.Json.Formatting.None)

    match Microsoft.FSharpLu.Json.Compact.tryDeserialize<ProducerConsumerUserAnnotation>
            annJson with
    | Choice2Of2 error ->
        failwith (sprintf "Invalid producer annotation: %s (%s)" error annJson)
    | Choice1Of2 annotation ->
        let producerId = {
                            requestId =
                                {
                                    endpoint = annotation.producer_endpoint
                                    method = getOperationMethodFromString annotation.producer_method
                                }
                            resourceName = annotation.producer_resource_name
                            }
        // Initialize the consumer parameter based on whether a path or name is specified.
        let consumerParameter =
            match AccessPaths.tryGetAccessPathFromString annotation.consumer_param with
            | Some p ->
                ResourcePath p
            | None ->
                ResourceName annotation.consumer_param

        let producerParameter, producerId =
            match AccessPaths.tryGetAccessPathFromString producerId.resourceName with
            | Some p ->
                (ResourcePath p),
                { producerId with resourceName =
                                        match p.getNamePart() with
                                        | None -> failwith (sprintf "Invalid producer annotation: %A "producerId)
                                        | Some n -> n
                                        }
            | None ->
                (ResourceName producerId.resourceName),
                producerId

        Some {  ProducerConsumerAnnotation.producerId = producerId
                consumerParameter = consumerParameter
                producerParameter = producerParameter
                exceptConsumerId = None
             }

/// Gets annotation data from Json
/// This applies if the user specifies a separate file with annotations only
let getAnnotationsFromJson (annotationJson:JToken) =
    try
        annotationJson.Children()
        |> Seq.choose (fun ann -> parseAnnotation ann)
        |> Seq.toList
    with e ->
        printfn "ERROR: malformed annotations specified. %A" e.Message
        raise e

/// Gets the REST-ler dependency annotation from the extension data
/// The 'except' clause indicates that "all consumer IDs with resource name 'workflowName'
/// should be resolved to this producer, except for the indicated consumer endpoint (which
/// should use the dependency in order of resolution, e.g. custom dictionary entry.)
//{
///        "producer_resource_name": "name",
///        "producer_method": "PUT",
///        "consumer_param": "workflowName",
///        "producer_endpoint": "/subscriptions/{subscriptionId}/providers/Microsoft.Logic/workflows/{workflowName}",
///        "except": {
///            "consumer_endpoint": "/subscriptions/{subscriptionId}/providers/Microsoft.Logic/workflows/{workflowName}",
///            "consumer_method": "PUT"
///        }
///    },
///
let getAnnotationsFromExtensionData (extensionData:IDictionary<_, obj>) annotationKey  =
    let getAnnotationProperty (aDict:IDictionary<string, obj>) propertyName =
        match Restler.Utilities.Dict.tryGetString aDict propertyName with
        | None ->
            printfn "ERROR: Malformed annotation, no value specified for %s"  propertyName
            // Special error message for renamed properties.
            // (For now, we do not need to maintain backwards compatibility but this may change in the future.)
            if propertyName = "param" then
                printfn "Did you mean 'consumer_param'?"
            None
        | Some v ->
            Some v

    if isNull extensionData then Seq.empty
    else
        match extensionData |> Seq.tryFind (fun kvp -> kvp.Key = annotationKey) with
        | None -> Seq.empty
        | Some annotations ->
            match annotations.Value with
            | :? seq<obj> as annotationList ->
                annotationList
                |> Seq.choose (fun aDict ->
                                    let jObject = JObject.FromObject(aDict)
                                    parseAnnotation jObject)
            | _  ->
                printfn "%s" "ERROR: malformed annotation format"
                Seq.empty

let getGlobalAnnotationsFromFile filePath =
    if File.Exists filePath then
        let annFileText = System.IO.File.ReadAllText(filePath)
        let globalAnnotationsJson = JObject.Parse(annFileText)
        let globalAnnotationKey = "x-restler-global-annotations"
        match Restler.Utilities.JsonParse.getProperty globalAnnotationsJson globalAnnotationKey with
        | Some globalAnn ->
            getAnnotationsFromJson globalAnn
        | None ->
            printfn "ERROR: invalid annotation file: x-restler-global-annotations must be the key"
            raise (ArgumentException("invalid annotation file"))
    else
        List.empty