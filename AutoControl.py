#!/usr/bin/env python2.7

import sys
import pygame
import threading
import Utils
import Drone
import cv
import time

DEBUG = True

class AutoControl(threading.Thread):    

    def __init__(self, controller, sensor):
        threading.Thread.__init__(self)
        self.lock = threading.Lock()
        self.controller = controller
        self.stopping = False
        self.video = False
        self.sensor = sensor
        self.videoruns = 0
        self.imagesretrieved = 0
        self.controlButton = None
        self.controlMethod = self.processAutoControlEvents
        return "auto control"


    def processAutoControlEvents(self):
        print "Processing autocontrol\r"
        if self.controlButton:
            return self.controlButton.get_active()
        else:
            return True

    def setControlButton(self, button):
        self.controlButton = button

    def getControlButton(self):
        return self.controlButton

    def setControlMethod(self, method):
        self.controlMethod = method

    def getControlMethod(self):
        return self.controlMethod

    def stop(self):
        Utils.dprint(DEBUG, '4: Stopping AutoControl thread')
        self.stopping = True


