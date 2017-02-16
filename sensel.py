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

import sys
PY3 = sys.version > '3'

from ctypes import *
from sensel_register_map import *
import platform
import glob
import logging
import serial
import serial.tools.list_ports;
import threading
import time
import math
if PY3:
    import queue
else:
    import Queue

from struct import * #pack()

sensel_lib = None

SENSEL_LOGGING_LEVEL = logging.WARNING #(DEBUG/INFO/WARNING/ERROR/CRITICAL)

SENSEL_BAUD = 115200
SENSEL_TIMEOUT = 1

if PY3:
    SENSEL_MAGIC = b'S3NS31'
else:
    SENSEL_MAGIC = 'S3NS31'

SENSEL_FRAME_PRESSURE_FLAG = 0x01
SENSEL_FRAME_LABELS_FLAG   = 0x02
SENSEL_FRAME_CONTACTS_FLAG = 0x04
SENSEL_FRAME_ACCEL_FLAG    = 0x08
    
SENSEL_PT_RESERVED           = 0
SENSEL_PT_READ_ACK           = 1
SENSEL_PT_READ_NACK          = 2
SENSEL_PT_RVS_ACK            = 3
SENSEL_PT_RVS_NACK           = 4
SENSEL_PT_WRITE_ACK          = 5
SENSEL_PT_WRITE_NACK         = 6
SENSEL_PT_WVS_ACK            = 7
SENSEL_PT_WVS_NACK           = 8

SENSEL_EVENT_CONTACT_INVALID = 0
SENSEL_EVENT_CONTACT_START   = 1
SENSEL_EVENT_CONTACT_MOVE    = 2
SENSEL_EVENT_CONTACT_END     = 3

SENSEL_BOARD_ADDR = 0x01
SENSEL_READ_HEADER = (SENSEL_BOARD_ADDR | (1 << 7))
SENSEL_WRITE_HEADER = (SENSEL_BOARD_ADDR)


EC_OK = 0
EC_REG_INVALID_ADDRESS = 1
EC_REG_INVALID_VALUE = 2
EC_REG_INVALID_PERMISSIONS = 3

sensel_serial = None
sensel_shift_dims = math.pow(2,8)
sensel_shift_force = math.pow(2,3)
sensel_shift_area = math.pow(2,0)
sensel_shift_angle = math.pow(2,4)

_serial_lock = None

forces = None
labels = None
decompressed_cols = 0
decompressed_rows = 0

SENSEL_DEVICE_INFO_SIZE = 9

class SenselDeviceInfo():
    def __init__(self, data):
        self.fw_protocol_version = _convertBufToVal(data[0:1])
        self.fw_version_major =    _convertBufToVal(data[1:2])
        self.fw_version_minor =    _convertBufToVal(data[2:3])
        self.fw_version_build =    _convertBufToVal(data[3:5])
        self.fw_version_release =  _convertBufToVal(data[5:6])
        self.device_id =        _convertBufToVal(data[6:8])
        self.device_revision =  _convertBufToVal(data[8:9])

class SenselContact():
    data_size = 16

    def __init__(self, data):
        if(len(data) != SenselContact.data_size):
            logging.error("Unable to create SenselContact. Data length (%d) != contact length (%d)" %
                          (len(data), SenselContact.data_size))
            raise Exception
        
        self.id =          _convertBufToVal(data[0:1])
        self.type =        _convertBufToVal(data[1:2])
        self.x_pos =       _convertBufToVal(data[2:4])/(1.0*sensel_shift_dims)
        self.y_pos =       _convertBufToVal(data[4:6])/(1.0*sensel_shift_dims)
        self.total_force = _convertBufToVal(data[6:8])/(1.0*sensel_shift_force)
        self.area =        _convertBufToVal(data[8:10])/(1.0*sensel_shift_area)
        self.orientation =  (unpack('h', pack('H',_convertBufToVal(data[10:12])))[0])/(1.0*sensel_shift_angle)
        self.major_axis =        _convertBufToVal(data[12:14])/(1.0*sensel_shift_dims)
        self.minor_axis =        _convertBufToVal(data[14:16])/(1.0*sensel_shift_dims)

    def __str__(self):
        retstring = "Sensel Contact:\n"
        retstring += "id:          %d\n" % self.id
        retstring += "type:        %d\n" % self.type
        retstring += "x_pos:       %d\n" % self.x_pos
        retstring += "y_pos:       %d\n" % self.y_pos
        retstring += "total_force: %d\n" % self.total_force
        retstring += "area:        %d\n" % self.area
        retstring += "orientation:  %d\n" % self.orientation
        retstring += "major:        %d\n" % self.major_axis
        retstring += "minor:        %d\n" % self.minor_axis
        return retstring

