#!/usr/bin/env python2.7

#import struct
import sys
#import socket
import os
#import threading
#import Video
import Controller
import Receiver
import Utils

NAV_PORT = 5554
VIDEO_PORT = 5555
CMD_PORT = 5556

MULTICAST_IP = '224.1.1.1'
DRONE_IP = '192.168.1.1'
TEST_DRONE_IP = '127.0.0.1'
INTERFACE_IP = '192.168.1.2'

DEBUG = False
TEST = False        
MULTI = False

class Drone(object):

    def __init__(self, test):
        pass

def main():
    videosensor = Receiver.Receiver(TEST, MULTI)
    videosensor.start()

    controller = Controller.Controller(True, videosensor)
    controller.start()
    print 'derp1'
    controller.join()
    print 'derp2'
    videosensor.stop()
    print 'derp3'

if __name__ == '__main__':
    main()
