---
layout: post
title: Attaching a USB WIFI adapter to the AR.Drone
public: false
---

Purpose
=======
To allow a robot like the AR.Drone to be more autonomous we find that it is important to be able to attach extra sensors.
The purpose of the work described in this post was to document how one attaches a USB WIFI adapter. The device was attached 
via the drone OTG USB port which we [activated in a previous post][1]. A secondary purpose was to gain more experience with linux drivers and
[the cross compiling process][2].

Procedure
=========
Before getting to work we needed a device with the required features, for our purpose of gathering information about the WIFI access points in range,
this meant a USB WIFI adapter capable of entering monitor mode and preferrably accompanied by a driver for linux kernel version 2.6.27. After some research on the web(mostly [here][8] and [here][9]), we found that a device based on a Ra-Link chipset would probably work and after a little more research we finally opted for a [D-Link DWL-G122][3].   
After aquiring the device we must go through the following steps: examining the device to retrieve vendor and device ids, finding a suitable driver, cross compiling the driver, inserting the compiled driver module and testing monitor mode with tcpdump(cross compiled for the occasion).

1.	To examine the device we used `sudo lsusb -v`, lsusb is not available(so far)
 	on the drone so we used a Ubuntu 11.10 host. After finding the entry describing our device, we read our vendor:device id to be 0x07D1:0x3C0F. Next we attached the device to 		the drone and saw that it was picked up on insertion, but of course no driver was loaded.

2.	In hindsight finding the correct driver was the most troublesome step, this was mostly because we didn't search for the vendor:device id but instead for the more generic 		"RT2870". Thus after much searching, trying different drivers and modyfying before mentioned drivers(some of which actually loaded), we finally found the right driver, 	[RT3370][01], after reading this [thread on Ubuntu forums][4]. 

3.	The instructions for compiling the driver can be found in the README\_STA\_usb. Basically we needed to edit the path to the linux source and modules and add a CROSS_COMPILE 		path in the Makefile(of course these instructions will only fit this specific driver), see below:

		ifeq ($(PLATFORM),PC)
		# Linux 2.6
		LINUX_SRC = /home/taghof/speciale/embedded_linux/linux-2.6.27/
		# Linux 2.4 Change to your local setting
		#LINUX_SRC = /usr/src/linux-2.4
		LINUX_SRC_MODULE = /home/taghof/speciale/embedded_linux/linux-2.6.27/drivers/net/wireless/
		CROSS_COMPILE = arm-none-linux-gnueabi-
		endif
 	
	<br />Next enter the cross compiling environment and run `make`
		
		$ sudo codesourcery-arm-2009q3.sh
		$ make
	<br />
4.	The commands above produces rt3370sta.ko, FTP this to the drone, load the rt3370sta module and then load dwc_otg.ko.

		$ insmod rt3370sta.ko
		$ insmod dwc_otg.ko
	<br />Next one would probably want to add the insmod commands to [the load script][02] mentioned in a previous [post][1].		

5.	To test the driver we ran the commands listed below on the drone. The commands show us the new wireless interface ra0, brings it up and then gives us a list of in-range 		APs, lastly we see monitor mode working with the aid of tcpdump.
		
		$ ifconfig -a
		$ ifconfig ra0 up
		$ iwlist ra0 scan
		$ iwconfig ra0 mode monitor
		$ tcpdump -i ra0
	<br />Like our advanced test program in [the cross compiling post][2] tcpdump depends on libpcap and it is compiled in a similar way, a guide that gets around the 		enevitable quirks can be found [here][7].

Results
=======
After finding the correct driver, compiling and testing was straight forward. The driver works as expected and we have gained the ability to scan for wireless APs and to monitor all incoming wireless packets. We have also become painfully aware of the importance of finding the right driver version, specifically if the vendor:device id is not found in the drivers list of supported devices, it probably is not the correct driver... and further hacking and fiddling with the driver is likely futile. It would seem that other drivers might support our device, for instance the RT5370 USB which can be downloaded from the [Ra-Link support site][5]. Attempts to compile rt2800usb(available in the kernel tree from around 2.6.31) for 2.6.27 with [compat wireless][6] was unsuccesfull.


References
==========

Posts, guides and threads used in the above procedures:   
["Enabling the drone USB port"][1]   
["Compiling code for the AR.Drone"][2]   
["D-Link DWL-G122"][3]   
["Ubuntu forums thread"][4]   
["Ra-Link driver download"][5]   
["Compat wireless download"][6]   
["Cross compiling tcpdump"][7]   
["Tool for linking devices to chipsets and drivers"][8]   
["List of usable WIFI adapters"][9]   

Code resources:   
[RT3370STA driver][01]   
[Our load script][02]   

<!-- references -->
[1]: http://taghof.github.com/Navigation-for-Robots-with-WIFI-and-CV/blog/2012/01/12/Enabling-The-Drone-USB-Port/ "Enabling the drone USB port"
[2]: http://taghof.github.com/Navigation-for-Robots-with-WIFI-and-CV/blog/2012/01/13/Compiling-Code-For-The-ARDrone/ "Compiling code for the AR.Drone"
[3]: http://www.dlink.dk/cs/Satellite?c=Product_C&childpagename=DLinkEurope-DK%2FDLProductCarouselMultiple&cid=1197319529299&p=1197357728135&packedargs=ParentPageID%3D1197337625277%26ProductParentID%3D1197318706946%26TopLevelPageProduct%3DBusiness%26category%3DQuickProductFinder%26locale%3D1195806935729%26term%3DDWL-G122&pagename=DLinkEurope-DK%2FDLWrapper "D-Link DWL-G122"
[4]: http://ubuntuforums.org/showthread.php?t=1675764 "Ubuntu forums thread"
[5]: http://www.ralinktech.com/en/04_support/support.php?sn=501 "Ra-Link driver download"
[6]: http://linuxwireless.org/en/users/Download/stable#Stable_compat-wireless_releases "Compat wireless download"
[7]: http://owen-hsu.blogspot.com/2011/03/embedded-porting-tcpdump-to-arm-emedded.html "Cross compiling tcpdump"
[8]: http://linux-wless.passys.nl/ "Tool for linking devices to chipsets and drivers"
[9]: http://airodump.net/wifi-hardware-monitor-applications/ "List of usable WIFI adapters"

<!-- downloads -->
[01]: /Navigation-for-Robots-with-WIFI-and-CV/downloads/2010_0831_RT3070_Linux_STA_v2.4.0.1_DPO.bz2 "RT3370STA driver"
[02]: /Navigation-for-Robots-with-WIFI-and-CV/downloads/load.sh "Our load script"

