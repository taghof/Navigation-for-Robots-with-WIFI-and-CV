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

import controllers
import receivers
import presenter
import testdevice
import utils
import settings

class Drone(object):


    def __init__(self):
        self.sensors = []
        
        self.video_sensor = receivers.VideoReceiver(settings.VIDEO_PORT)
        self.sensors.append(self.video_sensor)
        
        self.wifi_sensor = receivers.WifiReceiver(settings.WIFI_PORT)
        self.sensors.append(self.wifi_sensor)
        
        self.navdata_sensor = receivers.NavdataReceiver(settings.NAVDATA_PORT)
        self.sensors.append(self.navdata_sensor)
        
        self.controller_manager = controllers.ControllerManager(self)
        self.gui = presenter.PresenterGui(self)

    def get_sensors(self):
        return self.sensors

    def start(self):
       
        for sensor in self.sensors:
            sensor.start()
            while not sensor.get_status() == settings.RUNNING:
                pass

        # self.wifi_sensor.start()
        # while not self.wifi_sensor.get_status() == settings.RUNNING:
        #     pass

        # self.navdata_sensor.start()
        # while not self.navdata_sensor.get_status() == settings.RUNNING:
        #     pass
       
        self.gui.start()

    def stop(self):
        for sensor in self.sensors:
            sensor.stop()
        self.controller_manager.stop()

    def get_video_sensor(self):
        return self.video_sensor
        
    def get_wifi_sensor(self):    
        return self.wifi_sensor

    def get_navdata_sensor(self):
        return self.navdata_sensor

    def get_controller_manager(self):
        return self.controller_manager

    def get_gui(self):
        return self.gui

def main():
    os.system('clear')
    if settings.TEST:
        testdevice_ = testdevice.TestDevice(False)
        testdevice_.start()

    drone = Drone()
    drone.start()

    if settings.TEST:
        drone.get_video_sensor().join()
        testdevice_.stop()
   
if __name__ == '__main__':
    main()
