// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.Engine.Settings

open System.IO
open Restler.Grammar
open Microsoft.FSharpLu
open Newtonsoft.Json.Linq

module Constants =
    [<Literal>]
    let PerResourceSettingsKey = "per_resource_settings"

    [<Literal>]
    let ProducerTimingDelayKey = "producer_timing_delay"

    [<Literal>]
    let CustomDictionaryKey = "custom_dictionary"

    [<Literal>]
    let MaxParameterCombinationsKey = "max_combinations"

    [<Literal>]
    let DefaultParameterCombinations = 20

type EngineSettings = {
        settings : JObject
    }
    with
        member x.getPerResourceSettings() =
            match Restler.Utilities.JsonParse.getProperty x.settings Constants.PerResourceSettingsKey with
            | Some o -> Some (o.Value<JObject>())
            | None -> None

        member x.getPerResourceDictionary endpoint =
            match x.getPerResourceSettings() with
            | None -> None
            | Some prs ->
                let resourceSettings = Restler.Utilities.JsonParse.getProperty prs endpoint
                match resourceSettings with
                | None -> None
                | Some rs ->
                    Restler.Utilities.JsonParse.getPropertyAsString (rs.Value<JObject>()) Constants.CustomDictionaryKey

        /// Gets the recipe location for the body payload checker
        member x.getBodyPayloadRecipeFilePath() =
            let checkersKey, payloadBodyKey, recipeFileKey = ("checkers", "payloadbody", "recipe_file")

            let getProperty settings propertyName =
                match Restler.Utilities.JsonParse.getProperty settings propertyName with
                | Some o -> Some (o.Value<JObject>())
                | None -> None

            let checkerSettings = getProperty x.settings checkersKey
            match checkerSettings with
            | None -> None
            | Some checkers ->
                let payloadBody = getProperty checkers payloadBodyKey
                match payloadBody with
                | None -> None
                | Some pb ->
                    Restler.Utilities.JsonParse.getPropertyAsString pb recipeFileKey

        /// Add a default per-resource timing delay for any request declared as a long running operation
        member x.addPerResourceTimingDelays (requests:Request list) =
            // Add per-resource timing delay for any long running operations
            // The default timing delay is expected to be modified by the user.
            //
            let defaultTimingDelaySeconds = 0

            // Get the existing per-resource settings, or create them.
            let perResourceSettings =
                match x.getPerResourceSettings() with //  getSettingsValue engineSettings Constants.PerResourceSettingsKey
                | None -> JObject()
                | Some prs -> prs

            // The per-resource timing delays are in the following format
            //"per_resource_settings": {
            //    "/dnsZones/{zoneName}/{recordType}/{relativeRecordSetName}": {
            //           "producer_timing_delay" : 1 }
            //    "/dnsZones/{zoneName}": { "producer_timing_delay" : 5 }
            //  }
            //},
            requests
            |> List.iter (fun x -> if x.requestMetadata.isLongRunningOperation then
                                        let timingDelaySetting = JProperty(Constants.ProducerTimingDelayKey, defaultTimingDelaySeconds)
                                        match Restler.Utilities.JsonParse.getProperty perResourceSettings x.id.endpoint with
                                        | None ->
                                            // create the property
                                            let obj = JObject()
                                            obj.Add(timingDelaySetting)
                                            let prs = JProperty(x.id.endpoint, obj)

                                            // create the per-resource setting
                                            perResourceSettings.Add(prs)
                                        | Some prs ->
                                            // add the producer timing delay to the endpoint setting if it does not already exist.
                                            match Restler.Utilities.JsonParse.getProperty
                                                    (prs.Value<JObject>()) Constants.ProducerTimingDelayKey with
                                            | None ->
                                                prs.Value<JObject>().Add(timingDelaySetting)
                                            | Some x ->
                                                ()
                            )

            x.settings.Remove(Constants.PerResourceSettingsKey) |> ignore
            x.settings.Add(Constants.PerResourceSettingsKey, perResourceSettings)

        /// Serialize the per-resource dictionaries (by ID, to prevent name conflicts)
        member x.addPerResourceDictionaries (perResourceDictionaries:Map<string, string>)
                                            (engineSettingsFilePath:string option)
                                            (grammarOutputDirectoryPath:string) =
            // Get the existing per-resource settings, or create them.
            let perResourceSettings =
                match x.getPerResourceSettings() with
                | None -> JObject()
                | Some prs -> prs

            // The per-resource dictionaries are in the following format
            //"per_resource_settings": {
            //    "/dnsZones/{zoneName}/{recordType}/{relativeRecordSetName}": {
            //           "custom_dictionary" : "dict.json"
            //  },
            //    "/dnsZones/{zoneName}": {
            //           "custom_dictionary" : "c:\\temp\\dict.json"
            //  }
            //},
            perResourceDictionaries
            |> Map.iter (fun endpoint dictionaryName ->
                            let dictionaryFilePath =
                                // Use a relative path - new dictionaries are expected
                                // to be output to the same folder as the grammar.
                                let fileName = sprintf @"%s.json" dictionaryName
                                fileName
                            let dictionarySetting = JProperty(Constants.CustomDictionaryKey, dictionaryFilePath)
                            match Restler.Utilities.JsonParse.getProperty perResourceSettings endpoint with
                            | None ->
                                // create the property
                                let obj = JObject()
                                obj.Add(dictionarySetting)
                                let prs = JProperty(endpoint, obj)

                                // create the per-resource setting
                                perResourceSettings.Add(prs)
                            | Some prs ->
                                match Restler.Utilities.JsonParse.getProperty
                                        (prs.Value<JObject>()) Constants.CustomDictionaryKey with
                                | None ->
                                    prs.Value<JObject>().Add(dictionarySetting)
                                | Some prevValue ->
                                    // Note: the dictionary referenced from Swagger will still be written to the compile directory.
                                    // TODO: use the per-resource dictionary value from engine settings if it already exists.
                                    printfn "Warning: per-resource dictionary for endpoint %s already exists, preserving the current value: %A." endpoint prevValue

                                    let fullPath =
                                        let currentPath = prevValue.ToString()
                                        if System.IO.Path.IsPathRooted(currentPath) then
                                            currentPath
                                        else
                                            let engineSettingsDirectory = System.IO.Path.GetDirectoryName(engineSettingsFilePath.Value)
                                            System.IO.Path.Combine(engineSettingsDirectory, prevValue.ToString())
                                    if not (File.Exists(fullPath)) then
                                        printfn "ERROR: invalid dictionary path specified in per-resource settings: %s." fullPath
                            )

            x.settings.Remove(Constants.PerResourceSettingsKey) |> ignore
            x.settings.Add(Constants.PerResourceSettingsKey, perResourceSettings)

        /// Serialize the per-resource dictionaries (by ID, to prevent name conflicts)
        member x.addMaxCombinations =
            if not (x.settings.ContainsKey(Constants.MaxParameterCombinationsKey)) then
                // create the property
                let maxCombinations = JProperty(Constants.MaxParameterCombinationsKey, Constants.DefaultParameterCombinations)
                x.settings.Add(maxCombinations)

