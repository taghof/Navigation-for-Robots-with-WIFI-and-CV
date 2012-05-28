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
import utils
import settings
import time

class Drone(object):


    def __init__(self, video, gui):
        self.svideo = video
        self.sgui = gui

        self.sensors = []
        
        self.video_sensor = receivers.VideoReceiver(settings.VIDEO_PORT)
        self.sensors.append(self.video_sensor)
        
        self.wifi_sensor = receivers.WifiReceiver(settings.WIFI_PORT)
        self.sensors.append(self.wifi_sensor)
        
        self.navdata_sensor = receivers.NavdataReceiver(settings.NAVDATA_PORT)
        self.sensors.append(self.navdata_sensor)
        
        self.interface = controllers.ControllerInterface()

        self.controller_manager = controllers.ControllerManager(self)
        if self.sgui:
            import presenter
            self.gui = presenter.PresenterGui(self)
        elif self.svideo:
            import presenter
            self.gui = presenter.VideoWindow(self.video_sensor, self.controller_manager.get_controller(settings.AUTOCONTROL), self)#PresenterGui(self)
        else:
            self.gui = None
            
    def get_sensors(self):
        return self.sensors

    def start(self):
       
        for sensor in self.sensors:
            sensor.start()
            while not sensor.get_status() == settings.RUNNING:
                pass

        time.sleep(0.1)
        if self.svideo or self.gui is None:
            navdata = self.navdata_sensor.get_data()
            bat   = navdata.get(0, dict()).get('battery', 0)
            print 'Battery: ' + str(bat) + '\r'
        
        self.interface.start()
        self.controller_manager.start_controllers()
        if self.svideo or self.sgui:
            self.gui.show()
        
    def stop(self, gui=False):
        if not gui:
            if self.svideo or self.sgui:
                self.gui.stop(None, None)
                return 0

        self.controller_manager.stop()

        for sensor in self.sensors:
            sensor.stop()
        
        self.interface.stop()
        return 0
                

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

    def sigint_handler(self, arg1, arg2):
        print 'You pressed Ctrl+C!'
        self.stop()
        sys.exit(0)

def main():
    video, gui = False, False
    arg_len = len(sys.argv)
    for i in range(arg_len):
        if sys.argv[i] == '-v':
            video = True
        elif sys.argv[i] == '-g':
            gui = True
        elif sys.argv[i] == '-t':
            settings.TEST = True


    os.system('clear')
    if settings.TEST:
        import testdevice
        testdevice_ = testdevice.TestDevice(False)
        testdevice_.start()

    drone = Drone(video, gui)
    drone.start()
    signal.signal(signal.SIGINT, drone.sigint_handler)

    if settings.TEST:
        drone.get_video_sensor().join()
        testdevice_.stop()


   
if __name__ == '__main__':
    main()
