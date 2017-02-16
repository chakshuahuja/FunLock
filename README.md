#Sensel Python API

This API allows users to communicate with a Sensel device through Python. This API should be cross-platform, and work across Windows, Mac, and Linux. If you find any incompatibilities, please submit a bug report through Github.

##Setup
In order to use this API, please install Python (version 2.7 or later) on your machine. You must also install pySerial to allow communication with the sensor. 

Clone this Github project, and drop sensel.py into a new project directory.

##Usage
The Sensel Python API provides an object-oriented approach to interacting with a Sensel device. Here's a high-level view of how to use this API:

First, we need to import Sensel:

```python
import sensel
```

Next, we need to properly setup the sensor. We first instantiate an instance of a SenselDevice. Then we call `openConnection()`, which returns true if we successfully connect to a Sensel device. If we connect to a sensor, we need to tell the sensor to send us contacts. We use the method `setFrameContentControl()`, and pass in a frame content constant: `sensel.SENSEL_FRAME_CONTACTS_FLAG` `sensel.SENSEL_FRAME_PRESSURE_FLAG` and/or `sensel.SENSEL_FRAME_LABELS_FLAG`. To recieve multipe frame content, perform a bitwise or '|' of the frame content flags. After this, we tell the sensor to start scanning by calling `startScanning()`:

```python
sensel_device = sensel.SenselDevice()

if not sensel_device.openConnection():
    print("Unable to open Sensel sensor!")
    exit()

#Enable contact sending
sensel_device.setFrameContentControl(sensel.SENSEL_FRAME_CONTACTS_FLAG)

#Enable scanning
sensel_device.startScanning()
```

Next, you can read out a frame content in your program's main event loop with `readFrame`. This returns an array of contacts.

```python
while looping:
    frame = sensel_device.readFrame();
    if frame:
        (lost_frame_count, forces, labels, contacts) = frame
        #USE FRAME DATA HERE
```

Before the applciation exits, make sure to cleanly close the connection to the sensor by calling `stopScanning()` and `closeConnection()`

```python
print("Done looping, exiting...")

sensel_device.stopScanning();
sensel_device.closeConnection();
```

##Examples

There is an example in this repository that you can use as a starting point for your project:

####sensel_example_read_contacts.py
This project opens up a Sensel device, reads out contact data, and prints it to the screen.
