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

import datetime
import time
import os
import sys
import threading
import socket
import multiprocessing
import select
import cv
import math
import TestDevice
import Utils
import decoder
import Queue
import pickle

from collections import OrderedDict
from copy import deepcopy

DEBUG = False

STOPPING = 0
INIT = 1
RUNNING = 2
PAUSED = 3
CAPTURE = 4

class VideoReceiver(multiprocessing.Process):

    def __init__(self, test, multicast):

        # Communication between parent and child process happens via a shared list 'comlist', the fields represents the following values:
        # comlist[0] : first data hold
        # comlist[1] : second data hold
        # comlist[2] : int describing the currently readable data hold
        # comlist[3] : int describing whether the process is running normally or shutting down

        manager = multiprocessing.Manager()
        self.comlist = manager.list(range(4))
        self.comlist[0] = None
        self.comlist[1] = None
        self.comlist[2] = 1
        self.comlist[3] = INIT
        multiprocessing.Process.__init__(self, target=self.runner, args=(self.comlist,))        
        self.fetches = 0
        self.MCAST = multicast       
        self.TEST = test
        self.capture = False
        self.capture_all = False
        self.videosamples = OrderedDict()
        self.targetVideoSample = None
        self.imagelist = []
        self.imagelist_all = []
        self.DRONE_IP = '192.168.1.1'
        self.INIT_PORT = 5555
        self.INITMSG = "\x01\x00\x00\x00"
        self.MCAST_GRP = '224.1.1.1'
        self.VIDEO_PORT = 5555
                            
        self.lock = multiprocessing.Lock()
        self.wakeup = 2500
       
        # Standard socket setup for unicast
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setblocking(0)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
       
        if self.TEST:
            self.DRONE_IP = '127.0.0.1'
            self.INIT_PORT = 5550

        # changing the socket setup to multicast
        if self.MCAST:
            self.INITMSG = "\x02\x00\x00\x00"
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32) 
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
            self.sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, socket.inet_aton('192.168.1.2'))
            self.sock.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(self.MCAST_GRP) + socket.inet_aton('192.168.1.2'))
        
        self.sock.bind(('', self.VIDEO_PORT))
        
    def initVideo(self):
        self.sock.sendto(self.INITMSG, (self.DRONE_IP, self.INIT_PORT))
        self.sock.sendto(self.INITMSG, (self.DRONE_IP, self.INIT_PORT))
        self.sock.sendto(self.INITMSG, (self.DRONE_IP, self.INIT_PORT))
        Utils.dprint(DEBUG, 'initing')

    def stop(self):
        self.comlist[3] = STOPPING 
        self.join()
        self.sock.close()    
        if self.capture:
            fileObj = open("./pickled.data", "a")
            pickle.dump(self.imagelist, fileObj)
            fileObj.close()

    def recordVideoSample(self):
        time = datetime.datetime.now()
        print 'VIDEO sample recorded at: ', time, "\r"
        ind = self.comlist[2]
        w, h, img, ti = decoder.read_picture(self.comlist[ind])
        gray  = cv.CreateImage ((320, 240), cv.IPL_DEPTH_8U, 1)
        canny = cv.CreateImage ((320, 240), cv.IPL_DEPTH_8U, 1)
        cv.CvtColor(img, gray,cv.CV_BGR2GRAY)
        cv.Canny(gray, canny, 10, 15)
        
        li = cv.HoughLines2(canny,
                            cv.CreateMemStorage(),
                            cv.CV_HOUGH_STANDARD,
                            1,
                            math.pi/180,
                            100,
                            0,
                            0)
              
        p = {}
        coords =  []
        for (rho,theta) in li:
           
            if theta < 0.04:
                #print theta
                c = math.cos(theta)
                s = math.sin(theta)
                x0 = c*rho
                y0 = s*rho
                cv.Line(img,
                        ( int(x0 + 1000*(-s)) , int(y0 + 1000*c) ),
                        (int(x0 + -1000*(-s)), int( y0 - 1000*c)),
                        (0,0,255))
                index = int(min([int(x0 + 1000*(-s)), int(x0 + -1000*(-s))]) + (abs((x0 + 1000*(-s)) - (x0 + -1000*(-s))) / 2))
                p[index] = 1
                coords.append( ( (int(x0 + 1000*(-s)) , int(y0 + 1000*c)) , (int(x0 + -1000*(-s)), int( y0 - 1000*c)) ) )
              
        self.videosamples[time] = (p, coords) 
        return (p, coords, img)

    def getImage(self):
        #self.fetches += 1
        #print "fetches: ", self.fetches
        index = self.comlist[2]
        image = self.comlist[index]
        if self.capture and image:
            self.captureImage(self.imagelist)
       
        if image:
            w, h, img, ti = decoder.read_picture(self.comlist[index])
            return img
        else:
            return None

    def captureImage(self, ilist):
        index = self.comlist[2]
        image = self.comlist[index]
        print "cap\r"
        if image:
            print "appending\r"
            ilist.append(deepcopy(image))

    def toggleCapture(self):
        print "toggleCapture\r"
        print len(self.imagelist), "\r"
        if self.capture:
            fileObj = open("./pickled.data", "a")
            pickle.dump(self.imagelist, fileObj)
            fileObj.close()

        self.capture = not self.capture
       
    def toggleCaptureAll(self):
        print "toggleCaptureAll\r"
        if self.capture_all:
            self.comlist[3] = RUNNING
        else:
            self.comlist[3] = CAPTURE
        
        self.capture_all = not self.capture_all

    def getVideoSamples(self):
        return self.videosamples

    def setTargetVideoSample(self):
        print "Setting target video print\r"
        vs = self.recordVideoSample()
        self.targetVideoSample = vs

    def getTargetVideoSample(self):
        return self.targetVideoSample

    def getStatus(self):
        return self.comlist[3]

    def setStatus(self, arg):
        self.comlist[3] = arg


    def runner(self, l):
        Utils.dprint(True, 'Starting video receiver\r')
        currentbuffer = 0        
        runs = 0
        time_start = datetime.datetime.now()
        imagelist_all = []
        self.initVideo()
        self.setStatus(RUNNING)
        while l[3]:

            inputready, outputready, exceptready = select.select([self.sock], [], [], 1)
            
            if len(inputready) == 0:
                self.initVideo()
        
            for i in inputready:
                
                if i == self.sock:
                    try:
                        data, addr = self.sock.recvfrom( 65535 )
                    except socket.error, e:
                        Utils.dprint(DEBUG,  e)
            
                    if data:
                        Utils.dprint(DEBUG, 'Got video data')
                        l[2] = (runs+1)%2
                        l[currentbuffer] = data
                        runs += 1
                        currentbuffer = runs%2
                        if l[3] == CAPTURE:
                            imagelist_all.append(data)

            if runs % 50 == 0:
                self.initVideo()
        
        if len(imagelist_all):
            fileObj = open("./pickled_video.data", "w")
            pickle.dump(imagelist_all, fileObj)
            fileObj.close()
            print "pickling data\r"

        time_end = datetime.datetime.now()
        delta = (time_end - time_start)
        time_elapsed = (delta.microseconds + (delta.seconds*1000000.0))/1000000.0
        print "Shutting down video receiver\t\t (" + str(runs),"frames fetched in",time_elapsed,"secs)\r"
      
def main():
    r = VideoReceiver(True, False)
    r.start()

    sp = multiprocessing.Process(target=showVideo, args=(r,))
    sp.start()

    input = Utils.getChar()
    r.stop() # kill process
    r.join()
    sp.join()

def showVideo(r):
    cv.NamedWindow('test')
    time.sleep(0.1)
    while r.getStatus():
        cv.ShowImage('test', r.getImage())
        cv.WaitKey(1)
    cv.DestroyWindow('test')


if __name__ == '__main__':
    main()
