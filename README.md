# funLock #

A proof of concept for a keyboard which recognizes your typing pattern and autoatically logs out anyone who isn't you.
This was the winning entry in the Devweek hackathon for The Sensel Morph Authentication and Security Challenge.
Details of challenge: http://accelerate.im/challenges/105

#### P.S.: This project is just the naive POC to demostrate the idea. Not ready for production until proper neural network and proper training and testing pattern have been used. 

### Quick start ###

* Clone the repo
* Attach the sensel device
* Run python sensel_example_read_contacts.py
* Having typed enough to capture the train data, press P to flush it to FORCEMAP.data file
* Type again and now after every 3 second, data is collected and compared against training data file.

### Details
* The sensel morph captures the force you apply on every key and the coordinates you hit you press a key.
* This captured data is used to train the morph and fed as training data for it to recognize as you.
* A random person comes and starts typing and that typing test pattern is compared with that of yours.
* In case of mismatch, screen automatically logs out.
* Enjoy the next generation keyboard where you need to never lock your computer :P

### Contributors ###
* Chakshu https://github.com/chakshuahuja
* Siddhant https://github.com/siddhant3s
* You?

### License ###
* Do whatever you want. If you like the idea, or would like to develop on it, please contact us.


