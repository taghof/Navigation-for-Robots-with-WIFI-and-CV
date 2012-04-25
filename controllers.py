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
import time

import cv2.cv as cv
import cv2

import utils
import settings
import matcher

class ControllerManager(object):


    def __init__(self, drone):
        self.drone = drone
        self.interface = ControllerInterface()
        auto = AutoControl(self.drone,self.interface)
        man = ManualControl(self.drone, self.interface, auto)
        self.controllers = []
        self.controllers.append(man)
        self.controllers.append(auto)

    def get_controllers(self):
        return self.controllers

    def get_controller(self, id):
        controllers = self.get_controllers()
        for con in controllers:
            if con.id == id:
                return con
            
        return None

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
        self.id = None       
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
        self.control_interface.stop()
        self.stopping = True

class AutoControl(Controller):    


    def __init__(self, drone, interface):
        Controller.__init__(self, drone, interface)
        self.navdata_sensor = drone.get_navdata_sensor()
        self.wifi_sensor = drone.get_wifi_sensor()
        self.video_sensor = drone.get_video_sensor()
        self.id = settings.AUTOCONTROL
        self.name = "Auto Controller"
        
        self.unstarted_tasks = []
        self.active_tasks = []
        
        self.lock = threading.Lock()
        
        self.mark = []
        self.init_mark()
        self.mark_acquired = False
        self.mark_search = False
        self.last_match_image = None

    def init_mark(self, markpics=None):
        if markpics is None:
            self.mark.append(cv2.imread('./mark3e.png', 0))
            self.mark.append(cv2.imread('./mark3f.png', 0))
            self.mark.append(cv2.imread('./mark3g.png', 0))
            self.mark.append(cv2.imread('./mark3h.png', 0))

    def toggle_mark_search(self):
        self.mark_search = not self.mark_search

    def search_for_mark(self):
        matching = None
        frame_org = self.video_sensor.get_data()
        frame = cv.CreateImage ((frame_org.width, frame_org.height), cv.IPL_DEPTH_8U, 1)
        cv.CvtColor(frame_org, frame, cv.CV_RGB2GRAY)
        match_frame = utils.cv2array(frame)
        num = 0
       
        for m in self.mark:
            matching = matcher.match(m, match_frame)
            if matching is not None and matching[1] > num:
                num = matching[1]
                matching = matching
        if num:
            self.last_match_image = matching[0]

        if matching is not None and matching[1] >= 5:
            self.last_match_image = None
            return matching
        else:
            return None

    def process_events(self):
        self.lock.acquire()
        
        
        if not self.mark_acquired and self.mark_search:
            print 'Searching...'
            mark = self.search_for_mark()
            if not mark is None:
                self.unstarted_tasks.append(self.create_track_point_task(mark[2]))
                self.mark_acquired = True
        
        for task in self.unstarted_tasks:
            task.start()
            self.unstarted_tasks.remove(task)
            self.active_tasks.append(task)

        self.lock.release()

        if self.control_button is not None:
            return self.control_button.get_active()
        else:
            return not self.stopping


    def stop(self):
        self.lock.acquire()
        for task in self.active_tasks:
            task.stop()
            task.join()
        self.lock.release()        
        Controller.stop(self)

    def move_rotate(self, degrees):
        pass

    def get_altitude(self):
        return self.navdata_sensor.get_data().get(0, dict()).get('altitude', 0)

    def get_psi(self):
        return self.navdata_sensor.get_data().get(0, dict()).get('psi', 0)

    def get_phi(self):
        return self.navdata_sensor.get_data().get(0, dict()).get('phi', 0)

    def get_theta(self):
        return self.navdata_sensor.get_data().get(0, dict()).get('theta', 0)

    def actual_move(self, x, y, power, yaw):
        self.control_interface.move(x, y, power, yaw, True)

    def move_vertically(self, dist):
        pass
    
    def lost_track(self, caller):
        self.mark_acquired = False
        self.task_done(caller)

    def task_done(self, caller):
        self.active_tasks.remove(caller)

    def create_track_point_task(self, point=(88,72)):
        tracker = utils.PointTracker(self.video_sensor, self.navdata_sensor, point)
        t = utils.PIDxy(tracker, self.actual_move, self.lost_track)
        return t

    def start_auto_session(self, point=(88,72)):
        tracker = utils.PointTracker(self.video_sensor, self.navdata_sensor, point)
        #t.append(utils.PID(self.get_psi, self.actual_move, 180))
        t = utils.PIDxy(tracker, self.actual_move)
        self.unstarted_tasks.append(t)

