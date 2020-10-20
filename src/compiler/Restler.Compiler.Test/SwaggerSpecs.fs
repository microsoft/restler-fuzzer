// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

namespace Restler.Test

open System
open System.IO
open Restler.Config

/// The Swagger specifications for real-world examples, which may be used across several test suites to test
/// different areas of RESTler.  Each spec will be tested at least once in this default configuration, but tests
/// may also modify it to test specific features (e.g. payload fuzzing, examples, etc.).
module SwaggerSpecs =

    let configs =
        [
            ("demo_server",
                { DefaultConfig with
                    SwaggerSpecFilePath = Some [(Path.Combine(Environment.CurrentDirectory, @"swagger\demo_server.json")) ]
                    IncludeOptionalParameters = true
                })
        ] |> Map.ofSeq
