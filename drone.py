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
import sys
import signal
import threading

import controllers
import receivers
import virtualsensors
import newtasks as tasks
import utils
import settings
import time
import map

class Drone(object):


    def __init__(self, test):


        if test:
            settings.TEST = True
            import testdevice
            self.testdevice = testdevice.TestDevice(False)

        self.gui = None

        self.map = map.PosMap()

        self.sensors = []

        self.video_sensor = receivers.VideoReceiver(settings.VIDEO_PORT)
        self.sensors.append(self.video_sensor)
        
        self.wifi_sensor = receivers.WifiReceiver(settings.WIFI_PORT)
        self.sensors.append(self.wifi_sensor)
        
        self.navdata_sensor = receivers.NavdataReceiver(settings.NAVDATA_PORT)
        self.sensors.append(self.navdata_sensor)
        
        self.interface = controllers.ControllerInterface()

        self.task_manager = tasks.TaskManager(self)
        self.controller_manager = controllers.ControllerManager(self)
            
    def get_sensors(self):
        return self.sensors

    def start(self):
        self.detector_sensor = virtualsensors.Detector(self) 
        self.sensors.append(self.detector_sensor)


        if settings.TEST:
            self.testdevice.start()
       
        for sensor in self.sensors:
            sensor.start()
            while not sensor.get_status() == settings.RUNNING:
                pass

        time.sleep(0.2)
        if self.gui is None:
            navdata = self.navdata_sensor.get_data()
            if navdata is not None:
                bat   = navdata.get(0, dict()).get('battery', 0)
                print 'Battery: ' + str(bat) + '\r'
        
        self.interface.start()
       # self.task_manager.start()
        self.controller_manager.start_controllers()
               
    def stop(self, gui_stop=False):
        if not gui_stop and self.gui is not None:
            self.gui.stop(None, None)
            self.gui = None
            return 0
                    
        self.task_manager.stop()
        
        for sensor in self.sensors:
            sensor.stop()
        
        self.interface.stop()
        if settings.TEST:
            self.testdevice.stop()
        
        self.controller_manager.stop()
        return 0

    def get_map(self):
        return self.map

    def get_detector_sensor(self):
        return self.detector_sensor

    def get_task_manager(self):
        return self.task_manager

    def get_video_sensor(self):
        return self.video_sensor
        
    def get_wifi_sensor(self):    
        return self.wifi_sensor

    def get_navdata_sensor(self):
        return self.navdata_sensor

    def get_controller_manager(self):
        return self.controller_manager

    def get_interface(self):
        return self.interface
   
    def get_gui(self):
        return self.gui

def main():
    video, gui, test, map = False, False, False, False
    arg_len = len(sys.argv)
    for i in range(arg_len):
        if sys.argv[i] == '-v':
            video = True
        elif sys.argv[i] == '-g':
            gui = True
        elif sys.argv[i] == '-t':
            test = True
        elif sys.argv[i] == '-m':
            map = True
            
    os.system('clear')

    drone = Drone(test)
    drone.start()
    
    if gui:
        import presenter
        gui = presenter.PresenterGui(drone)
        drone.gui = gui
    
    elif video:
        import presenter
        gui = presenter.VideoWindow(drone)
        drone.gui = gui
    elif map:
        import mapdraw
        gui = mapdraw.TaskGUI(drone)
        drone.gui = gui
    else:
        gui = None
       
    if gui is not None:
        gui.show()
   
if __name__ == '__main__':
    main()