class SenselDevice():

    def __init__(self):
        pass

    def _openAndProbePort(self, port_name):
        global sensel_serial

        logging.info("Opening port " + str(port_name))
        try:
            sensel_serial.port=port_name
            sensel_serial.open()
            sensel_serial.flushInput()
            resp = self.readReg(SENSEL_REG_MAGIC, 6)
        except SenselRegisterReadError:
            logging.warning("Failed to read magic register")
            sensel_serial.close()
            return False
        except Exception:
            e = sys.exc_info()[1]
            print(str(e))
            logging.warning("Unable to open " + str(port_name))
            return False

        if(resp == SENSEL_MAGIC):
            logging.info("Found sensel sensor at " + str(port_name))
        else:
            logging.info("Probe didn't read out magic (%s)" % resp)
            sensel_serial.close()
            return False

        try:
            protocol_version = _convertBufToVal(self.readReg(SENSEL_REG_FW_VERSION_PROTOCOL, 1))
        except SenselRegisterReadError:
            logging.warning("Failed to read protocol register")
            sensel_serial.close()
            return False

        if(protocol_version == SENSEL_REG_MAP_PROTOCOL_VERSION):
            logging.info("Compatible protocol found")
            return True
        else:
            logging.info("Incompatible protocol found")
            return False

    
    def _openSensorWin(self):
        logging.info("Opening device on WIN architecture")
        for port in serial.tools.list_ports.comports():
            if '2C2F:' in port[2]:
                if self._openAndProbePort(port[0]):
                    logging.warning("Found sensor on port %s" % port[0])
                    return True
        return False

    def _openSensorMac(self):
        logging.info("Opening device on MAC architecture")
        for port in serial.tools.list_ports.comports():
            if '2C2F:' in port[2]:
                if self._openAndProbePort(port[0]):
                    logging.warning("Found sensor on port %s" % port[0])
                    return True
        return False


    def _openSensorLinux(self):
        logging.info("Opening device on LINUX architecture")
        for port in serial.tools.list_ports.comports():
            if '2c2f:' in port[2] or '2C2F' in port[2]:
                if self._openAndProbePort(port[0]):
                    logging.warning("Found sensor on port %s" % port[0])
                    return True
        return False

    def _initLogging(self):
        FORMAT = "[%(filename)s:%(lineno)s - %(funcName)s() ] %(message)s (%(levelname)s)"
        logging.basicConfig(stream=sys.stderr, level=SENSEL_LOGGING_LEVEL, format=FORMAT)

    def _serialRead(self, num_bytes):
        resp = sensel_serial.read(num_bytes)
        if(len(resp) != num_bytes):
            raise SenselSerialReadError(len(resp), num_bytes)
        return resp

    def _serialWrite(self, data):
        resp = sensel_serial.write(data)
        if(resp != len(data)):
            raise SenselSerialWriteError(resp, len(data))
        return True;

    def _readByteValFromBuf(self, buf, idx):
        if PY3:
            return buf[idx]
        else:
            return ord(buf[idx])

    def openConnection(self, com_port=None):
        global sensel_serial
        global _serial_lock
        global sensel_lib

        self._initLogging()

        platform_name = platform.system()

        logging.info("Initializing Sensel on " + platform_name + " platform")

        sensel_serial = serial.Serial(
            baudrate=SENSEL_BAUD,\
                parity=serial.PARITY_NONE,\
                stopbits=serial.STOPBITS_ONE,\
                bytesize=serial.EIGHTBITS,\
                timeout=SENSEL_TIMEOUT)

        _serial_lock = threading.RLock()

        if(com_port != None): 
            resp = self._openAndProbePort(com_port)
        else: #Auto-detect sensor
            if platform_name == "Windows":
                sensel_lib = windll.LoadLibrary("SenselLib.dll")
                resp = self._openSensorWin()
            elif platform_name == "Darwin":
                sensel_lib = cdll.LoadLibrary("./libSensel.dylib")
                resp = self._openSensorMac()
            else:
                sensel_lib = cdll.LoadLibrary("./libSensel.so")
                resp = self._openSensorLinux()

        if resp == False:
            logging.error("Failed to open Sensel sensor!")

        return resp

    def getDeviceInfo(self):
        return SenselDeviceInfo(self.readReg(SENSEL_REG_FW_PROTOCOL_VERSION, SENSEL_DEVICE_INFO_SIZE))

    def getSensorActiveAreaDimensionsUM(self):
        width =  _convertBufToVal(self.readReg(SENSEL_REG_SENSOR_ACTIVE_AREA_WIDTH_UM, 4))
        height = _convertBufToVal(self.readReg(SENSEL_REG_SENSOR_ACTIVE_AREA_HEIGHT_UM,4))
        return (width, height)

    def getMaxForce(self):
        return _convertBufToVal(self.readReg(SENSEL_REG_PRESSURE_MAP_MAX_VALUE, 2))

    def getMaxContacts(self):
        return _convertBufToVal(self.readReg(SENSEL_REG_CONTACTS_MAX_COUNT, 1))

    def getDecompressedCols(self):
        global decompressed_cols
        return decompressed_cols

    def getDecompressedRows(self):
        global decompressed_rows
        return decompressed_rows

    def getFrameRate(self):
        return _convertBufToVal(self.readReg(SENSEL_REG_SCAN_FRAME_RATE, 1))

    def getSerialNumber(self):
        serial_num_str = self.readRegVSP(SENSEL_REG_DEVICE_SERIAL_NUMBER)
        if PY3:
            serial_num_list = [ x for x in serial_num_str ]
        else:
            serial_num_list = [ ord(x) for x in serial_num_str ]
        serial_num_list.reverse()
        return serial_num_list

    def getBatteryVoltagemV(self):
        return _convertBufToVal(self.readReg(SENSEL_REG_BATTERY_VOLTAGE_MV, 2)) 

    def setFrameContentControl(self, content):
        global forces
        global labels
        global decompressed_cols
        global decompressed_rows
        global sensel_lib
        if(content & SENSEL_FRAME_PRESSURE_FLAG):
            resp = self.readRegVSP(SENSEL_REG_COMPRESSION_METADATA)
            if(len(resp) == 6):
                metadata = (c_ubyte * 6)()
                for i in range(len(resp)):
                    metadata[i] = c_ubyte(ord(resp[i]));
                sensel_lib.senselDecompressInit(metadata, c_int(len(resp)))
                decompressed_cols = sensel_lib.senselDecompressGetCols()
                decompressed_rows = sensel_lib.senselDecompressGetRows()
                forces = cast((c_float * decompressed_cols*decompressed_rows)(), POINTER(c_float))
                labels = cast((c_ubyte * decompressed_cols*decompressed_rows)(), POINTER(c_ubyte))

        return self.writeReg(SENSEL_REG_SCAN_CONTENT_CONTROL, 1, bytearray([content]))

    def setLEDBrightness(self, idx, brightness):
        if idx < 16:
           self.writeReg(SENSEL_REG_LED_BRIGHTNESS + idx, 1, bytearray([brightness]))

    def setLEDBrightnessArr(self, brightness_levels):
        if len(brightness_levels) > 16:
            logging.error("You cannot set %d brightness levels (16 max)" % brightness_levels)
            return False
        return self.writeReg(SENSEL_REG_LED_BRIGHTNESS, len(brightness_levels), bytearray(brightness_levels))

    def resetSoft(self):
        return self.writeReg(SENSEL_REG_SOFT_RESET, 1, bytearray([1]))

    def _populateDimensions(self):
        global sensel_shift_dims
        global sensel_shift_force
        global sensel_shift_area
        global sensel_shift_angle
        sensel_shift_dims = math.pow(2,_convertBufToVal(self.readReg(SENSEL_REG_UNIT_SHIFT_DIMS, 1)))
        sensel_shift_force = math.pow(2,_convertBufToVal(self.readReg(SENSEL_REG_UNIT_SHIFT_FORCE, 1)))
        sensel_shift_area = math.pow(2,_convertBufToVal(self.readReg(SENSEL_REG_UNIT_SHIFT_AREA, 1)))
        sensel_shift_angle = math.pow(2,_convertBufToVal(self.readReg(SENSEL_REG_UNIT_SHIFT_ANGLE, 1)))

    def startScanning(self):
        self._populateDimensions()

        return self.writeReg(SENSEL_REG_SCAN_ENABLED, 1, bytearray([0x01]))

    def stopScanning(self):
        return self.writeReg(SENSEL_REG_SCAN_ENABLED, 1, bytearray([0x00]))

    #The user doesn't need to know that we're sending a write request
    def readFrame(self):
        global _serial_lock

        _serial_lock.acquire()
        self._sendFrameReadReq()
        frame_data = self._readFrameData()
        _serial_lock.release()
        return self._parseFrameData(frame_data)

    def _sendFrameReadReq(self):
        #Send first read request
        cmd = pack('BBB', SENSEL_READ_HEADER, SENSEL_REG_SCAN_READ_FRAME, 0)
        return self._serialWrite(cmd)

    #Reads frame data, and verifies checksum
    def _readFrameData(self):

        ack = _convertBufToVal(self._serialRead(1))
        reg_resp = _convertBufToVal(self._serialRead(1))
        header = _convertBufToVal(self._serialRead(1))

        if(ack != SENSEL_PT_RVS_ACK):
            logging.error("Failed to recieve ACK on force frame finish! (received %d)\n" % ack)
            raise SenselSerialReadError(0, 1)

        frame_size = _convertBufToVal(self._serialRead(2))
        logging.info("reading frame of %d bytes" % frame_size)

        frame_data = self._serialRead(frame_size)
        resp_checksum = _convertBufToVal(self._serialRead(1))

        if not self._verifyChecksum(frame_data, resp_checksum):
            logging.error("Response checksum didn't match checksum (resp_checksum=%d, checksum=%d)" % 
                          (resp_checksum, checksum))
            raise SenselSerialReadError(1, 1)

        return frame_data


    def _parseFrameData(self, frame_data):
        global forces
        global labels
        global decompressed_cols
        global decompressed_rows
        global sensel_lib
        if len(frame_data) < 2:
            logging.error("Frame data size is less than 2!")
            raise SenselSerialReadError(2, 0)

        #Pull off frame header info
        content_bit_mask = _convertBufToVal(frame_data[0])
        lost_frame_count = _convertBufToVal(frame_data[1])
        frame_data = frame_data[6:]

        logging.info("content mask: %d, lost frames: %d" % (content_bit_mask, lost_frame_count))

        if content_bit_mask & SENSEL_FRAME_CONTACTS_FLAG:
            logging.info("Received contacts")
            contact_mask = _convertBufToVal(frame_data[0])
            num_contacts = _convertBufToVal(frame_data[1])
            frame_data = frame_data[2:]

            contacts = []

            for i in range(num_contacts):
                contacts.append(SenselContact(frame_data[:SenselContact.data_size]))
                frame_data = frame_data[SenselContact.data_size:]
        else:
            contacts = None


        if content_bit_mask & SENSEL_FRAME_PRESSURE_FLAG:
            frame_data_c = (c_ubyte * (len(frame_data)))()
            frame_str = "";
            for i in range(len(frame_data)):
                frame_data_c[i] = c_ubyte(ord(frame_data[i]));
            sensel_lib.senselDecompressFrame(frame_data_c, c_int(len(frame_data)), forces, labels)
            return (lost_frame_count, forces, labels, contacts)
        else:
            return (lost_frame_count, None, None, contacts)


    def _verifyChecksum(self, data, checksum):
        curr_sum = 0
        for val in data:
            if PY3:
                curr_sum += val
            else:
                curr_sum += ord(val)
        curr_sum = (curr_sum & 0xFF)
        if(checksum != curr_sum):
            logging.error("Checksum failed! (%d != %d)" % (checksum, curr_sum))
            return False
        else:
            logging.debug("Checksum passed! (%d == %d)" % (checksum, curr_sum))
        return True

    def readReg(self, reg, size):
        global _serial_lock

        cmd = pack('BBB', SENSEL_READ_HEADER, reg, size)
        _serial_lock.acquire()
        try:
            self._serialWrite(cmd)
            ack = _convertBufToVal(self._serialRead(1))
            reg_resp = _convertBufToVal(self._serialRead(1))
            resp_size = _convertBufToVal(self._serialRead(2))

            if(ack != SENSEL_PT_READ_ACK):
                logging.error("Failed to receive ACK from reg read (received %d)" % ack)
                raise SenselSerialReadError(1, 0)

            if(resp_size != size):
                logging.error("Response size didn't match request size (resp_size=%d, req_size=%d)" % (resp_size, size))
                raise SenselSerialReadError(resp_size, size)

            resp = self._serialRead(size)
            resp_checksum = _convertBufToVal(self._serialRead(1))
        except (SenselSerialWriteError, SenselSerialReadError):
            raise SenselRegisterReadError(reg, size)
        _serial_lock.release()

        if not self._verifyChecksum(resp, resp_checksum):
            logging.error("Response checksum didn't match checksum (resp_checksum=%d, checksum=%d)" % (resp_checksum, checksum))
            raise SenselSerialReadError(1, 1)

        return resp

    def readRegVSP(self, reg):
        global _serial_lock

        cmd = pack('BBB', SENSEL_READ_HEADER, reg, 0) # 0 for RVS
        _serial_lock.acquire()
        try:
            self._serialWrite(cmd)
            ack = _convertBufToVal(self._serialRead(1))
            reg_resp = _convertBufToVal(self._serialRead(1))
            header = _convertBufToVal(self._serialRead(1))
            if(ack != SENSEL_PT_RVS_ACK):
                logging.error("Failed to receive ACK from vsp read (received %d)" % ack)
                raise SenselSerialReadError
            vsp_size = _convertBufToVal(self._serialRead(2))
            vsp_size = 0x7FFF & vsp_size;
            resp = self._serialRead(vsp_size)
            resp_checksum = _convertBufToVal(self._serialRead(1))
        except SenselSerialReadError:
            raise SenselRegisterReadVSPError(reg, vsp_size)
        _serial_lock.release()

        if not self._verifyChecksum(resp, resp_checksum):
            raise SenselRegisterReadVSPError(reg, vsp_size)

        return resp

    def readErrorCode(self):
        return _convertBufToVal(self.readReg(0xEC, 1))

    def printErrorCode(self, error_code):
        if error_code == 0:
            print("Success!")
        elif error_code == 1:
            print("ERROR: Invalid write address")
        elif error_code == 2:
            print("ERROR: Invalid write value")
        elif error_code == 3:
            print("ERROR: Invalid register write permissions")


    def writeReg(self, reg, size, data):
        global _serial_lock
        cmd = pack('BBB', SENSEL_WRITE_HEADER, reg, size)

        checksum = 0
        for d in data:
            checksum += d
        checksum &= 0xFF

        _serial_lock.acquire()
        try:
            self._serialWrite(cmd)
            self._serialWrite(data)
            self._serialWrite(bytearray([checksum]))
            resp = _convertBufToVal(self._serialRead(1)) #Read ACK
            reg_resp = _convertBufToVal(self._serialRead(1))
        except (SenselSerialWriteError, SenselSerialReadError):
            raise SenselRegisterWriteError(reg, size, data, False, 0)

        if (resp != SENSEL_PT_WRITE_ACK):
            raise SenselRegisterWriteError(reg, size, data, True, resp)

        ec = self.readErrorCode()
        _serial_lock.release() #We should hold the lock through the EC read
        return ec

    def closeConnection(self):
        self.setLEDBrightnessArr([0] * 16)
        sensel_serial.close()


