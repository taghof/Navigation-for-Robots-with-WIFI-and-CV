#!/usr/bin/env python2.7

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
from collections import OrderedDict
from copy import deepcopy

DEBUG = False

INIT = 0
STARTED = 1
PAUSED = 2
STOPPING = 3

NORMAL = 4
PRINT = 5

class NavdataReceiver(multiprocessing.Process):

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
        self.comlist[3] = 1
        multiprocessing.Process.__init__(self, target=self.runner, args=(self.comlist,))        
        
        self.MCAST = multicast       
        self.TEST = test
      
        self.navdatasamples = OrderedDict()
        self.targetNavdataSample = None

        self.DRONE_IP = '192.168.1.1'
        self.INIT_PORT = 5554
        self.INITMSG = "\x01\x00\x00\x00"
        self.MCAST_GRP = '224.1.1.1'
        self.NAVDATA_PORT = 5554
                            
        self.lock = multiprocessing.Lock()
        self.state = INIT 
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
        
        self.sock.bind(('', self.NAVDATA_PORT))
        
    def initNavdata(self):
        self.sock.sendto(self.INITMSG, (self.DRONE_IP, self.INIT_PORT))
        self.sock.sendto(self.INITMSG, (self.DRONE_IP, self.INIT_PORT))
        self.sock.sendto(self.INITMSG, (self.DRONE_IP, self.INIT_PORT))
        Utils.dprint(DEBUG, 'initing')

    def stop(self):
        self.state = STOPPING
        self.comlist[3] = 0 
        time.sleep(1)
        self.sock.close()    

    def getNavdata(self):
        index = self.comlist[2]
        navdata = decoder.decode_navdata(self.comlist[index])
        return navdata

    def recordNavdataSample(self):
        time = datetime.datetime.now()
        print 'Navdata sample recorded at: ', time, "\r"
        ind = self.comlist[2]
        navdata = decoder.read_navdata(self.comlist[ind])
        # gray  = cv.CreateImage ((320, 240), cv.IPL_DEPTH_8U, 1)
        # canny = cv.CreateImage ((320, 240), cv.IPL_DEPTH_8U, 1)
        # cv.CvtColor(img, gray,cv.CV_BGR2GRAY)
        # cv.Canny(gray, canny, 10, 15)
        
        # li = cv.HoughLines2(canny,
        #                     cv.CreateMemStorage(),
        #                     cv.CV_HOUGH_STANDARD,
        #                     1,
        #                     math.pi/180,
        #                     100,
        #                     0,
        #                     0)
              
        # p = {}
        # coords =  []
        # for (rho,theta) in li:
           
        #     if theta < 0.04:
        #         #print theta
        #         c = math.cos(theta)
        #         s = math.sin(theta)
        #         x0 = c*rho
        #         y0 = s*rho
        #         cv.Line(img,
        #                 ( int(x0 + 1000*(-s)) , int(y0 + 1000*c) ),
        #                 (int(x0 + -1000*(-s)), int( y0 - 1000*c)),
        #                 (0,0,255))
        #         index = int(min([int(x0 + 1000*(-s)), int(x0 + -1000*(-s))]) + (abs((x0 + 1000*(-s)) - (x0 + -1000*(-s))) / 2))
        #         p[index] = 1
        #         coords.append( ( (int(x0 + 1000*(-s)) , int(y0 + 1000*c)) , (int(x0 + -1000*(-s)), int( y0 - 1000*c)) ) )
              
        self.navdatasamples[time] = navdata 
        return (time, navdata)

    def getNavdataSamples(self):
        return self.videosamples


    def setTargetNavdataSample(self):
        print "Setting target navdata print\r"
        nds = self.recordNavdataSample()
        self.targetNavdataSample = nds

    def getTargetNavdataSample(self):
        return self.targetVideoSample

    def getStatus(self):
        return self.comlist[3]

    def runner(self, l):
        Utils.dprint(True, 'Starting navdata receiver\r')
        currentbuffer = 0        
        runs = 0
        state = STARTED
        mode = NORMAL
        time_start = datetime.datetime.now()
        
        self.initNavdata()
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
        
            if runs % 50 == 0:
                self.initNavdata()
        
        time_end = datetime.datetime.now()
        delta = (time_end - time_start)
        time_elapsed = (delta.microseconds + (delta.seconds*1000000.0))/1000000.0
      
        print "Shutting down navdata receiver\t\t (" + str(runs),"frames fetched in",time_elapsed,"secs)\r"
        #print 'frames:\t', runs
        #print 'avg time:\t', time_elapsed / runs, 'sec'
        #print 'avg fps:\t', runs / time_elapsed, 'fps'




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
