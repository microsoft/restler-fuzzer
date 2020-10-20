# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import datetime
import time

def timestamp():
    epoch = time.time()
    ts = datetime.datetime.fromtimestamp(epoch)
    # Year-Month-Day Hour:Minute:Second.millisecond
    return ts.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]