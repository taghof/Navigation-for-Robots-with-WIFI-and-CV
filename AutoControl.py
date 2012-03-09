#!/usr/bin/env python2.7
#
#    Copyright (c) 2012 Morten Daugaard
#
#    Permission is hereby granted, free of charge, to any person obtaining a copy
#    of this software and associated documentation files (the "Software"), to deal
#    in the Software without restriction, including without limitation the rights
#    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#    copies of the Software, and to permit persons to whom the Software is
#    furnished to do so, subject to the following conditions:
#
#    The above copyright notice and this permission notice shall be included in
#    all copies or substantial portions of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#    THE SOFTWARE.

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


