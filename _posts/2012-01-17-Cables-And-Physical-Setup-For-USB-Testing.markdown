---
layout: post
title: Cables and physical setup for USB testing
public: true
---

Purpose
=======
To document how we assembled the cables used in [Enabling the Drone USB Port][0].

Procedure
=========
Initially we bought an AR.Drone USB cable from [morfars.dk][1], alternatively one could have obtained a 7-pin Molex connector and some USB chord and constructed a cable from this 
[pinout][2]. After receiving the cable we realized that a female-to-female adapter would be needed if we were going to connect devices to the drone.   
Instead of ordering an adapter, we decided to cut two regular usb-extension cables in halves and resolder the two female ends. After a few attempts(thank you [Peter][3]) we succeded in making two working cables,
one female-female and one male-male. Cables were tested by measuring voltage levels after being plugged into the drone.   
Though our newly created cables actually worked, we decided to simplify the setup a bit by cutting off the male connector of the AR.Drone
USB cable and attaching a female connector scavenged from an old motherboard.

Results
=======
<a href=" https://projects.ardrone.org/attachments/download/170 "AR.Drone USB cable"><img src="https://projects.ardrone.org/attachments/download/170 "AR.Drone USB cable"" width="150" height="150"></a>
<a href="/Navigation-for-Robots-with-WIFI-and-CV/images/femaletofemale.JPG"><img src="/Navigation-for-Robots-with-WIFI-and-CV/images/femaletofemale.JPG" width="150" height="150"></a>
<a href="/Navigation-for-Robots-with-WIFI-and-CV/images/droneconnector.JPG"><img src="/Navigation-for-Robots-with-WIFI-and-CV/images/droneconnector.JPG" width="150" height="150"></a>
<a href="/Navigation-for-Robots-with-WIFI-and-CV/images/droneconnector-close.JPG"><img src="/Navigation-for-Robots-with-WIFI-and-CV/images/droneconnector-close.JPG" width="150" height="150"></a>
<a href="/Navigation-for-Robots-with-WIFI-and-CV/images/cabletest.JPG"><img src="/Navigation-for-Robots-with-WIFI-and-CV/images/cabletest.JPG" width="150" height="150"></a>
<a href="/Navigation-for-Robots-with-WIFI-and-CV/images/usbsetup.JPG"><img src="/Navigation-for-Robots-with-WIFI-and-CV/images/usbsetup.JPG" width="150" height="150"></a>   

The cables above have been used to succesfully access a USB stick from the AR.Drone OTG USB port. For now the cables are suitable for testing, but when time comes for flying and reducing weight,
the cables will be further shortened/stripped to ensure drone maneuverability.

<!-- references -->
[0]: http://127.0.0.1:4000/Navigation-for-Robots-with-WIFI-and-CV/blog/2012/01/12/Enabling-The-Drone-USB-Port/ "Enabling the drone USB port"
[1]: http://www.morfars.dk/rc/katalog-reservedele-c-52_308.html?preload=PF070021 "Morfars.dk, AR.Drone USB cable"
[2]: https://projects.ardrone.org/attachments/167/ARDrone-USB-Cable.png "pinout"
[3]: http://blog.ptx.dk/ "ptx's blog"
[4]: https://projects.ardrone.org/attachments/download/170 "AR.Drone USB cable"