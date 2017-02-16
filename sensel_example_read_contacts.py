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

#
#  Read Contacts
#  by Aaron Zarraga - Sensel, Inc
# 
#  This opens a Sensel sensor, reads contact data, and prints the data to the console.
#
#  Note: We have to use \r\n explicitly for print endings because the keyboard reading code
#        needs to set the terminal to "raw" mode.
##

from __future__ import print_function
from keyboard_reader import *
import sensel

exit_requested = False;

def keypress_handler(ch):
    global exit_requested

    if ch == 0x51 or ch == 0x71: #'Q' or 'q'
        print("Exiting Example...", end="\r\n");
        exit_requested = True;


def openSensorReadContacts():
    sensel_device = sensel.SenselDevice()

    if not sensel_device.openConnection():
        print("Unable to open Sensel sensor!", end="\r\n")
        exit()

    keyboardReadThreadStart(keypress_handler)

    #Enable contact sending
    sensel_device.setFrameContentControl(sensel.SENSEL_FRAME_CONTACTS_FLAG)
  
    #Enable scanning
    sensel_device.startScanning()

    print("\r\nTouch sensor! (press 'q' to quit)...", end="\r\n")

    while not exit_requested: 
        frame = sensel_device.readFrame()
        if frame:
            (lost_frame_count, forces, labels, contacts) = frame
  
            if len(contacts) == 0:
                continue
       
            for c in contacts:
                event = ""
                if c.type == sensel.SENSEL_EVENT_CONTACT_INVALID:
                    event = "invalid"; 
                elif c.type == sensel.SENSEL_EVENT_CONTACT_START:
                    sensel_device.setLEDBrightness(c.id, 100) #Turn on LED
                    event = "start"
                elif c.type == sensel.SENSEL_EVENT_CONTACT_MOVE:
                    event = "move";
                elif c.type == sensel.SENSEL_EVENT_CONTACT_END:
                    sensel_device.setLEDBrightness(c.id, 0) #Turn off LED
                    event = "end";
                else:
                    event = "error";
        
                print("Contact ID %d, event=%s, mm coord: (%f, %f), force=%.3f, " 
                      "major=%f, minor=%f, orientation=%f" % 
                      (c.id, event, c.x_pos, c.y_pos, c.total_force, 
                       c.major_axis, c.minor_axis, c.orientation), end="\r\n")

            if len(contacts) > 0:
                print("****", end="\r\n");

    sensel_device.stopScanning();
    sensel_device.closeConnection();
    keyboardReadThreadStop()

if __name__ == "__main__":
    openSensorReadContacts()
    