let getEngineSettings engineSettingsFilePath =
    if System.IO.File.Exists engineSettingsFilePath then
        try
            let text = System.IO.File.ReadAllText(engineSettingsFilePath)
            let json = JObject.Parse(text)
            Ok { settings = json }
        with e ->
            Error (e.Message)
    else
        Error (sprintf "ERROR: invalid path specified for engine settings: %s" engineSettingsFilePath)

let newEngineSettings() =
    Ok { settings = JObject() }

/// Updates the specified engine settings and writes them to the compiler output directory
let updateEngineSettings (requests:Request list)
                         (perResourceDictionaries:Map<string, string>)
                         (engineSettingsFilePath: string option)
                         grammarOutputDirectoryPath
                         newEngineSettingsFilePath =

    let engineSettings =
        match engineSettingsFilePath with
        | Some filePath ->
            getEngineSettings filePath
        | None ->
            newEngineSettings()

    match engineSettings with
    | Ok settings ->
        settings.addPerResourceTimingDelays requests
        settings.addPerResourceDictionaries perResourceDictionaries engineSettingsFilePath grammarOutputDirectoryPath
        settings.addMaxCombinations
        System.IO.File.WriteAllText(newEngineSettingsFilePath, settings.settings.ToString(Newtonsoft.Json.Formatting.Indented))
        Ok ()
    | Error str ->
        Error str