class ManualControl(Controller):    


    def __init__(self, drone, interface, auto_control):
        Controller.__init__(self, drone, interface)
        pygame.joystick.init()
        self.auto_control = auto_control
        self.id = settings.JOYCONTROL
        self.name = "Joystick Controller"
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
                    print self.js.get_axis(2)
                    print self.js.get_axis(5)
                    power2 = self.convert( self.js.get_axis(2) )
                    power1 = self.convert( self.js.get_axis(5) )
                    power = power1 - power2
                    #print "power:" + str(power)
                    self.control_interface.move(roll, pitch, power, yaw, False)
                    # print 'roll: ' + str(roll) + ' pitch: ' + str(pitch) + ' power: ' + str(power) + ' yaw: ' + str(yaw)                    
                    
                elif e.type == pygame.JOYBUTTONDOWN: # 10
                    for b in xrange(self.js.get_numbuttons()):
                                                
                        if self.js.get_button(b) > 0:
                            print 'number of button pushed: ' + str(b)
                            if b==0:
                                self.control_interface.zap()
                            elif b==1:
                                self.control_interface.reset() 
                            elif b==2:
                                self.drone.gui.toggle_video_window(None)
                            elif b==3:
                                self.control_interface.flat_trim()
                                #self.control_interface.led_show(5)
                            elif b==4:
                                self.drone.gui.set_target(None)
                            elif b==5:
                                self.drone.gui.take_sample(None)
#
                            elif b==6:
                                c = self.auto_control.current
                                if c is not None:
                                    c.toggle_verbose()
                                else:
                                    print "No task"
                          
                            # elif b==7:
                            #     pass
                            elif b==8:
                                if self.control_interface.get_landed():
                                    self.control_interface.take_off()
                                else:
                                    self.control_interface.land()
                                # elif b==9:
                                #     pass
                                # elif b==10:
                                #     pass
                            elif b==11:
                                c = self.auto_control.current
                                if c is not None:
                                    p = c.getKp()
                                    c.setKp(p - 0.05)
                                else:
                                    print "No task"
                          
                            elif b==12:
                                c = self.auto_control.current
                                if c is not None:
                                    p = c.getKp()
                                    c.setKp(p + 0.05)
                                else:
                                    print "No task"
                          
                            elif b==13:
                                c = self.auto_control.current
                                if c is not None:
                                    d = c.getKd()
                                    c.setKd(d + 0.05)
                                else:
                                    print "No task"
                          
                            elif b==14:
                                c = self.auto_control.current
                                if c is not None:
                                    d = c.getKd()
                                    c.setKd(d - 0.05)
                                else:
                                    print "No task"
                          
        if self.control_button:
            return self.control_button.get_active()
        else:
            return True

    def stop(self):
        Controller.stop(self)
        self.control_interface.stop()
        pygame.joystick.quit()
        pygame.display.quit()

# *************************** utils ***************************************
    
    def convert(self, num):
        print "converting: " + str(num)
        nump = float(num) + 1.0
        if nump > 0:
            return nump/2.0
        else:
            return float(nump)


class ControllerInterface(object):
    def __init__(self):
        self.landed = True
        self.lock = threading.Lock()
        self.seq_num = 1
        self.timer_t = 0.1
        self.com_watchdog_timer = threading.Timer(self.timer_t, self.commwdg)
        self.speed = 0.2
        self.at(at_config, "general:navdata_demo", "TRUE")
        self.chan = 1
   
    def zap(self):
        print 'zapping: ' + str(self.chan)
        self.at(at_config, "video:video_channel", str(self.chan))

        self.chan += 1
        self.chan = self.chan % 4

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

    def flat_trim(self):
        self.at(at_ftrim)
        self.at(at_config, "control:altitude_max", "40000")

    def reset(self):
        utils.dprint("", 'Resetting')
        self.at(at_ref, False, True)
        self.at(at_ref, False, False)
               
    def led_show(self, num):
        self.at(at_led, num, 1.0, 2)
        
    def move(self, roll, pitch, power, yaw, auto=False):
        if roll > 0.10 or roll < -0.10 or auto:
            r = roll
        else:
            r = 0.0

        if pitch > 0.10 or pitch < -0.10 or auto:
            pi = pitch 
        else:
            pi = 0.0

        if power > 0.10 or power < -0.10 or auto:
            po = power
        else:
            po = power

        if yaw > 0.10 or yaw < -0.10 or auto:
            y = yaw
        else:
            y = 0.0
        
        if r == 0.0 and pi == 0.0 and po == 0.0 and y == 0.0:
            self.at(at_pcmd, False, r, pi, po, y)
        else:
            self.at(at_pcmd, True, r, pi, po, y)
            
    def rotate(self, dir, speed=0.2):
        if dir > 0:
            utils.dprint("", ' Rotating clockwise!')
            self.at(at_pcmd, True, 0, 0, 0, -speed)
        elif dir < 0:
            utils.dprint("", 'Rotating counterclockwise!')
            self.at(at_pcmd, True, 0, 0, 0, speed)
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


