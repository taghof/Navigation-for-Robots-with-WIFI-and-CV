#!/usr/bin/env python2.7

import Utils
import os
import sys
import numpy
import cv
import time
import threading


class FunnyThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.stopping = False

    def run(self):
        while not self.stopping:
            print 'Derp'
            time.sleep(2)

    def stop(self):
        self.stopping = True
    

class ImageVideoThread(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        self.c = 0
        self.stopping = False
      
        
    def run(self):
        img = cv.LoadImage('./lena.png', cv.CV_LOAD_IMAGE_COLOR)
        cv.ShowImage('test', img)
        cv.SetMouseCallback('test', callBack, None)
        while not self.stopping:
            self.c += 1
            #print 'loading and showing'
            img = cv.LoadImage('./lena.png', cv.CV_LOAD_IMAGE_COLOR)
            if img:
                cv.ShowImage('test', img)
                cv.WaitKey(1)
            else:
                print 'Derp'

    def stop(self):
        self.stopping = True

def callBack(event, x, y, flags, param):
    print event
        


def main():
    #cv.StartWindowThread()
    #cv.NamedWindow('test', cv.CV_WINDOW_AUTOSIZE)
    img = cv.LoadImage('./lena.png', cv.CV_LOAD_IMAGE_COLOR)
    #cv.ShowImage('test', img)
   
    t = ImageVideoThread()
    f = FunnyThread()
    t.start()
    f.start()
    cv.WaitKey()
    t.stop()
    f.stop()
    
    
if __name__ == '__main__':
    main()
