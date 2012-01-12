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

0. To begin editing the port driver one must first obtain the source
code, luckily Parrot makes their custom kernel source(including drivers) 
freely available [here](https://projects.ardrone.org/documents/show/19
"Kernel Source"). Also available is the kernel config and so we are
able to build modules for the kernel running on the drone. 
0.1   So download and unpack the kernel source, rename kernel.config to
.config and place it in the kernel source root.
0.2   Setup a cross compilation environment by following the
instructions
[here](http://www.nas-central.org/wiki/Setting_up_the_codesourcery_toolchain_for_X86_to_ARM9_cross_compiling
"cross compilation setup").

1.1 Edit the file "drivers/parrot/usb/dwc_otg/dwc_otg_driver.c",
instructions are
[here](http://embedded-software.blogspot.com/2010/12/ar-drone-usb.html),
in short, around line 224 comment out: 

   params->ctrl_mode = info->ctrl_mode; 
   params->vbus_detection = info->vbus_detection;

and around lin 135 set `.overcurrent_pin = -1, /* default */`

1.2 Select the kernel modules you want to compile(including the one
you edited) by going to the kernel tree root and running:

   make ARCH=arm CROSS_COMPILE=arm-none-linux-gnueabi- menuconfig 	      

Remember to select as modules(M, not *). To enable the usb port go to
"System Type -> Parrot Drivers" and select "PARROT6 USB driver
(Synopsys)". To enable the FAT32 file system select "File systems ->
DOS/FAT/NT Filesystems -> VFAT (Windows-95) fs support", "File systems
-> Native language support", "File systems -> Native language support
-> Codepage 437 (United States, Canada)", "File systems -> Native
language support -> NLS ISO 8859-1  (Latin 1; Western European
Languages), "File systems -> Native language support -> NLS
UTF-8. Furthermore, for a USB stick to be recognized as a SCSI disk, we
must add SCSI support by selecting "Device Drivers -> SCSI device
support -> SCSI disk support.
Now the selected modules can be compiled by running:
    
    make ARCH=arm CROSS_COMPILE=arm-none-linux-gnueabi- modules
    
this should, among other things, generate the following modules:
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

Transfer these modules to the drone via FTP and before inserting the
modules run the following commands on the drone to activate the USB port in the
drone hardware:

      # gpio 127 -d ho 1
      # gpio 127 -d i

Then insert the modules with `insmod <module file>`. Consider a shell
script for automating the on-drone proces.