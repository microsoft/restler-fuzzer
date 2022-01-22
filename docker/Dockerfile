FROM mcr.microsoft.com/dotnet/aspnet:5.0-alpine

COPY ./compiler /RESTler/compiler
COPY ./restler /RESTler/restler

#Get the source code for the engine, and
#copy source code to the image
#RESTler Python dependency
RUN apk add --no-cache python3
RUN python3 -m ensurepip
RUN pip3 install --upgrade pip
RUN pip3 install requests
RUN pip3 install requests
RUN pip3 install applicationinsights
COPY ./engine /RESTler/engine
RUN python3 -m compileall -b /RESTler/engine
COPY ./resultsAnalyzer /RESTler/resultsAnalyzer
