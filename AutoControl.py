#!/usr/bin/env python2.7

import sys
import pygame
import threading
import Utils
import Drone
import cv
import time

DEBUG = False

class AutoControl(threading.Thread):    

    def __init__(self, controller, sensor):
        threading.Thread.__init__(self)
        self.lock = threading.Lock()
        self.controller = controller
        self.stopping = False
        self.video = False
        self.sensor = sensor
        self.videoruns = 0
        self.imagesretrieved = 0

    def run(self):
        while not self.stopping:
            cv.WaitKey(1)
            img = self.sensor.getImage()
            self.imagesretrieved += 1
            self.lock.acquire()
            if self.video:
                cv.ShowImage('test', self.sensor.getImage())
                cv.WaitKey(1)
                self.videoruns += 1
            self.lock.release()

    def stop(self):
        Utils.dprint(DEBUG, '4: Stopping AutoControl thread')
        if self.video:
            self.hideVideo()
        print 'frames showed: ' + str(self.videoruns)
        print 'frames retrieved: ' + str(self.imagesretrieved)
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

    def recordFingerPrint():
        # p = self.videothread.getVerticalPrint()
        # self.videothread.setCurrentTarget(p)
        # for x in range(len(p)):
        #     if p[x] == 1:
        #         print x
        pass
