#!/usr/bin/env python2.7

import datetime
import time
import os
import sys
import threading
import socket
#import numpy
import multiprocessing
import select
import cv
import math
import TestDevice
import Utils
import decoder
import Queue

DEBUG = False

INIT = 0
STARTED = 1
PAUSED = 2
STOPPING = 3

NORMAL = 4
PRINT = 5

class Receiver(multiprocessing.Process):

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
        # self.RECORD = record
        self.TEST = test
      
        self.DRONE_IP = '192.168.1.1'
        self.INIT_PORT = 5555
        self.INITMSG = "\x01\x00\x00\x00"
        self.MCAST_GRP = '224.1.1.1'
        self.VIDEO_PORT = 5555
                            
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
            self.testdevice = TestDevice.TestDevice(False)
            self.testdevice.start()
            while not self.testdevice.isAlive():
                pass # waiting for testdevice to start

        # TODO: move the recording functionality to suited class
        # if self.RECORD:
        #     Utils.ensure_dir('./testdata')
        #     fps = 12
        #     width, height = int(320), int(240)
        #     fourcc = cv.CV_FOURCC('I','4','2','0')
        #     self.writer = cv.CreateVideoWriter('out.avi', fourcc, fps, (width, height), 1)

        if self.MCAST:
            # changing the socket setup to multicast
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
        self.state = STOPPING
        if self.TEST:
            self.testdevice.stop()
            self.testdevice.join()
        self.comlist[3] = 0 
        time.sleep(1)
        print 'rstop'
        self.sock.close()    

    def getImage(self):
        index = self.comlist[2]
        w, h, img, ti = decoder.read_picture(self.comlist[index])
        return img

    def getStatus(self):
        return self.comlist[3]

    def runner(self, l):
        currentbuffer = 0        
        runs = 0
        state = STARTED
        mode = NORMAL
        time_start = datetime.datetime.now()
        
        self.initVideo()
        while l[3]:
            Utils.dprint(DEBUG, 'Video started')
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
        
        
        time_end = datetime.datetime.now()
        delta = (time_end - time_start)
        time_elapsed = (delta.microseconds + (delta.seconds*1000000.0))/1000000.0
        
        print
        print 'frames:\t', runs
        print 'avg time:\t', time_elapsed / runs, 'sec'
        print 'avg fps:\t', runs / time_elapsed, 'fps'

def main():
    r = Receiver(True, False)
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
