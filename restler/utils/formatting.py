# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from datetime import datetime, timezone
import time

def timestamp():
    epoch = time.time()
    ts = datetime.fromtimestamp(epoch)
    # Year-Month-Day Hour:Minute:Second.millisecond
    return ts.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

def iso_timestamp():
    dt = datetime.now(timezone.utc)
    iso_timestamp = dt.isoformat()
    return iso_timestamp
