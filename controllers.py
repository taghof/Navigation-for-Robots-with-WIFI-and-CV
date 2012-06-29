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
import tasks
import settings
import matcher

class ControllerManager(object):


    def __init__(self, drone):
        self.drone = drone
        auto = AutoControl(self.drone)
        man = ManualControl(self.drone)
        key = KeyboardControl(self.drone)
        self.controllers = []
        self.controllers.append(key)
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
        
    def start_controllers(self):
        for con in self.controllers:
            con.start()

class Controller(threading.Thread):

    
    def __init__(self, drone):
        threading.Thread.__init__(self)
        self.drone = drone
        self.control_interface = drone.get_interface()
        self.control_button = None
        self.control_method = self.process_events
        self.id = None       
        self.stopping = False
        self.update_time = 0.01

    def run(self):
        while self.control_method is not None and not self.stopping:
            self.control_method()
            time.sleep(self.update_time)
        print 'Ended: ', str(self), '\r'
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
        print "Shutting down " + str(self) + "\r"
        self.stopping = True

class AutoControl(Controller):    


    def __init__(self, drone):
        Controller.__init__(self, drone)
        self.drone = drone
        self.navdata_sensor = drone.get_navdata_sensor()
        #self.wifi_sensor = drone.get_wifi_sensor()
        self.video_sensor = drone.get_video_sensor()
        self.id = settings.AUTOCONTROL
        self.name = "Auto Controller"
        
        self.unstarted_tasks = []
        self.active_tasks = []
        
        self.lock = threading.Lock()

    def process_events(self):
        self.lock.acquire()
                        
        for task in self.unstarted_tasks:
            task.start()
            self.unstarted_tasks.remove(task)
            self.active_tasks.append(task)
            print self.active_tasks, '\r'
        self.lock.release()

        if self.control_button is not None:
            return self.control_button.get_active()
        else:
            return not self.stopping

    def kill_tasks(self):
        self.lock.acquire()
        for task in self.active_tasks:
            print 'killing: ', task, '\r'
            task.stop()
        self.lock.release()        
       
    def stop(self):
        Controller.stop(self)
        self.kill_tasks()

    def task_done(self, caller):
        print 'top level stopped: ', caller, '\r'
        self.active_tasks.remove(caller)

    def start_task_gui(self, widget=None):
        #self.lock.acquire()
        t = tasks.SeqCompoundTask(self.drone, self.task_done)
        t.set_conf_5()
        self.start_task(t)
        #self.unstarted_tasks.append(t)
        #self.lock.release()

    def start_task(self, task):
        self.lock.acquire()
        if not self.stopping:
            self.active_tasks.append(task)
            threading.Thread(target=task.run).start() 

        self.lock.release()
        return task

    def start_task_num(self, num):
        if num == 4:
            t = tasks.SeqCompoundTask(self.drone, self.task_done, None)
            t.set_conf_4()
            self.start_task(t)
        elif num == 5:
            t = tasks.SeqCompoundTask(self.drone, self.task_done, None)
            t.set_conf_5()
            self.start_task(t)
        elif num == 6:
            t = tasks.FollowTourTask(self.drone, self.task_done, None)
            #t.set_conf_5()
            self.start_task(t)
        elif num == 3:
            t = None#indsaet thomas' task her
            #self.start_task(t)
        else:
            return

class KeyboardControl(Controller):
    
    def __init__(self, drone):
        Controller.__init__(self, drone)
        #self.auto_control = drone.controller_manager.get_controller(settings.AUTOCONTROL)
        self.navdata_sensor = drone.get_navdata_sensor()
        self.id = settings.KEYCONTROL
        self.name = "Keyboard Controller"
        self.update_time = 0.05

    def process_events(self):
        self.auto_control = self.drone.get_controller_manager().get_controller(settings.AUTOCONTROL)
        ch = utils.get_char_with_break()
        if ch == 'q':
            self.drone.stop()
        if ch == 'z':
            print 'Zapping\r'
            self.drone.get_interface().zap()
        if ch == 'f':
            print 'Flat trimming\r'
            self.drone.get_interface().flat_trim()
        if ch == 'b':
            navdata = self.navdata_sensor.get_data()
            bat   = navdata.get(0, dict()).get('battery', 0)
            print 'Battery: ' + str(bat) + '\r'
        if ch == 'c':
            print 'Active tasks:\r'
            if len (self.auto_control.active_tasks) > 0:
                for t in self.auto_control.active_tasks: 
                    print t, '\r'
            else:
                print 'No active Tasks\r'

        if ch == 't':
            print 'Current threads:\r'
            for t in threading.enumerate(): 
                print t, '\r'


        if ch == '1':
            self.auto_control.start_task_num(6)
        if ch == '2':
            self.auto_control.start_task_num(3)
        if ch == '3':
            self.auto_control.start_task_num(3)

