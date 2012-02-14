#!/usr/bin/env python2.7
import math
import sys
import pygame

import threading
import Utils
import Drone
import cv
import time
import random
import WifiReceiver
from collections import OrderedDict

DEBUG = False

class Presenter(threading.Thread):    

    def __init__(self, controller, videosensor, wifisensor):
        threading.Thread.__init__(self)
        self.lock = threading.Lock()
        self.controller = controller
        self.stopping = False

        self.video = False
        self.videosensor = videosensor
        self.videoupdates = 0

        self.wifi = False
        self.wifisensor = wifisensor
        self.wifiscreen = None
        self.wifiupdates = 0
        self.wifimap_old = None
        self.wifimap_current = None

        #self.imagesretrieved = 0

    def run(self):
        Utils.dprint(DEBUG, 'Presenter thread started')
        while not self.stopping:
            cv.WaitKey(1)
            #img = self.sensor.getImage()
            #self.imagesretrieved += 1
            self.lock.acquire()
            if self.video:
                cv.ShowImage('test', self.videosensor.getImage())
                cv.WaitKey(1)
                self.videoupdates += 1
        
            if self.wifi:
                self.updateWifi(self.wifiscreen)
                self.wifiupdates += 1

            if not self.wifi and not self.video:
                pass
    
            self.lock.release()
            
    def stop(self):
        Utils.dprint(DEBUG, '4: Stopping Presenter thread')
        if self.video:
            self.hideVideo()
        print 'video frames showed: ' + str(self.videoupdates)
        print 'wifi sets showed: ' + str(self.wifiupdates)
        self.stopping = True

    def hideVideo(self):
        self.lock.acquire()
        self.video = False
        cv.DestroyAllWindows()
        self.lock.release()

    def showVideo(self):
        self.lock.acquire()
        cv.NamedWindow('test')
        self.video = True
        self.lock.release()

    def hideWifi(self):
        self.lock.acquire()
        self.wifi = false
        pygame.quit()
        self.lock.release()

    def getRanNum(self):
        return random.randint(-5, 5)

    def updateWifi(self, screen):
        self.wifimap_old = self.wifimap_current
        self.wifimap_current = self.wifisensor.getWifiSignals()       
        if len(self.wifimap_current) > 0:
            screen.fill((0,0,0))
            len_of_rows = 10
            num_of_sources = len(self.wifimap_current)
            num_of_rows = math.ceil(float(num_of_sources)/float(len_of_rows))
            x_margin = 25
            y_margin = 25
            internal_margin = 10
            x_available = 590
            y_available = 430
            current_x = x_margin
            current_y = y_margin
        
            row_height = y_available/num_of_rows
            fig_height = row_height - 20
            fig_width = (x_available -((len_of_rows-1)*internal_margin))/len_of_rows
            index = 0

            font = pygame.font.SysFont("Times New Roman",8)
            for k, v in self.wifimap_current.iteritems():
                if self.wifimap_old and self.wifimap_old.has_key(k) and self.wifimap_old[k] - v > 15:
                    v = self.wifimap_old[k]
                    self.wifimap_current[k] = self.wifimap_old[k]
                    #print 'old: ', self.wifimap_old[k], ' new: ', self.wifimap_current[k], 'v: ',v , '\r'
                                     
                figval = int((75+v)*(float(fig_height)/float(75)))
                colors = (255-((75+v)*(float(255)/float(75))),(75+v)*(float(255)/float(75)), 0)
                fig1 = pygame.draw.rect(screen, (255,255,255),(current_x, current_y, fig_width, fig_height), 1)
                fig2 = pygame.draw.rect(screen, colors, (current_x+1, current_y+(fig_height-figval), fig_width-2, figval-1), 1) 
                screen.fill(colors, fig2)

                label = font.render(k,True,(0,255,255))
                screen.blit(label, (current_x, current_y+fig_height+3+((index%3)*7)))

                index+=1
                current_x += (internal_margin + fig_width)
                if(index == len_of_rows):
                    current_x = x_margin
                    current_y += row_height
                    index = 0;

            pygame.display.update()

    def showWifi(self):
        self.lock.acquire()
        self.wifiscreen = pygame.display.set_mode((640,480))
        self.updateWifi(self.wifiscreen)
        self.wifi = True
        self.lock.release()

    def recordFingerPrint():
        # p = self.videothread.getVerticalPrint()
        # self.videothread.setCurrentTarget(p)
        # for x in range(len(p)):
        #     if p[x] == 1:
        #         print x
        pass

def main():

    wifisensor = WifiReceiver.WifiReceiver(True)
    wifisensor.start()
    r = Presenter(None, None, wifisensor)
    r.start()
    r.showWifi()
    input = Utils.getChar()
    wifisensor.stop()
    wifisensor.join()
    r.stop() # kill process
    r.join()

if __name__ == '__main__':
    main()
