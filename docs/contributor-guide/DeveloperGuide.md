# Developer Guide


## Components

RESTler components include:

- Compiler:
  - Written in F#
  - Uses [NSwag](https://github.com/RicoSuter/NSwag) to parse Swagger/OpenAPI specifications
  - Generates a fuzzing grammar from the specification
- Engine:
  - Written in Python
  - Takes a fuzzing grammar and executes tests against the API
  - Pluggable architecture for custom checkers, which can be passed on the command line
- Results analyzer:
  - Written in F#
  - Parses the RESTler engine logs and generates error summary
- Driver:
  - Written in F#
  - Wrapper for the RESTler workflow

## Tools

F#: Visual Studio 2019 version 16.7 or higher is recommended.

Python: Visual Studio Code is recommended.  See [EngineGettingStarted.md](EngineGettingStarted.md).