class ManualControl(Controller):    


    def __init__(self, drone):
        Controller.__init__(self, drone)
        pygame.joystick.init()
        
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
        self.auto_control = self.drone.get_controller_manager().get_controller(settings.AUTOCONTROL)
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
            
                    

                    self.control_interface.move(roll, pitch, power, yaw, False)
                    
                    # print self.js.get_axis(2)
                    # print self.js.get_axis(5)
                    # print "power:" + str(power)
                    # print 'roll: ' + str(roll) + ' pitch: ' + str(pitch) + ' power: ' + str(power) + ' yaw: ' + str(yaw) + 'auto: ' + str (self.control_interface.auto) + '\r'                     
                    
                elif e.type == pygame.JOYBUTTONDOWN: # 10
                    for b in xrange(self.js.get_numbuttons()):
                                                
                        if self.js.get_button(b) > 0:
                            #print 'number of button pushed: ' + str(b)
                            if b==0:
                                self.control_interface.zap()
                            elif b==1:
                                self.control_interface.reset() 
                            elif b==2:
                                self.auto_control.kill_tasks()
                            elif b==3:
                                self.auto_control.start_task_num(4)
                            elif b==4:
                                pass
                            elif b==5:
                                self.auto_control.start_task_num(6)
                            elif b==6:
                                pass
                            elif b==8:
                                if self.control_interface.get_landed():
                                    self.control_interface.take_off()
                                else:
                                    self.control_interface.land()
                            elif b==11:
                                pass
                            elif b==12:
                                pass
                            elif b==13:
                                pass
                            elif b==14:
                                pass
                         
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
        if num != 0:
            nump = float(num) + 1.0
        else:
            nump = 0

        if nump > 0:
            return nump/2.0
        else:
            return float(nump)


class ControllerInterface(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.lock = threading.Lock()
        self.zaplock = threading.Lock()
        self.seq_num = 1
        
        self.stopping = False
        self.sleep_time = 1.0
        
        self.chan = 1
        self.landed = True
        self.pitch = 0.0
        self.roll = 0.0
        self.yaw = 0.0
        self.gaz = 0.0
        self.auto = False

        if settings.TEST:
            self.at = self.__at_test
        else:
            self.at = self.__at_live

        self.at(at_config, "general:navdata_demo", "TRUE")
        #self.at(at_config, "general:navdata_demo", "FALSE")
        #self.at(at_config,"control:flying_mode","1")
        #self.at(at_config,"detect:detect_type","10")
        #self.at(at_config,"detect:detections_select_v","4")
        #self.at(at_config, "general:navdata_options","1024")

    def run(self):
        while not self.stopping:
            self.__commwdg()
            self.__update(self.roll, self.pitch, self.gaz, self.yaw, self.auto)
            time.sleep(self.sleep_time)
    
    def stop(self):
        self.land()
        self.stopping = True

    def move(self, roll, pitch, gaz, yaw, auto):
        if not roll is None:
            self.roll = roll
        if not pitch is None:
            self.pitch = pitch
        if not gaz is None:
            self.gaz = gaz
        if not yaw is None:
            self.yaw = yaw
        if not auto is None:
            self.auto = auto

    def take_off(self):
        utils.dprint("", 'Taking off!')
        self.at(at_ftrim)
        self.at(at_ftrim)
        self.at(at_ftrim)
        self.sleep_time = 0.05
        self.at(at_config, "control:altitude_max", "40000")
        self.at(at_ref, True)
        # TODO: implement check for takeoff
        self.__set_landed(False)
           
    def land(self):
        utils.dprint("", 'Landing')
        self.at(at_ref, False)
        # TODO: implement check for landed
        self.move(0.0, 0.0, 0.0, 0.0, False)
        self.sleep_time = 1.0
        self.__set_landed(True)
        
    def zap(self, ch=None):
        if ch is None:
            #print 'zapping: ' + str(self.chan) + '\r'
            self.at(at_config, "video:video_channel", str(self.chan))

            self.chan += 1
            self.chan = self.chan % 4
        else:
            #print 'zapping: ' + str(ch) + '\r'
            self.at(at_config, "video:video_channel", str(ch))

    def get_zaplock(self):
        return self.zaplock

    def flat_trim(self):
        self.at(at_ftrim)
        self.at(at_config, "control:altitude_max", "40000")

    def reset(self):
        utils.dprint("", 'Resetting')
        self.at(at_ref, False, True)
        self.at(at_ref, False, False)
               
    def led_show(self, num):
        self.at(at_led, num, 1.0, 2)
   
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

    def get_values(self):
        return [self.pitch, self.roll, self.yaw, self.gaz, self.auto]
     
    def __update(self, roll, pitch, power, yaw, auto=False):
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

    def get_landed(self):
        return self.landed

    def __set_landed(self, state):
        self.landed = state
   
    def __commwdg(self):
        self.at(at_comwdg)
        if not self.landed:
            self.at(at_ref, True)
        else:
            self.at(at_ref, False)
 
    def __at_live(self, cmd, *args, **kwargs):
        """Wrapper for the low level at commands.

        This method takes care that the sequence number is increased after each
        at command and the watchdog timer is started to make sure the drone
        receives a command at least every second.
        """
        self.lock.acquire()
        #self.com_watchdog_timer.cancel()
        cmd(self.seq_num, *args, **kwargs)
        self.seq_num += 1
        #self.com_watchdog_timer = threading.Timer(self.timer_t, self.commwdg)
        #self.com_watchdog_timer.start()
        self.lock.release()
        
    def __at_test(self, cmd, *args, **kwargs):
        #print 'AT test called with:\t' + str(cmd) + '\r'
        pass

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
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(msg, (settings.DRONE_IP, settings.CMD_PORT))
                
def f2i(f):
    #Interpret IEEE-754 floating-point value as signed integer.
    return struct.unpack('i', struct.pack('f', f))[0]


#======================================================================================


