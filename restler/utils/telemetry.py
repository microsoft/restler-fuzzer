# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

""" Telemetry module. """

from applicationinsights import TelemetryClient

#Instrumentation key is from app insights resource in Azure Portal
instrumentation_key = '6a4d265f-98cd-432f-bfb9-18ced4cd43a9'

class RestlerTelemetryClient():
    def __init__(self, machine_id):
        self.__telemetry_client = TelemetryClient(instrumentation_key)
        self.__machine_id = machine_id

    def restler_started(self, version, task, execution_id, features_list):
        properties = {
            'machineId' : machine_id,
            'version' : version,
            'executionId' : execution_id,
            'task' : task
        }
        self.__telemetry_client.track_event(
                    'restler started', {**properties, **features_list})

    def flush(self):
        self.__telemetry_client.flush()

machine_id = "0000-00-0000"
restler_telemetry = RestlerTelemetryClient(machine_id)
