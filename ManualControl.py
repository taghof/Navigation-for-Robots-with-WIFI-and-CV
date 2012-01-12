#!/usr/bin/env python2.7

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

class ManualControl(threading.Thread):    

    def __init__(self, controller):
        threading.Thread.__init__(self)
        self.controller = controller
        self.stopping = False

        pygame.init()
        pygame.joystick.init()

        if pygame.joystick.get_count() > 0:
            self.js = pygame.joystick.Joystick(0)
            self.js.init()
            print self.js.get_name()
            self.mode = JOY
        else:
            print 'No joystick available, defaulting to keyboard mode'
            self.mode = KEY
        
    def convert(self, num):
        nump = num +1
        if nump > 0:
            return nump/2
        else:
            return nump

    def run(self):
        Utils.dprint(DEBUG, 'control loop started')
        if self.mode == JOY:
            while not self.stopping:
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
                         
        else:
            while not self.stopping:
                s = Utils.getChar()

                if s == '\x20':
                    if self.controller.getLanded():
                        self.controller.takeoff()
                        print 'takeoff!'
                    else:
                        self.controller.land()
                        print 'landing!'

                elif s == '\x1b':
                    self.controller.stop()
                    self.controller.autocontrol.stop()
                    self.stop()
                    
                elif s == 'd':
                    self.controller.move(1.0, 0.0, 0.0, 0.0)
                    time.sleep(0.1)
                    self.controller.move(0.0, 0.0, 0.0, 0.0)
                elif s == 'a':
                    self.controller.move(-1.0, 0.0, 0.0, 0.0)
                    time.sleep(0.1)
                    self.controller.move(0.0, 0.0, 0.0, 0.0)
                elif s == 's':
                    self.controller.move(0.0, 1.0, 0.0, 0.0)
                    time.sleep(0.1)
                    self.controller.move(0.0, 0.0, 0.0, 0.0)
                elif s == 'w':
                    self.controller.move(0.0, -1.0, 0.0, 0.0)
                    time.sleep(0.1)
                    self.controller.move(0.0, 0.0, 0.0, 0.0)
                elif s == 'o':
                    self.controller.move(0.0, 0.0, 1.0, 0.0)
                    time.sleep(0.1)
                    self.controller.move(0.0, 0.0, 0.0, 0.0)
                elif s == 'p':
                    self.controller.move(0.0, 0.0, -1.0, 0.0)
                    time.sleep(0.1)
                    self.controller.move(0.0, 0.0, 0.0, 0.0)
                elif s == 'q':
                    self.controller.move(0.0, 0.0, 0.0, 1.0)
                    time.sleep(0.1)
                    self.controller.move(0.0, 0.0, 0.0, 0.0)
                elif s == 'e':
                    self.controller.move(0.0, 0.0, 0.0, -1.0)
                    time.sleep(0.1)
                    self.controller.move(0.0, 0.0, 0.0, 0.0)
                elif s == 'r':
                    self.controller.reset()
                elif s == 'v':
                    if self.controller.autocontrol.video:
                        self.controller.autocontrol.hideVideo()
                    else:
                        self.controller.autocontrol.showVideo()
                                        
    def stop(self):
        Utils.dprint(DEBUG, '4: Stopping ManualControl thread')
        self.stopping = True
