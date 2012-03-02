#!/usr/bin/env python2.7

#import struct
import sys
#import socket
import os
#import threading
#import Video
import Controller
import VideoReceiver
import WifiReceiver
import Utils
import TestDevice
import Presenter
#import pygame
import time

DEBUG = False
GTKVAL = True

NAV_PORT = 5554
VIDEO_PORT = 5555
CMD_PORT = 5556

MULTICAST_IP = '224.1.1.1'
DRONE_IP = '192.168.1.1'
TEST_DRONE_IP = '127.0.0.1'
INTERFACE_IP = '192.168.1.2'

DEBUG = False
TEST = True#False        
MULTI = False

class Drone(object):

    def __init__(self, test, multi):
        self.videosensor = VideoReceiver.VideoReceiver(test, multi)
        self.wifisensor = WifiReceiver.WifiReceiver()
        self.controller = Controller.Controller(test, self)
        #self.presenter = Presenter.Presenter(test, self)
        self.gui = Presenter.PresenterGui(self)

    def start(self):
        #os.system('clear')
        self.videosensor.start()
        self.wifisensor.start()
        self.controller.start()
        #self.presenter.start()
        time.sleep(2)
        self.gui.start()

    def stop(self):
        time.sleep(1)
        #self.gui.stop()
        #self.presenter.stop()
        self.controller.stop()
        self.wifisensor.stop()
        self.videosensor.stop()
        
    def getVideoSensor(self):
        return self.videosensor
        
    def getWifiSensor(self):    
        return self.wifisensor

    def getPresenter(self):
        pass
        #return self.presenter

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
