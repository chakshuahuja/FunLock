#!/usr/bin/env python

##########################################################################
# Copyright 2015 Sensel, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
# http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
##########################################################################

import portable_getch
import threading


_kbthread_getch = portable_getch.Getch()
_kbthread_exit_requested = False
_kbthread_read_callback = None
_kbthread = None

def _kbReadThread(callback):
    global _kbthread_exit_requested

    while not _kbthread_exit_requested:
        ch = _kbthread_getch(0.1)
        if ch:
            callback(ch)


def keyboardReadThreadStart(callback):
    global _kbthread_exit_requested
    global _kbthread

    _kbthread_exit_requested = False
    _kbthread = threading.Thread(target=_kbReadThread, 
                                 name="KB_THREAD", 
                                 args=[callback])
    _kbthread.start()

def keyboardReadThreadStop():
    global _kbthread_exit_requested

    if _kbthread:
        _kbthread_exit_requested = True
        _kbthread.join()
