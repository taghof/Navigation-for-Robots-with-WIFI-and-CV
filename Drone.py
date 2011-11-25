#!/usr/bin/env python2.7

import struct
import sys
import socket
import os
import threading
import Video
import Utils

NAV_PORT = 5554
VIDEO_PORT = 5555
CMD_PORT = 5556

MULTICAST_IP = '224.1.1.1'
DRONE_IP = '192.168.1.1'
TEST_DRONE_IP = '127.0.0.1'
INTERFACE_IP = '192.168.1.2'

DEBUG = False
        

class Drone(object):
    def __init__(self, test):
        self.landed = True
        self.test = test
        self.lock = threading.Lock()
        self.seq_num = 1
        self.timer_t = 0.1
        self.videothread = None
        self.com_watchdog_timer = threading.Timer(self.timer_t, self.commwdg)
        self.speed = 0.2
        self.at(at_config, "general:navdata_demo", "TRUE")
    
    def startVideo(self):
        if not self.videothread:
            self.videothread = Video.VideoThread(self.test, False, False)
            self.videothread.start()
        elif self.videothread and self.videothread.state == Video.STOPPING:
            self.Videothread = None
            self.videothread = Video.VideoThread(self.test, False, False)
            self.videothread.start()
        else:
            self.videothread.stop()


    def stop(self):
        self.land()
        self.com_watchdog_timer.cancel()
        if self.videothread:
            self.videothread.stop()
            
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
                
        # if true
        return True
            
    def land(self):
        Utils.dprint(DEBUG, 'Landing')
        self.at(at_ref, False)
        # if true
        return True

    def reset(self):
        Utils.dprint(DEBUG, 'Resetting')
        self.at(at_ref, False, True)
        self.at(at_ref, False, False)
        #if true
        return True
        
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
