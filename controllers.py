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
import os
import socket
import struct
import threading
import pygame

import utils
import settings

class ControllerManager(object):


    def __init__(self, drone):
        self.drone = drone
        self.interface = ControllerInterface()
        self.controllers = (ManualControl(self.drone, self.interface), AutoControl(self.drone,self.interface))
        
    def get_controllers(self):
        return self.controllers

    def add_controller(self, controller):
        self.controllers.append(controller)

    def remove_controller(self, controller):
        self.controllers.remove(controller)

    def stop(self):
        self.stop_controllers()

    def stop_controllers(self):
        for con in self.controllers:
            con.stop()

class Controller(object):

    
    def __init__(self, drone, interface):
        self.drone = drone
        self.control_interface = interface
        self.control_button = None
        self.control_method = self.process_events
        self.stopping = False
        
    def process_events(self):
        return False
    
    def set_control_button(self, button):
        self.control_button = button

    def get_control_button(self):
        return self.control_button

    def set_control_method(self, method):
        self.control_method = method

    def get_control_method(self):
        return self.control_method

    def stop(self):
        print "Shutting " + str(self)
        self.stopping = True

class AutoControl(Controller):    


    def __init__(self, drone, interface):
        Controller.__init__(self, drone, interface)

    def process_events(self):

        if self.control_button is not None:
            return self.control_button.get_active()
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
            self.control_method = self.process_events
            self.control = True
            print self.cstring
        else:
            self.cstring = "keyboard"
            self.control_method = None
            self.control = False
        
    def get_joystick_attached(self):
        if self.control:
            return True
        else: 
            return False

    def process_events(self):
        if self.control:
            for e in pygame.event.get(): # iterate over event stack
                utils.dprint("", 'event : ' + str(e.type))
                
                if e.type == pygame.JOYAXISMOTION: 
                    roll = self.js.get_axis(0)
                    pitch = self.js.get_axis(1)
                    yaw = self.js.get_axis(3)
                    power2 = self.convert( self.js.get_axis(2) )
                    power1 = self.convert( self.js.get_axis(5) )
                    power = power1 - power2
                    self.controlInterface.move(roll, pitch, power, yaw)
                    utils.dprint("", 'roll: ' + str(roll) + ' pitch: ' + str(pitch) + ' power: ' + str(power) + ' yaw: ' + str(yaw) )                   
                    
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
        self.control_interface.stop()
        pygame.joystick.quit()
        pygame.display.quit()

# *************************** utils ***************************************
    
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

    def get_landed(self):
        return self.landed

    def set_landed(self, state):
        self.landed = state

    def take_off(self):
        utils.dprint("", 'Taking off!')
        self.at(at_ftrim)
        self.at(at_config, "control:altitude_max", "40000")
        self.at(at_ref, True)
        # TODO: implement check for takeoff
        self.set_landed(False)
           
    def land(self):
        utils.dprint("", 'Landing')
        self.at(at_ref, False)
        # TODO: implement check for landed
        self.set_landed(True)

    def reset(self):
        utils.dprint("", 'Resetting')
        self.at(at_ref, False, True)
        self.at(at_ref, False, False)
               
    def led_show(self, num):
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
            utils.dprint("", ' Rotating clockwise!')
            self.at(at_pcmd, True, 0, 0, 0, -self.speed)
        elif dir < 0:
            utils.dprint("", 'Rotating counterclockwise!')
            self.at(at_pcmd, True, 0, 0, 0, self.speed)
        else:
            utils.dprint("", 'Stopping rotation!')
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
        utils.dprint("", msg)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(msg, (settings.DRONE_IP, settings.CMD_PORT))
                
def f2i(f):
    #Interpret IEEE-754 floating-point value as signed integer.
    return struct.unpack('i', struct.pack('f', f))[0]
#======================================================================================


