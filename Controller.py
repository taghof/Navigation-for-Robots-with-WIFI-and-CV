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

import struct
import sys
import socket
import os
import threading
import pygame
#import ManualControl
#import AutoControl
import Utils

NAV_PORT = 5554
VIDEO_PORT = 5555
CMD_PORT = 5556

MULTICAST_IP = '224.1.1.1'
DRONE_IP = '192.168.1.1'
TEST_DRONE_IP = '127.0.0.1'
INTERFACE_IP = '192.168.1.2'

DEBUG = False
        

class ControllerManager(object):
    def __init__(self, drone):
        self.drone = drone
        self.interface = ControllerInterface()
        self.controllers = (ManualControl(self.drone, self.interface), AutoControl(self.drone,self.interface))
        
    def getControllers(self):
        return self.controllers

    def addController(self, controller):
        self.controllers.append(controller)

    def removeController(self, controller):
        self.controllers.remove(controller)

    def stop(self):
        self.stopControllers()

    def stopControllers(self):
        for con in self.controllers:
            con.stop()

class Controller(object):
    
    def __init__(self, drone, interface):
        self.drone = drone
        self.controlInterface = interface
        self.controlButton = None
        self.controlMethod = self.processEvents
        self.stopping = False
        
    def processEvents(self):
        return False
    
    def setControlButton(self, button):
        self.controlButton = button

    def getControlButton(self):
        return self.controlButton

    def setControlMethod(self, method):
        self.controlMethod = method

    def getControlMethod(self):
        return self.controlMethod

    def stop(self):
        print "Shutting " + str(self)
        self.stopping = True

class AutoControl(Controller):    

    def __init__(self, drone, interface):
        Controller.__init__(self, drone, interface)

    def processEvents(self):

        if self.controlButton:
            return self.controlButton.get_active()
        else:
            return True

class ManualControl(Controller):    

    def __init__(self, drone, interface):
        Controller.__init__(self, drone, interface)
        pygame.joystick.init()

        if pygame.joystick.get_count() > 0:
            pygame.display.init()
            self.js = pygame.joystick.Joystick(0)
            self.js.init()
            self.cstring = "joystick: " + str(self.js.get_name()) + "\r"
            self.controlMethod = self.processEvents
            self.control = True
            print self.cstring
        else:
            self.cstring = "keyboard"
            self.controlMethod = None
            self.control = False
        
    def getJoystickAttached(self):
        if self.control:
            return True
        else: 
            return False

    def processEvents(self):
        if self.control:
            for e in pygame.event.get(): # iterate over event stack
                Utils.dprint(DEBUG, 'event : ' + str(e.type))
                
                if e.type == pygame.JOYAXISMOTION: 
                    roll = self.js.get_axis(0)
                    pitch = self.js.get_axis(1)
                    yaw = self.js.get_axis(3)
                    power2 = self.convert( self.js.get_axis(2) )
                    power1 = self.convert( self.js.get_axis(5) )
                    power = power1 - power2
                    self.controlInterface.move(roll, pitch, power, yaw)
                    Utils.dprint( DEBUG, 'roll: ' + str(roll) + ' pitch: ' + str(pitch) + ' power: ' + str(power) + ' yaw: ' + str(yaw) )                   
                    
                elif e.type == pygame.JOYBUTTONDOWN: # 10
                    for b in xrange(self.js.get_numbuttons()):
                                                
                        if self.js.get_button(b) > 0:
                            print 'number of button pushed: ' + str(b)
                            # if b==0:
                            #     self.controllerInterface.autocontrol.stop()
                            #     self.controllerInterface.stop()
                            #     self.stop()
                            #     break
                            if b==1:
                                self.controlInterface.reset() 
                            elif b==2:
                                self.drone.gui.toggleVideoWindow(None)
                               
                            elif b==3:
                                self.controlInterface.ledShow(6)
                            # elif b==4:
                            #     pass
                            elif b==5:
                                self.controlInterface.zap()
                            # elif b==6:
                            #     pass
                            # elif b==7:
                            #     pass
                            elif b==8:
                                if self.controlInterface.getLanded():
                                    self.controlInterface.takeoff()
                                else:
                                    self.controlInterface.land()
                                # elif b==9:
                                #     pass
                                # elif b==10:
                                #     pass
                            elif b==11:
                                self.controlInterface.rotate(-1)
                            elif b==12:
                                self.controlInterface.rotate(1)
                              # elif b==13:
                              #     pass
                              # elif b==14:
                              #     pass
                          
        if self.controlButton:
            return self.controlButton.get_active()
        else:
            return True

    def stop(self):
        Controller.stop(self)
        self.controlInterface.stop()
        pygame.joystick.quit()
        pygame.display.quit()

# *************************** Utils ***************************************
    
    def convert(self, num):
        nump = num +1
        if nump > 0:
            return nump/2
        else:
            return nump



