#!/usr/bin/env python2.7

#import struct
import sys
#import socket
import os
#import threading
#import Video
import Controller
import Receiver
import WifiReceiver
import Utils
import TestDevice
import Presenter
import pygame

NAV_PORT = 5554
VIDEO_PORT = 5555
CMD_PORT = 5556

MULTICAST_IP = '224.1.1.1'
DRONE_IP = '192.168.1.1'
TEST_DRONE_IP = '127.0.0.1'
INTERFACE_IP = '192.168.1.2'

DEBUG = False
TEST = True        
MULTI = False

class Drone(object):

    def __init__(self, test, multi):
        self.videosensor = Receiver.Receiver(test, multi)
        self.wifisensor = WifiReceiver.WifiReceiver()
        self.controller = Controller.Controller(test, self)
        self.presenter = Presenter.Presenter(test, self)

    def start(self):
        self.videosensor.start()
        self.wifisensor.start()
        self.controller.start()
        self.presenter.start()

    def stop(self):
        self.presenter.stop()
        self.controller.stop()
        self.wifisensor.stop()
        self.videosensor.stop()

    def getVideoSensor(self):
        return self.videosensor
        
    def getWifiSensor(self):    
        return self.wifisensor

    def getPresenter(self):
        return self.presenter

    def getController(self):
        return self.controller

def main():

    if TEST:
        testdevice = TestDevice.TestDevice(False)
        testdevice.start()

    drone = Drone(TEST, MULTI)
    drone.start()


    if TEST:
        drone.getVideoSensor().join()
        testdevice.stop()

if __name__ == '__main__':
    main()
