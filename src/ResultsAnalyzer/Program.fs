// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

module Restler.ResultsAnalyzer.Program

open System
open System.IO
open System.Text.RegularExpressions

open Restler.Dictionary
open Common.Abstractions

open Analyze.Main
open Overview
open OverviewDiff
open Timing
open Convert
open Diff.Main

// TODO Replace the manual parsing below by using a proper command line parser library.
// E.g., https://github.com/commandlineparser/commandline

// TODO If arguments (for diff mode in particular, but also in general) grow unwieldy, use config file.
// E.g., --config diff.json similar to RESTler compiler

let usage() =
    eprintfn @"
Usage: dotnet Restler.ResultsAnalyzer.dll <command> <args...> [<options...>]

Examples:
    ResultsAnalyzer analyze .\path\to\restler\results\
    ResultsAnalyzer overview .\path\to\network_log.txt --request-hashes-dir .\request-hashes\
    ResultsAnalyzer overview-diff .\network_log_A.txt .\network_log_B.txt -af .\dict.json -ah Date -aq api-version -ah Content-Length
    ResultsAnalyzer convert .\path\to\network_log.txt --json-body
    ResultsAnalyzer diff .\network_log_A.txt .\network_log_B.txt --json-body --only-requests --show-equal
    ResultsAnalyzer timing .\path\to\network_log.txt

Commands (and their options):

analyze <path to REST-ler network log directory or file>
    [--output_dir <output directory>]
    [--exclude_payload]
    [--dictionary_file <optional path to the fuzzing dictionary>]
    [--max_instances_per_bucket <number of instances per bucket>]

overview <network log>         Give an overview of the sent requests and received response ""types"".
    [--no-counts]                Do not show counts of requests/responses. Useful when diffing two overviews.
    [--no-summary]               Do not show summary overview at the beginning. Useful when diffing two overviews.
    [--request-hashes-dir <directory>]
                                 If given, outputs one text file per hash of the abstracted request (for debugging).
    <abstraction options...>     See below.

overview-diff <log A> <log B>  Compare two network logs in terms of their ""stateless"" overviews.
    <abstraction options...>     See below.

convert <network log>          Convert an unstructured, textual network log to JSON.
    [--json-body]                Assume request/response bodies are JSON. Will pretty-print bodies instead of
                                 treating them as plain strings, e.g., puts properties on new lines etc.

diff <log A> <log B>           Parse two network logs and output ""stateful"" or ""precise"" differences as JSON.
    [--json-body]                Assume request/response bodies are JSON. Gives finer differences.
    [--only-requests]            Diff only requests, ignore differences in responses.
                                 Useful for testing RESTler itself, i.e., how it generated requests.
    [--ignore-get-responses]     When diffing, ignore all response bodies of GET requests (because those are often
                                 false positives due to ""global state in the service"").
    [--show-equal]               Show parts that are equal in both logs, instead of shortening to the string ""Equal"".
    <abstraction options...>     See below.

timing <network log>           Output CSV (comma-separated values) of delays for all (request, response) pairs in the network log.
    <abstraction options...>     See below.

Abstractions:                  Replace a pattern with a fixed string, either to ignore this pattern during diffing
                               or to group similar requests together when building the request map.
                               Some abstractions can be given multiple times: -ah, -aq, -as, and -ac.
    [-au, --abstract-uuid]       Abstract UUIDs, see https://en.wikipedia.org/wiki/Universally_unique_identifier#Format
    [-ah, --abstract-header <regex>]
                                 Abstract HTTP header values where the header name matches <regex>.
    [-aq, --abstract-query-parameter <regex>]
                                 Abstract HTTP query parameter values where the parameter name matches <regex>.
    [-as, --abstract-random-suffix <regex>]
                                 Abstract any <regex> that is followed by 10 random hex digits (5 random bytes).
                                 E.g., ""prefixA-|prefixB_"" would match ""prefixA-aadeadbeef"" and ""prefixB_0a1b2c3d4e"".
    [-af, --abstract-dictionary-file <dictionary.json file>]
                                 Abstract over all restler_custom_uuid4_suffix values in the dictionary file, as if they
                                 were individually given via -as.
    [-ac, --abstract-custom <regex>]
                                 Abstract any string in the HTTP path, query, headers, or body that matches <regex>.
