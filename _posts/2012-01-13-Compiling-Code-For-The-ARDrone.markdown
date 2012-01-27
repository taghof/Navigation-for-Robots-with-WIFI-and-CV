---
layout: post
title: Compiling code for the AR.Drone
public: true
---

Purpose
=======
To document the build process, when cross-compiling code to be executed on an AR.Drone. Results are considered satisfactory if we can
compile a simple "hello world" program and execute the program on the drone, further we should be able to compile third-party libraries and likewise test them with simple programs on the drone.

Procedure - simple
==================
The procedure for making and testing drone-executable code is rather simple: install a cross-compilation toolchain, make a "hello world" c program and cross compile it, transfer the program to the drone and execute it like any other program. The following steps assume you are using a linux distro.

1.	To install the codesourcery toolchain follow the instruction on the [Nas-central website][1] or just download and run this [script][01] (which originates from the Nat-center 		site).   
	Run the following command to enter your cross compilation environment:
		
		$ codesourcery-arm-2009q3.sh
	<br />
2.	Construct a simple C program, for instance:

		#include <stdio.h>

		int main ()
		{
		  printf ("Hello World!\n");
		}

	<br />Compile it for the AR.Drones ARM9 processor with the following command:

		$ arm-none-linux-gnueabi-gcc hello.c -o hello_arm
	<br />

3.	Connect to the drone FTP server(assuming that you are already connected to the drone wifi) and put hello_arm on the drone. The server will place the file in
	/data/video/. Run the program like any other:

		$ ./hello_arm 
		Hello World!

	<br />

Procedure - advanced
====================
The advanced procedure deals with cross compiling a third party library, installing it to be used with the cross compiling toolchain and compiling a program using the library.
For the example we will use libpcap as the third party library and compile a simple packet sniffer.

1.	Fetch the libpcap source [here][02] and unpack it.

2.	Start up the cross compile environment, build an ARM version of libpcap and install it with the following commands (remember the prefix part). To get the command right we 		used [the ARM cross-compiling howto][2] and [the www.secdev.org guide][3] for inspiration.
		
		$ codesourcery-arm-2009q3.sh
		$ CC=arm-none-linux-gnueabi-gcc ./configure --prefix=/usr/local/codesourcery/arm-2009q3/arm-none-linux-gnueabi/ --host=arm-none-linux-gnu \ 
		  --target=arm-none-linux-gnu --with-pcap=linux
		$ make
		$ sudo codesourcery-arm-2009q3.sh
		$ sudo make install
	<br />
	Note that(on our system at least) make install must be called with root privileges, therefore the codesourcery script must also be started again with sudo.

3.	Now that the library has been built and installed all we need is to compile our sniffer program which uses the library.

		$ arm-none-linux-gnueabi-gcc *.c -lpcap -static -o sniffer   
	<br />
	The output, sniffer, can be transferred to and executed on the drone.

Results
=======
We were able to cross compile both the simple program, the library and the more advanced program utilizing the library. By doing a static compile of the advanced program, we don't have to transfer the library to the drone. We were also able to execute both programs on the drone.

References
==========
Cross compilation guides:   
[Nas Central, cross compile setup][1]   
[The ARM cross-compiling howto][2]   
[The www.secdev.org guide][3]   

Code resources:   
[Cross compilation setup script][01]   
[Libpcap source code][02]   


<!-- references -->
[1]: http://www.nas-central.org/wiki/Setting_up_the_codesourcery_toolchain_for_X86_to_ARM9_cross_compiling "Nas Central, cross compile setup"
[2]: http://www.ailis.de/~k/archives/19-ARM-cross-compiling-howto.html "the ARM cross-compiling howto"
[3]: http://www.secdev.org/zaurus/crosscompile.html "the www.secdev.org guide"

<!-- downloads -->
[01]: /Navigation-for-Robots-with-WIFI-and-CV/downloads/codesetup.sh "Cross compilation setup script"
[02]: http://www.tcpdump.org/release/libpcap-1.2.1.tar.gz "Libpcap source"

