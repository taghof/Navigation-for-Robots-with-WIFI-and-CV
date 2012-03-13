---
layout: post
title: Python Tool for Controlling The Drone
public: False
---

Purpose
=======
To describe the python tool we have designed as the base of our further experimentation
and to explain the archictecture of the program. The source code can be found in our repository 
and easily cloned.

Description
===========
On a higher level of abstraction our tool consist of three distict parts: Data retrieval, 
data display and drone control. For performance reasons the data retrieval is split into
separate processes. The entry point for the program is drone.py, here retrieval, display 
and control is initialised and their processes and threads started. We are also able to
start a testdevice if a real physical drone is not present.

The data retrieval processes continously receives video, wifi and nav data from the drone or from
the test device. We have implemented a base Receiver class and subclassed this base for each of the
data types received. The classes use the python multiprocess library and defines an interface for 
external use of the data received. Each class spawn a new process for the retrieval loop, the received 
data is shared via multiprocess manager objects.

We display the decoded data to the user via a pyGTK user interface. It basically consist of some radiobuttons
to select the type of data to view and some togglebuttons to add special layers on top of the data. The data 
itself is drawn to a standard pyGTK drawing area. Below the drawing area we have added buttons to control 
the recording functions of the receiver classes.
<a href="/Navigation-for-Robots-with-WIFI-and-CV/images/dronetool.png">
<img src="/Navigation-for-Robots-with-WIFI-and-CV/images/thumbs/dronetool.png" width="150" height="150">
</a><a href="/Navigation-for-Robots-with-WIFI-and-CV/images/controller.png">
<img src="/Navigation-for-Robots-with-WIFI-and-CV/images/thumbs/controller.png" width="150" height="150">
</a>

The third part of the system deals with controlling the drone. The drone is controlled by sending AT 
commands to the drone command port, we have isolated these commands in a controller interface and all commands 
to drone is sent through this interface. Like in the receiver case we have implemented a base controller class and 
from this base we subclass the actual controllers. At this point we have two controllers, one for manual control 
via an Xbox360 joypad and one for automatic control. The automatic control loop at this point is empty, but will 
see development in the near future. Our controller arrangement is easily extendable if the need for 
additional controllers arise.

Results
=======
The program has reached a development stage where it can be used to control and monitor our
drone experiments, it is not though a finished product, we expect the program to be developed further in the course 
of the project.