"

    exit 1

module AnalyzeArgs =
    let rec parse (parsedArgs:AnalyzeArgs) = function
        | "--output_dir"::outputDir::rest ->
            if not (Directory.Exists outputDir) then
                eprintfn "Directory %s does not exist." outputDir
                usage()
            parse { parsedArgs with outputDirPath = outputDir } rest
        | "--exclude_payload"::rest -> parse { parsedArgs with includePayload = false } rest
        | "--dictionary_file"::dictionaryFilePath::rest ->
            parse { parsedArgs with fuzzingDictionaryPath = Some dictionaryFilePath } rest
        | "--max_instances_per_bucket"::maxInstances::rest ->
            match Int32.TryParse(maxInstances) with
            | (false, _) ->
                eprintfn "Invalid maximum number of instances given: %s" maxInstances
                usage()
            | (true, i) ->
                parse { parsedArgs with maxInstancesPerBucket = i } rest
        | [] ->
            if String.IsNullOrWhiteSpace parsedArgs.logsPath then
                eprintfn "You must specify the logs directory to analyze."
                usage()
            if not (File.Exists parsedArgs.logsPath || Directory.Exists parsedArgs.logsPath) then
                eprintfn "Directory '%s' does not exist." parsedArgs.logsPath
                usage()
            parsedArgs
        | invalidArgument::_rest ->
            eprintfn "Invalid argument: %s" invalidArgument
            usage()

/// Tries to parse a single abstraction option, and returns the parsed ones and the remaining arguments.
/// For the syntax/construct, see https://docs.microsoft.com/en-us/dotnet/fsharp/language-reference/active-patterns#parameterized-active-patterns
let (|AbstractionOptions|_|) (parsedOptions:AbstractionOptions) = function
    // TODO wrap in try ... catch and do nicer error message on invalid Regex
    | "-au"::rest | "--abstract-uuid"::rest ->
        Some ({ parsedOptions with abstractUuid = true }, rest)
    | "-ah"::regex::rest | "--abstract-header"::regex::rest ->
        Some ({ parsedOptions with abstractHeader = new Regex(regex) :: parsedOptions.abstractHeader }, rest)
    | "-aq"::regex::rest | "--abstract-query-parameter"::regex::rest ->
        Some ({ parsedOptions with abstractQueryParameter = new Regex(regex) :: parsedOptions.abstractQueryParameter }, rest)
    | "-as"::regex::rest | "--abstract-random-suffix"::regex::rest ->
        Some ({ parsedOptions with abstractRandomSuffix = new Regex(regex) :: parsedOptions.abstractRandomSuffix }, rest)
    | "-ac"::regex::rest | "--abstract-custom"::regex::rest ->
        Some ({ parsedOptions with abstractCustom = new Regex(regex) :: parsedOptions.abstractCustom }, rest)
    | "-af"::dictionaryFile::rest | "--abstract-dictionary-file"::dictionaryFile::rest ->
        let dictionarySuffixes =
            match Microsoft.FSharpLu.Json.Compact.tryDeserializeFile<Restler.Dictionary.MutationsDictionary> dictionaryFile with
            | Choice1Of2 d ->
                d.restler_custom_payload_uuid4_suffix
                |> Option.defaultValue Map.empty
                |> Map.toSeq
                |> Seq.map (fun (_jsonProperty, jsonValue) -> new Regex(jsonValue))
                |> Seq.toList
            | Choice2Of2 e ->
                eprintfn "Cannot deserialize mutations dictionary: %s" e
                exit 1
        Some ({ parsedOptions with abstractRandomSuffix = dictionarySuffixes @ parsedOptions.abstractRandomSuffix}, rest)
    | _ -> None

// TODO add --out/-o parameter to write to file with UTF-8 (no BOM).

module TimingArgs =
    let rec parse (parsedArgs:TimingArgs) = function
        | AbstractionOptions parsedArgs.abstractionOptions (abstractionOptions, rest) -> parse { parsedArgs with abstractionOptions = abstractionOptions } rest
        | [] ->
            if String.IsNullOrWhiteSpace parsedArgs.logFile then
                eprintfn "You must give a network log file to build the request map."
                usage()
            parsedArgs
        | invalidArgument::_rest ->
            eprintfn "Invalid argument: %s" invalidArgument
            usage()

