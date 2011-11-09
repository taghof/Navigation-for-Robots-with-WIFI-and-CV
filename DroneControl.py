#!/usr/bin/env python2.7

import struct
import sys
import socket
import pygame
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

class ComThread(threading.Thread):
    def __init__(self):
        self.stopping = False
        

    def run(self):
        pass

    def stop(self):
        self.stopping = True
        

class Drone(object):
    def __init__(self):
        self.landed = True
        self.lock = threading.Lock()
        self.seq_num = 1
        self.timer_t = 0.1
        self.videothread = None
        self.com_watchdog_timer = threading.Timer(self.timer_t, self.commwdg)
        self.speed = 0.2
        self.at(at_config, "general:navdata_demo", "TRUE")
    
    def startVideo(self):
        self.videothread = Video.VideoThread()
        self.videothread.start()


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

class Controller(threading.Thread):    
    def __init__(self, drone, js):
        threading.Thread.__init__(self)
        self.drone = drone
        self.stopping = False
        self.js = js

    def convert(self, num):
        nump = num +1
        if nump > 0:
            return nump/2
        else:
            return nump
        


    def run(self):
        while not self.stopping:
            for e in pygame.event.get(): # iterate over event stack
		#print 'event : ' + str(e.type)
		if e.type == pygame.JOYAXISMOTION: 
                    roll = self.js.get_axis(0)
                    pitch = self.js.get_axis(1)
                    yaw = self.js.get_axis(3)
                    power2 = self.convert( self.js.get_axis(2) )
                    power1 = self.convert( self.js.get_axis(5) )
                    power = power1 - power2
                    self.drone.move(roll, pitch, power, yaw)
                    Utils.dprint( DEBUG, 'roll: ' + str(roll) + ' pitch: ' + str(pitch) + ' power: ' + str(power) + ' yaw: ' + str(yaw) )                   
                
                elif e.type == pygame.JOYBUTTONDOWN: # 10
                    
                    for b in range(self.js.get_numbuttons()):
                                                
                        if self.js.get_button(b) > 0:
                            #print 'number of button pushed: ' + str(b)
                            if b==0:
                                self.drone.stop()
                                self.stop()
                                break
                            elif b==1:
                                self.drone.reset() 
                            elif b==2:
                                self.drone.startVideo()
                            elif b==3:
                                self.drone.ledShow(6)
                            # elif b==4:
                            #     pass
                            # elif b==5:
                            #     pass
                            # elif b==6:
                            #     pass
                            # elif b==7:
                            #     pass
                            elif b==8:
                                if self.drone.getLanded():
                                    if self.drone.takeoff():
                                        self.drone.setLanded(False)
                                else:
                                    if self.drone.land():
                                        self.drone.setLanded(True)
                            # elif b==9:
                            #     pass
                            # elif b==10:
                            #     pass
                            elif b==11:
                                self.drone.rotate(-1)
                            elif b==12:
                                self.drone.rotate(1)
                            # elif b==13:
                            #     pass
                            # elif b==14:
                            #     pass
                         
                # elif e.type == pygame.JOYBUTTONUP: # 11
                #     for b in range(self.js.get_numbuttons()):
                #         bstate = self.js.get_button(b)
                        
                #         if bstate > 0:
                #             if b==0:
                #                 pass
                #             elif b==1:
                #                 pass
                #             elif b==2:
                #                 pass
                #             elif b==3:
                #                 pass
                #             elif b==4:
                #                 pass
                #             elif b==5:
                #                 pass
                #             elif b==6:
                #                 pass
                #             elif b==7:
                #                 pass
                #             elif b==8:
                #                 pass
                #                 #if self.drone.getLanded():
                #                 #    if self.drone.takeoff():
                #                 #        self.drone.setLanded(False)
                #                 #else:
                #                 #    if self.drone.land():
                #                 #        self.drone.setLanded(True)
                #             elif b==9:
                #                 pass
                #             elif b==10:
                #                 pass
                #             elif b==11:
                #                 self.drone.rotate(0)
                #             elif b==12:
                #                 self.drone.rotate(0)
                #             elif b==13:
                #                 pass
                #             elif b==14:
                #                 pass


    def stop(self):
        Utils.dprint(DEBUG, '4: stopping control thread')
        self.stopping = True


def main():
    pygame.init()
    pygame.joystick.init()

    if pygame.joystick.get_count() > 0:
        js = pygame.joystick.Joystick(0)
        js.init()
        print js.get_name()
    else:
        print 'No joystick available, exiting.'
        return False
    Utils.dprint(DEBUG, '1')
    drone = Drone()
    controller = Controller(drone, js)
    controller.start()
    
    controller.join()
    Utils.dprint(DEBUG, '2')
    #js.quit()
    pygame.joystick.quit()
    pygame.quit()
    Utils.dprint(DEBUG, '3')

if __name__ == '__main__':
    if 'profile' in sys.argv:
        cProfile.run('main()')
    else:
        main()