def _convertBufToVal(buf):
    if PY3:
        if type(buf) is int:
            return buf
    else:
        buf = ["{:02d}".format(ord(c)) for c in buf]
    final_val = 0
    for i in range(len(buf)):
        final_val |= (int(buf[i]) << (i * 8))
    return final_val

class SenselError(Exception):
    """Base class for exceptions in this module"""
    pass

class SenselSerialReadError(SenselError):
    """Exception raised when a serial read fails"""
    def __init__(self, num_bytes_read, num_bytes_requested):
        self.num_bytes_read = num_bytes_read
        self.num_bytes_requested = num_bytes_requested
        logging.error("Requested %d bytes, received %d bytes" % (num_bytes_requested, num_bytes_read))

class SenselFrameDecompressionError(SenselError):
    """Exception raised when a serial read fails"""
    def __init__(self, num_bytes_decompressed, num_bytes_expected):
        logging.error("Only decompressed %d of %d bytes" % 
                      (num_bytes_decompressed, num_bytes_expected))

class SenselSerialWriteError(SenselError):
    """Exception raised when a serial read fails"""
    def __init__(self, num_bytes_written, num_bytes_requested):
        self.num_bytes_written = num_bytes_written
        self.num_bytes_requested = num_bytes_requested
        logging.error("Requested %d bytes, wrote %d bytes" % (num_bytes_requested, num_bytes_written))

class SenselRegisterReadError(SenselError):
    """Exception raised when a register read times out"""
    def __init__(self, reg, size):
        self.reg = reg
        self.size = size
        logging.error("Failed to read register 0x%02X (size %d)" % (reg, size))

class SenselRegisterReadVSPError(SenselError):
    """Exception raised when a variable-sized register read times out"""
    def __init__(self, reg, vsp_size):
        self.reg = reg
        self.vsp_size = vsp_size
        logging.error("Failed to read VSP register 0x%02X (vsp size %d)" % (reg, vsp_size))

class SenselRegisterWriteError(SenselError):
    """Exception raised when a register write times out or a non-ACK value is read"""
    def __init__(self, reg, size, data, ack_received, response):
        self.reg = reg
        self.size = size
        self.data = data
        self.ack_received = ack_received
        self.response = response
        logging.error("Failed to write register 0x%02X (size=%d, ack_received=%d, response=%d)" % (reg, size, ack_received, response))

