namespace Restler.Driver

open System
open System.IO
open System.Runtime.InteropServices
open System.Text
open Microsoft.FSharpLu.File

module Telemetry =

    let [<Literal>] TelemetryOptOutEnvVarName = "RESTLER_TELEMETRY_OPTOUT"

    let [<Literal>] AppInsightsInstrumentationSettingsKey = "restlerAppInsightsTelemetry"

    let getMicrosoftOptOut() =
        // Disable telemetry if the environment variable is set to 1 or true
        let optOutValues = ["1" ; "true"]
        let doNotSendTelemetry =
            match System.Environment.GetEnvironmentVariable(TelemetryOptOutEnvVarName) with
            | x when not (System.String.IsNullOrWhiteSpace x) ->
                optOutValues |> List.contains (x.ToLower())
            | _ -> false
        doNotSendTelemetry

    let getMachineIdFilePath() =
        let machineTelemetryIdFileName = "restler.telemetry.uuid"
        let restlerSettingsCacheDir =
            match Types.Platform.getOSPlatform() with
            | Types.Platform.Platform.Linux ->
                "~/.config/microsoft/restler"
            | Types.Platform.Platform.Windows ->
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData) + @"\Microsoft\Restler";
        if not (Directory.Exists(restlerSettingsCacheDir)) then
            // Re-tries are needed in case several RESTler instances are started on a new machine
            let retryCount = 3
            Files.createDirectoryWithRetries restlerSettingsCacheDir retryCount [] (TimeSpan.FromSeconds(10.0)) true
        restlerSettingsCacheDir ++ machineTelemetryIdFileName

    let rec initSharedFile machineGuid filePath retryCount (delay:TimeSpan) =
        let encoding = UnicodeEncoding()
        let readMachineGuid filePath =
            let incorrectFormatException = Exception("Telemetry error: incorrect format of machine Guid in shared settings.")
            let text = File.ReadLines(filePath, encoding)
            match text |> Seq.tryHead with
            | None -> raise incorrectFormatException
            | Some s ->
                match Guid.TryParse(s.Trim()) with
                | false, _ -> raise incorrectFormatException
                | true, g -> g

        if retryCount = 0 then
            raise (Exception("Telemetry error: could not initialize shared settings."))
        try
            readMachineGuid filePath
        with
        | :? FileNotFoundException ->
            // File does not exist.  Try to create it.
            try
                use writeFileStream = File.Open(filePath, FileMode.CreateNew, FileAccess.Write, FileShare.None)
                let info = encoding.GetBytes(machineGuid.ToString().ToCharArray())
                writeFileStream.Write(info, 0, info.Length)
                machineGuid
            with
            | :? IOException ->
                // The file is being created by another RESTler instance.
                System.Threading.Thread.Sleep(delay)
                initSharedFile machineGuid filePath (retryCount - 1) delay
        | :? IOException ->
            // The file is being created by another RESTler instance.
            System.Threading.Thread.Sleep(delay)
            initSharedFile machineGuid filePath (retryCount - 1) delay

    let getMachineId() =
        let filePath = getMachineIdFilePath()
        let machineId =
            initSharedFile (Guid.NewGuid()) filePath 5 (TimeSpan.FromSeconds(1.0))
        machineId