class ControllerInterface(object):
    def __init__(self):
        self.landed = True
        self.lock = threading.Lock()
        self.seq_num = 1
        self.timer_t = 0.1
        self.com_watchdog_timer = threading.Timer(self.timer_t, self.commwdg)
        self.speed = 0.2
        self.at(at_config, "general:navdata_demo", "TRUE")
        self.chan = 0
   
    def zap(self):
        print 'zapping: ' + str(self.chan)
        self.at(at_config, "video:video_channel", str(self.chan))
        self.at(at_zap, self.chan)
        self.chan += 2
        self.chan = self.chan % 8

    def stop(self):
        self.land()
        self.com_watchdog_timer.cancel()
    
    def commwdg(self):
        self.at(at_comwdg)
        if not self.landed:
            self.at(at_ref, True)
        else:
            self.at(at_ref, False)

    def getLanded(self):
        return self.landed

    def setLanded(self, state):
        self.landed = state

    def takeoff(self):
        Utils.dprint(DEBUG, 'Taking off!')
        self.at(at_ftrim)
        self.at(at_config, "control:altitude_max", "40000")
        self.at(at_ref, True)
        # TODO: implement check for takeoff
        self.setLanded(False)
           
    def land(self):
        Utils.dprint(DEBUG, 'Landing')
        self.at(at_ref, False)
        # TODO: implement check for landed
        self.setLanded(True)

    def reset(self):
        Utils.dprint(DEBUG, 'Resetting')
        self.at(at_ref, False, True)
        self.at(at_ref, False, False)
               
    def ledShow(self, num):
        self.at(at_led, num, 1.0, 2)

    def move(self, roll, pitch, power, yaw):

        if roll > 0.35 or roll < -0.35 :
            r = roll
        else:
            r = 0.0

        if pitch > 0.35 or pitch < -0.35 :
            pi = pitch 
        else:
            pi = 0.0

        if power > 0.35 or power < -0.35 :
            po = power
        else:
            po = power

        if yaw > 0.35 or yaw < -0.35 :
            y = yaw
        else:
            y = 0.0

        if r == 0.0 and pi == 0.0 and po == 0.0 and y == 0.0:
            self.at(at_pcmd, False, r, pi, po, y)
        else:
            self.at(at_pcmd, True, r, pi, po, y)
        
    def rotate(self, dir):
        if dir > 0:
            Utils.dprint(DEBUG, ' Rotating clockwise!')
            self.at(at_pcmd, True, 0, 0, 0, -self.speed)
        elif dir < 0:
            Utils.dprint(DEBUG, 'Rotating counterclockwise!')
            self.at(at_pcmd, True, 0, 0, 0, self.speed)
        else:
            Utils.dprint(DEBUG, 'Stopping rotation!')
            self.at(at_pcmd, True, 0, 0, 0, 0.0)

    
    def at(self, cmd, *args, **kwargs):
        """Wrapper for the low level at commands.

        This method takes care that the sequence number is increased after each
        at command and the watchdog timer is started to make sure the drone
        receives a command at least every second.
        """
        self.lock.acquire()
        self.com_watchdog_timer.cancel()
        cmd(self.seq_num, *args, **kwargs)
        self.seq_num += 1
        self.com_watchdog_timer = threading.Timer(self.timer_t, self.commwdg)
        self.com_watchdog_timer.start()
        self.lock.release()







#=====================================================================================
# Low level functions
#=====================================================================================
def at_ref(seq, takeoff, emergency=False):
        """
        Basic behaviour of the drone: take-off/landing, emergency stop/reset)
        
        Parameters:
        seq -- sequence number
        takeoff -- True: Takeoff / False: Land
        emergency -- True: Turn of the engines
        """
        p = 0b10001010101000000000000000000
        if takeoff:
            p += 0b1000000000
        if emergency:
            p += 0b0100000000
        at("REF", seq, [p])

def at_pcmd(seq, progressive, lr, fb, vv, va):
    """
    Makes the drone move (translate/rotate).

    Parameters:
    seq -- sequence number
    progressive -- True: enable progressive commands, False: disable (i.e.
        enable hovering mode)
    lr -- left-right tilt: float [-1..1] negative: left, positive: right
    rb -- front-back tilt: float [-1..1] negative: forwards, positive:
        backwards
    vv -- vertical speed: float [-1..1] negative: go down, positive: rise
    va -- angular speed: float [-1..1] negative: spin left, positive: spin 
        right

    The above float values are a percentage of the maximum speed.
    """
    p = 1 if progressive else 0
    at("PCMD", seq, [p, float(lr), float(fb), float(vv), float(va)])

def at_led(seq, anim, f, d):
    """
    Control the drones LED.

    Parameters:
    seq -- sequence number
    anim -- Integer: animation to play
    f -- ?: frequence in HZ of the animation
    d -- Integer: total duration in seconds of the animation
    """
    at("LED", seq, [anim, float(f), d])

def at_comwdg(seq):
    """
    Reset communication watchdog.
    """
    # FIXME: no sequence number
    at("COMWDG", seq, [])

def at_ftrim(seq):
    """
    Tell the drone it's lying horizontally.

    Parameters:
    seq -- sequence number
    """
    at("FTRIM", seq, [])

def at_zap(seq, stream):
    """
    Selects which video stream to send on the video UDP port.

    Parameters:
    seq -- sequence number
    stream -- Integer: video stream to broadcast
    """
    # FIXME: improve parameters to select the modes directly
    at("ZAP", seq, [stream])

def at_config(seq, option, value):
    """Set configuration parameters of the drone."""
    at("CONFIG", seq, [str(option), str(value)])


def at(command, seq, params):
    """
    Parameters:
    command -- the command
    seq -- the sequence number
    params -- a list of elements which can be either int, float or string
    """
    param_str = ''
    for p in params:
        if type(p) == int:
            param_str += ",%d" % p
        elif type(p) == float:
            param_str += ",%d" % f2i(p)
        elif type(p) == str:
            param_str += ',"'+p+'"'
            
    msg = "AT*%s=%i%s\r" % (command, seq, param_str)
    if command != "COMWDG":
        Utils.dprint(DEBUG, msg)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(msg, (DRONE_IP, CMD_PORT))
                
def f2i(f):
    #Interpret IEEE-754 floating-point value as signed integer.
    return struct.unpack('i', struct.pack('f', f))[0]
#======================================================================================


