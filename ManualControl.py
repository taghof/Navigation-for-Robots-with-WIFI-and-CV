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
from pygame.locals import *
import threading
import Utils
import Drone
import time

DEBUG = True
JOY = 0
KEY = 1
NONE = 2

FLIGHT = 1
TEST = 2

class ManualControl(threading.Thread):    

    def __init__(self, controller):
        threading.Thread.__init__(self)
        pygame.joystick.init()

        self.controller = controller
        self.stopping = False
        self.mode = TEST
        self.controlButton = None
       

        if pygame.joystick.get_count() > 0:
            pygame.display.init()
            self.js = pygame.joystick.Joystick(0)
            self.js.init()
            self.cstring = "joystick: " + str(self.js.get_name())
            self.controlMethod = self.processJoystickEvents
            self.control = JOY
        else:
            self.cstring = "keyboard"
            self.controlMethod = None
            self.control = NONE

        return self.cstring
        
    def getJoystickAttached(self):
        if self.control == JOY:
            return True
        else: 
            return False


    def processJoystickEvents(self):
        if self.control == JOY:
            for e in pygame.event.get(): # iterate over event stack
                Utils.dprint(DEBUG, 'event : ' + str(e.type))
                
                if e.type == pygame.JOYAXISMOTION: 
                    roll = self.js.get_axis(0)
                    pitch = self.js.get_axis(1)
                    yaw = self.js.get_axis(3)
                    power2 = self.convert( self.js.get_axis(2) )
                    power1 = self.convert( self.js.get_axis(5) )
                    power = power1 - power2
                    self.controller.move(roll, pitch, power, yaw)
                    Utils.dprint( DEBUG, 'roll: ' + str(roll) + ' pitch: ' + str(pitch) + ' power: ' + str(power) + ' yaw: ' + str(yaw) )                   
                    
                elif e.type == pygame.JOYBUTTONDOWN: # 10
                    for b in xrange(self.js.get_numbuttons()):
                                                
                        if self.js.get_button(b) > 0:
                            print 'number of button pushed: ' + str(b)
                            if b==0:
                                self.controller.autocontrol.stop()
                                self.controller.stop()
                                self.stop()
                                break
                            elif b==1:
                                self.controller.reset() 
                            elif b==2:
                                if self.controller.autocontrol.video:
                                    self.controller.autocontrol.hideVideo()
                                else:
                                    self.controller.autocontrol.showVideo()
                            elif b==3:
                                self.controller.ledShow(6)
                            # elif b==4:
                            #     pass
                            elif b==5:
                                self.controller.zap()
                            # elif b==6:
                            #     pass
                            # elif b==7:
                            #     pass
                            elif b==8:
                                if self.controller.getLanded():
                                    self.controller.takeoff()
                                else:
                                    self.controller.land()
                                # elif b==9:
                                #     pass
                                # elif b==10:
                                #     pass
                            elif b==11:
                                self.controller.rotate(-1)
                            elif b==12:
                                self.controller.rotate(1)
                              # elif b==13:
                              #     pass
                              # elif b==14:
                              #     pass
                          
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
        Utils.dprint(DEBUG, 'Shutting down manual controller\r')
        self.stopping = True
        pygame.joystick.quit()
        pygame.display.quit()

# *************************** Utils ***************************************

    def getCharWithBreak(self):
        import sys, tty, termios, select
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            while not self.stopping:
                rlist, _, _ = select.select([sys.stdin], [], [], 1)
                if rlist:
                    s = sys.stdin.read(1)
                    return s
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    
    def convert(self, num):
        nump = num +1
        if nump > 0:
            return nump/2
        else:
            return nump