module OverviewArgs =
    let rec parse (parsedArgs:OverviewArgs) = function
        | "--no-counts"::rest -> parse { parsedArgs with includeCounts = false } rest
        | "--no-summary"::rest -> parse { parsedArgs with includeSummary = false } rest
        | "--request-hashes-dir"::directory::rest -> parse { parsedArgs with requestHashesDir = Some directory } rest
        | AbstractionOptions parsedArgs.abstractionOptions (abstractionOptions, rest) -> parse { parsedArgs with abstractionOptions = abstractionOptions } rest
        | [] ->
            if String.IsNullOrWhiteSpace parsedArgs.logFile then
                eprintfn "You must give a network log file to overview."
                usage()
            parsedArgs
        | invalidArg::_rest ->
            eprintfn "Invalid argument: '%s'" invalidArg
            usage()

module OverviewDiffArgs =
    let rec parse (parsedArgs:OverviewDiffArgs) = function
        | AbstractionOptions parsedArgs.abstractionOptions (abstractionOptions, rest) -> parse { parsedArgs with abstractionOptions = abstractionOptions } rest
        | [] ->
            if parsedArgs.logFiles |> fst |> String.IsNullOrWhiteSpace || parsedArgs.logFiles |> snd |> String.IsNullOrWhiteSpace then
                eprintfn "You must give two network log files to diff."
                usage()
            parsedArgs
        | invalidArg::_rest ->
            eprintfn "Invalid argument: '%s'" invalidArg
            usage()

module ConvertArgs =
    let rec parse (parsedArgs:ConvertArgs) = function
        | "--json-body"::rest -> parse { parsedArgs with jsonBody = true } rest
        | [] ->
            if String.IsNullOrWhiteSpace parsedArgs.logFile then
                eprintfn "You must give a network log file to convert."
                usage()
            parsedArgs
        | invalidArg::_rest ->
            eprintfn "Invalid argument: '%s'" invalidArg
            usage()

module DiffArgs =
    let rec parse (parsedArgs:DiffArgs) = function
        | "--json-body"::rest -> parse { parsedArgs with jsonBody = true } rest
        | "--only-requests"::rest -> parse { parsedArgs with onlyRequests = true } rest
        | "--ignore-get-responses"::rest -> parse { parsedArgs with ignoreGetResponses = true } rest
        | "--show-equal"::rest -> parse { parsedArgs with showEqual = true } rest
        | AbstractionOptions parsedArgs.abstractionOptions (abstractionOptions, rest) -> parse { parsedArgs with abstractionOptions = abstractionOptions } rest
        | [] ->
            let (logFileA, logFileB) = parsedArgs.logFiles
            if String.IsNullOrWhiteSpace logFileA || String.IsNullOrWhiteSpace logFileB then
                eprintfn "You must give two network log files to diff."
                usage()
            parsedArgs
        | invalidArg::_rest ->
            eprintfn "Invalid argument: '%s'" invalidArg
            usage()

[<EntryPoint>]
let main argv =
    match Array.toList argv with
    | "analyze"::logsPath::args -> args |> AnalyzeArgs.parse (AnalyzeArgs.initWithDefaults logsPath) |> Analyze.Main.main
    | "timing"::logFile::args -> args |> TimingArgs.parse (TimingArgs.initWithDefaults logFile) |> Timing.main
    | "overview"::logFile::args -> args |> OverviewArgs.parse (OverviewArgs.initWithDefaults logFile) |> Overview.main
    | "overview-diff"::logA::logB::args -> args |> OverviewDiffArgs.parse (OverviewDiffArgs.initWithDefaults (logA, logB)) |> OverviewDiff.main
    | "convert"::logFile::args -> args |> ConvertArgs.parse (ConvertArgs.initWithDefaults logFile) |> Convert.main
    | "diff"::logA::logB::args -> args |> DiffArgs.parse (DiffArgs.initWithDefaults logA logB) |> Diff.Main.main
    | _ -> eprintfn "Unknown command or missing required argument for a particular command."; usage()
    0
