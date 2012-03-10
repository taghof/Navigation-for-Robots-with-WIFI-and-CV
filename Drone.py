#!/usr/bin/env python2.7

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

import os
import Controller
import Receiver
import Presenter
import TestDevice
import Utils
import Settings

class Drone(object):

    def __init__(self):
        self.videosensor = Receiver.VideoReceiver(Settings.VIDEO_PORT)
        self.wifisensor = Receiver.WifiReceiver(Settings.WIFI_PORT)
        self.navdatasensor = Receiver.NavdataReceiver(Settings.NAVDATA_PORT)
        self.controllerManager = Controller.ControllerManager(self)
        self.gui = Presenter.PresenterGui(self)

    def start(self):
       
        self.videosensor.start()
        while not self.videosensor.getStatus() == Settings.RUNNING:
            pass

        self.wifisensor.start()
        while not self.wifisensor.getStatus() == Settings.RUNNING:
            pass

        self.navdatasensor.start()
        while not self.navdatasensor.getStatus() == Settings.RUNNING:
            pass
       
        self.gui.start()

    def stop(self):
        self.wifisensor.stop()
        self.videosensor.stop()
        self.navdatasensor.stop()
        self.controllerManager.stop()

    def getVideoSensor(self):
        return self.videosensor
        
    def getWifiSensor(self):    
        return self.wifisensor

    def getNavdataSensor(self):
        return self.navdatasensor

    def getControllerManager(self):
        return self.controllerManager

    def getGUI(self):
        return self.gui

def main():
    os.system('clear')
    if Settings.TEST:
        testdevice = TestDevice.TestDevice(False)
        testdevice.start()

    drone = Drone()
    drone.start()

    if Settings.TEST:
        drone.getVideoSensor().join()
        testdevice.stop()
   
if __name__ == '__main__':
    main()
