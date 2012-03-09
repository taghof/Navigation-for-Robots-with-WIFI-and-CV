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
        self.comlist[3] = INIT
        multiprocessing.Process.__init__(self, target=self.runner, args=(self.comlist,))        
        
        self.MCAST = multicast       
        self.TEST = test
        self.capture_all = False
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
        self.comlist[3] = STOPPING 
        self.join()
        self.sock.close()    

    def getNavdata(self):
        index = self.comlist[2]
        navdata = self.comlist[index] if self.getStatus() else None
        if navdata:
            nd = decoder.decode_navdata(navdata)
            return nd
        else:
            return None

    
    def toggleCaptureAll(self):
        print "toggleCaptureAll\r"
        if self.capture_all:
            self.comlist[3] = RUNNING
        else:
            self.comlist[3] = CAPTURE
        
        self.capture_all = not self.capture_all

    def recordNavdataSample(self):
        time = datetime.datetime.now()
        print 'Navdata sample recorded at: ', time, "\r"
        ind = self.comlist[2]
        navdata = decoder.read_navdata(self.comlist[ind])
        self.navdatasamples[time] = navdata 
        return (time, navdata)

    def getNavdataSamples(self):
        return self.navsamples

    def setTargetNavdataSample(self):
        print "Setting target navdata print\r"
        nds = self.recordNavdataSample()
        self.targetNavdataSample = nds

    def getTargetNavdataSample(self):
        return self.targetNavdataSample

    def getStatus(self):
        return self.comlist[3]

    def setStatus(self, arg):
        self.comlist[3] = arg

    def runner(self, l):

        Utils.dprint(True, 'Starting navdata receiver\r')
        currentbuffer = 0        
        runs = 0
        navdatalist_all = []
        time_start = datetime.datetime.now()
        
        self.initNavdata()
        self.setStatus(RUNNING)
        
        while l[3]:

            inputready, outputready, exceptready = select.select([self.sock], [], [], 1)
           
            for i in inputready:
                
                if i == self.sock:
                    try:
                        data, addr = self.sock.recvfrom( 65535 )
                    except socket.error, e:
                        Utils.dprint(DEBUG,  e)
            
                    if data:
                        Utils.dprint(DEBUG, 'Got navdata')
                        l[2] = (runs+1)%2
                        l[currentbuffer] = data
                        runs += 1
                        currentbuffer = runs%2
                        navdatalist_all.append(data)
            if runs % 50 == 0:
                self.initNavdata()

        if len(navdatalist_all):
            ofile = open("./pickled_navdata.data", "w")
            pickle.dump(navdatalist_all, ofile)
            ofile.close()


        time_end = datetime.datetime.now()
        delta = (time_end - time_start)
        time_elapsed = (delta.microseconds + (delta.seconds*1000000.0))/1000000.0
        
        print "Shutting down navdata receiver\t\t (" + str(runs),"frames fetched in",time_elapsed,"secs)\r"

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
