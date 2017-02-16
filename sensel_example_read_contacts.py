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
import sensel, json

exit_requested = False;

def compare(file1, test):
    print('***************************************************************')
    train = json.loads(open(file1).read())
    key_maps = {}
    i = 0
    for k, v in train.items():
        if k in key_maps.keys():
            continue
        key_maps[k] = i
        i = i + 1

    for k, v in test.items():
        if k in key_maps.keys():
            continue
        key_maps[k] = i
        i = i + 1

    train_points = []
    test_points = []
    train_avg, test_avg = {}, {}
    for k,v in train.items():
        if train != {}:
            avg = sum(v)/len(v)
            train_avg[k] = avg
            train_points.append((key_maps[k], avg))
    print(train_avg)
    for k,v in test.items():
        if test != {}:
            avg = sum(v)/len(v)
            test_avg[k] = avg
            test_points.append((key_maps[k], avg))
    print(test_avg)

    result = {}
    for k in train.keys():
        if k not in test.keys():
            continue
        if (test_avg[k] <= (train_avg[k] + 20)) and (test_avg[k] >= (train_avg[k]-20)):
            result[k] = True
        else:
            result[k] = False
    return sum(result.values())/float(len(result.values()))

def contactToKey(c, KEYMAP):
    for name, key in KEYMAP.items():
        if key['x'] <= c.x_pos <= key['x'] + key['w'] and \
            key['y'] <= c.y_pos <= key['y'] + key['h']:
            return (name, key)
    return None

def lockScreen():
    loginPF = CDLL('/System/Library/PrivateFrameworks/login.framework/Versions/Current/login')
    result = loginPF.SACLockScreenImmediate()

def keypress_handler(ch):
    global exit_requested
    global FORCEMAP

    # print('FORCEMAP', FORCEMAP)
    # print(json.dumps(FORCEMAP), file=open('forcemap.data', 'w'))
    # os.system("plot.py forcemap.data")
    if chr(ch) == 'p':
        print('FORCEMAP', FORCEMAP)
        print(json.dumps(FORCEMAP), file=open('forcemap.data', 'w'))
#        lockScreen()
    if chr(ch) == '~':
        FORCEMAP.clear()
    if ch == 0x51 or ch == 0x71: #'Q' or 'q'
        print("Exiting Example...", end="\r\n");
        exit_requested = True;

def openSensorReadContacts():
    KEYMAP_RAW = [x.split() for x in open('keymap.txt').read().split('\n')]
    KEYMAP = {}
    for key in KEYMAP_RAW:
        if not key:
            continue
        x, y, w, h, name = key
        name = name.strip('//')
        KEYMAP[name] = {'x': float(x), 'y': float(y), 'w': float(w.strip('f')), 'h': float(h.strip('f'))}

    print('KEYMAP')
    print(KEYMAP)
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
    global last_updated_time
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
                try:
                    keyname, key = contactToKey(c, KEYMAP)
                    if keyname == 'Delete':
                        continue
                    print(time.time(), 'KEY:', keyname, key, c.total_force)
                    FORCEMAP[keyname].append(c.total_force)
                    time_now = time.time()
                    if ((time_now - last_updated_time) >= 3):
                        print('FORCEMAP', FORCEMAP)
                        last_updated_time = time_now
                        # print(json.dumps(FORCEMAP), file=open('test.data', 'w'))
                        print('***************************************************************')
                        comp = compare('chakshu.datatrain', FORCEMAP)
                        if (comp < 0.6):
                            lockScreen()
                        else:
                            print('CONTINUEING')


                    print
                    # print(json.dumps(FORCEMAP), file=open('forcemap.data', 'w'))
                except Exception as e:
                    print("error", e)
            if len(contacts) > 0:
                print("****", end="\r\n");

    sensel_device.stopScanning();
    sensel_device.closeConnection();
    keyboardReadThreadStop()

if __name__ == "__main__":
    openSensorReadContacts()
    
