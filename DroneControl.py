#!/usr/bin/env python2.7

#import struct
import sys
import pygame
#import os
import threading
import Utils
import Drone

NAV_PORT = 5554
VIDEO_PORT = 5555
CMD_PORT = 5556

MULTICAST_IP = '224.1.1.1'
DRONE_IP = '192.168.1.1'
TEST_DRONE_IP = '127.0.0.1'
INTERFACE_IP = '192.168.1.2'

DEBUG = False

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
                    
                    for b in xrange(self.js.get_numbuttons()):
                                                
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
        print 'No joystick available, exiting... should default to keyboard mode'
        return False
    Utils.dprint(DEBUG, '1')
    drone = Drone.Drone(False)
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
