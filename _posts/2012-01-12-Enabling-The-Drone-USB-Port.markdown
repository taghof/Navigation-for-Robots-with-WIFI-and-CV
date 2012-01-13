---
layout: post
title: Enabling the Drone USB Port
---


Purpose
=======
To determine whether attaching extra sensors to the AR.Drone is
possible and to make a proof of concept by attaching and mounting a
USB memory stick.

Procedure
=========
To enable the On-The-Go USB port several steps must be taken: Editing the port
driver to enable host mode, compiling the driver and other necessary
kernel modules with a cross compiler toolchain, uploading the compiled
modules to the drone and inserting the modules in the kernel and
lastly changing the state of an I/O pin with the drone gpio tool. The following
steps assume you are using a linux build environment.
								
1.	To begin editing the port driver one must first obtain the
      	source code, luckily the custom Parrot kernel source(including
       	drivers) is freely available from the [AR.Drone website][1]. Also available is the kernel config file, so we
       	are able to build modules for the exact kernel running on the drone.
	
	+	Download and unpack the kernel source and 
		kernel.config. Rename kernel.config to .config and place it in
		the kernel source root.
	+	Setup a cross compilation environment by following the instructions
       		from [www.nas-central.com][2], instructions include a setup script which automatically fetches the [codesourcery toolchain][3].

2.	Edit the file "drivers/parrot/usb/dwc\_otg/dwc\_otg\_driver.c",
	instructions are from [the E/S and I blog][4].
	In short, around line 224 comment out: 

		params->ctrl_mode = info->ctrl_mode;
		params->vbus_detection = info->vbus_detection;

	<br />and around line 135 set `.overcurrent_pin = -1`.</li>

3.	Select the kernel modules you want to compile(including the one you edited) by going to the kernel tree root and running:

		make ARCH=arm CROSS_COMPILE=arm-none-linux-gnueabi- menuconfig

	<br />Remember to select as modules(M, not *).   
	+	To enable the usb port select:   
		"System Type -> Parrot Drivers -> PARROT6 USB driver (Synopsys)".   

	+	To enable the FAT32 file system select:   
		"File systems -> DOS/FAT/NT Filesystems -> VFAT (Windows-95) fs support"   
		"File systems -> Native language support"   
		"File systems -> Native language support -> Codepage 437 (United States, Canada)"   
		"File systems -> Native language support -> NLS ISO 8859-1  (Latin 1..."   
		"File systems -> Native language support -> NLS UTF-8"   

	+	For a USB stick to be recognized as a SCSI disk, we must add SCSI support by selecting:   
		"Device Drivers -> SCSI device support -> SCSI disk support"   

	Alternatively you could use [our kernel config][5] and spare yourself the trouble, anyway the selected modules can now be compiled by running:
   
		make ARCH=arm CROSS_COMPILE=arm-none-linux-gnueabi- modules

	<br />This should, among other things, generate the following modules:

		drivers/block/nbd.ko
		drivers/parrot/usb/dwc_otg/dwc_otg.ko
		drivers/scsi/scsi_wait_scan.ko
		drivers/scsi/sd_mod.ko
		fs/fat/fat.ko
		fs/nls/nls_base.ko
		fs/nls/nls_cp437.ko
		fs/nls/nls_iso8859-1.ko
		fs/nls/nls_utf8.ko
		fs/vfat/vfat.ko
	<br />   

4.	Transfer these modules to the drone via FTP and before inserting the modules, login to the drone via telnet and run the following commands to activate the USB port in the 		drone hardware:
   
		# gpio 127 -d ho 1
		# gpio 127 -d i
   

	<br />Then insert the modules with `insmod <module file>`. Consider a shell script for automating the on-drone proces, we made a [script][6] that copies all transferred .ko 		files to a custom_modules directory, sets the I/O pin and inserts the needed modules. For further ease of use this script could be called from the drone startup script.

Results
=======

After following the procedure above we were able to power the USB port, compile and insert the necessary kernel modules, recognize our USB stick 
as a SCSI disk, mount the stick and copy files from the stick to the drone internal memory and back. Below are screen caps of the on-drone-process and results.   

<a href="/Navigation-for-Robots-with-WIFI-and-CV/images/load.png"><img src="/Navigation-for-Robots-with-WIFI-and-CV/images/load.png" width="150" height="150"></a>
<a href="/Navigation-for-Robots-with-WIFI-and-CV/images/fdisk-df.png"><img src="/Navigation-for-Robots-with-WIFI-and-CV/images/fdisk-df.png" width="150" height="150"></a>
<a href="/Navigation-for-Robots-with-WIFI-and-CV/images/copying.png"><img src="/Navigation-for-Robots-with-WIFI-and-CV/images/copying.png" width="150" height="150"></a>

References
==========
Much of the tweaking described above was developed by the users ["Scorpion2k"][http://embedded-software.blogspot.com]
 and "MAPGPS" of [www.ardrone-flyers.com][http://www.ardrone-flyers.com]. Below is listed the actual threads, blogpost and wikis we used above.
[NAS central, cross compilations setup][2]   
[E/S and I, AR.Drone USB][4]   
[AR.Drone Flyers, USB disc thread][7]   
Code resources:
[Kernel source and kernel config][1]
[Our custom kernel config][5]
[Our load script][6]

<!-- references -->
[2]: http://www.nas-central.org/wiki/Setting_up_the_codesourcery_toolchain_for_X86_to_ARM9_cross_compiling "cross compilation setup"
[3]: http://www.mentor.com/embedded-software/sourcery-tools/sourcery-codebench/editions/lite-edition/ "Codesourcery(Mentor) lite edition"
[4]: http://embedded-software.blogspot.com/2010/12/ar-drone-usb.html "E/S and I, AR.Drone USB"
[7]: http://www.ardrone-flyers.com/forum/viewtopic.php?t=829 "AR.Drone Flyers, USB disc thread"

<!-- downloads -->
[1]: https://projects.ardrone.org/documents/show/19 "Kernel Source"
[5]: https://raw.github.com/taghof/Navigation-for-Robots-with-WIFI-and-CV/gh-pages/downloads/custom-kernel.config "Our kernel config"
[6]: https://raw.github.com/taghof/Navigation-for-Robots-with-WIFI-and-CV/gh-pages/downloads/load.sh "Our load script"
