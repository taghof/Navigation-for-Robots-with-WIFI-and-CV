---
layout: post
title: UDPing ATcommands from inside the drone
public: true
---


Purpose
=======
To have tysse do a blog post before the taghof:tysse blog post ratio is out of a 50:50 reach, and also to make initial investigations of the future possibility of constructing a controlprogram onboard the AR.Drone, - either instead-of or in-parallel with the current program.elf. A prerequisite of this is to be able of doing ATcommand requests onboard the drone.

Procedure
=========
It is already possible to send ATcommands from an external source. This is what is used in the controller app on the iphone. Some of the AT-commands have been mapped for the use in the [Drone SDK][6]. The SDK system is mostly used from a PC platform etc. Some of the initial testings (of the initial testings) done in this projekt was done playing around with the py-code of [venthur][1], specifically the code for the [Drone-implementation][2].   

Some contemplating was conducted, before deciding on an adequate command to execute. When not having access to all other controls, and not wanting to break or damage anything, - it seems best to refrain from doing any moving of any rotary part. - Other available commands are retrieving video or retrieving navigation data. When not wanting to do any retrieving, but just issue commands left and right without responsibility, one may restrict one-self to issuing commands to control the LED-animations on the motor-LED indicators.   

1.	A [C-program][3] or [two][4] was stolen and re-written (using [man][5]) to send off UDP-packages to the Drones command port 5556.   

	The client code is available at [udping.c][01]. udping.c is made to send one AT command and then terminate. Below is a small recap.

		#include <sys/socket>
		 ...

		#define PORT 5556
		 ...

			line = "AT*LED=5,6,1,2\r";
			inet_aton("192.168.1.1", &receiver_addr.sin_addr);
			receiver_addr.sin_port = htons( PORT );

			sendto( sock_fd, line, BUFSIZE, 0,
							(struct sockaddr*)&receiver_addr, sizeof(receiver_addr)
						);   
   
	The port number and ip addresse is assigned to a struct in order to send the message "AT*LED=5,6,1,2" to the drone.   

Cross compilation of the code and setup of the environment is managed as in the post by taghof on [Compiling code for the AR.Drone][7].
After installation, the environment is onvoked by calling:

		$ codesourcery-arm-2009q3.sh   
   

After that compilation of eg. udping.c may be executed by calling

		$ arm-none-linux-gnueabi-gcc udping.c -o hello_arm   
   

The program should then be transfered to the drone, eg. by ftp.

		$ ftp 192.168.1.1
		...
		ftp> put hello_arm   
   

Upon which you telnet to the drone, change directory in to /data/video and execute the newly transfered program.

		$ telnet 198.168.1.1

		# cd data/video
		# chmod +x hello_arm
		# ./hello_arm   
   

2.	On the first testrun the idea was to have a udp [server][02] listening to the control port 5556, in order to ease the debugging, ie. to make sure that the correct signal was transfered complete.
Though the Drones parrot control program had initially called first dibs on the 5556 port, so a 'killall program.elf' was initiated. With this the new listener program can use the socket interface alone.   

The server or listener was sat to listen for one udp package, then print the message to stdout and then terminate. The program was good in determining the cause of a faulty udp client. The Client was editted to send a correctly formatted AT-command by help from the server/listener program.   

3.	program.elf was once again restarted, in order to see the effects of the command to initiate LED animation. 'hello_arm' was also started again. The effekt of issuing the LED animations command was seen ... it changed the ligt of one motor indicator LED from the color green to the color red ...   


Results
=======
The experiment showed that it is indeed possible to issue ATcomamnd with UDP packages sent from onboard the AR.Drone itself.   

Future experiments may contain more sequentially timed function calls eg. watchdog timely kicks, keep alive signals etc. and maybe a few experiments with autonomous flying without any human intervention, maybe.


References
==========
on py-sockets and AT commands:   
[Examples of ATcommands in use][2]   
[Venthurs pythonlib for Drone control][1]   

on SDK AT commands:   
[AR.Drone SDK Developer Guide][6]   

on sockets in C:   
[a man page for socket][5]   
[example from sub.nokia][3]   
[example from hi-ranking google sweed...][4]   

our own work:   
[taghofs blog entry on cross combilation for ar.drone][7]   
[udp'ing.c][01]   
[udp server][02]   

<!-- references -->
[1]: https://github.com/venthur/python-ardrone "python-ardrone"
[2]: https://github.com/venthur/python-ardrone/blob/master/libardrone.py "python code for sending commands to the AR.Drone"

[5]: http://www.freebsd.org/cgi/man.cgi?query=socket&apropos=0&sektion=0&manpath=FreeBSD+9.0-RELEASE&arch=default&format=html
[3]: http://www.developer.nokia.com/Community/Wiki/Open_C_Sockets:_send,_sendto,_sendmsg_methods "udp sendto.c"
[4]: http://www.abc.se/~m6695/udp.html "udp programII"
[6]: http://abstract.cs.washington.edu/~shwetak/classes/ee472/notes/ARDrone_SDK_1_6_Developer_Guide.pdf "AR.Drone SDK Developer Guide"
[7]: http://taghof.github.com/Navigation-for-Robots-with-WIFI-and-CV/blog/2012/01/13/Compiling-Code-For-The-ARDrone/ "cross combilation"

<!-- downloads -->
[01]: /Navigation-for-Robots-with-WIFI-and-CV/downloads/udp_onboard/udping.c "hello world of udp on ARDrone LED"
[02]: http://cs.au.dk/~tysse/speciale/ciaoserver.c

