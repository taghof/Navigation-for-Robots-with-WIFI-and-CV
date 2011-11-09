#!/usr/bin/env python2.7

import threading
import pygame
import decoder
import socket
import Utils
import time
import os
import sys
from opencv.highgui import *
from opencv.cv import *
from opencv import *

RUNS = 10000
MCAST = True
MCAST_GRP = '224.1.1.1' 
VIDEO_PORT = 5555
DEBUG = False
RECORD = False

class VideoThread(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
            
        self.window = "win"
        cvNamedWindow(self.window)
        cvStartWindowThread()
        
        self.stopping = False 
        self.t = 0
        self.runs = 0
        self.wakeup = 100
        self.initVideo(MCAST)
        
        if RECORD:
            fps = 12
            width, height = int(320). int(240)
            fourcc = CV_FOURCC('I','4','2','0')
            self.writer = cvCreateVideoWriter('out.avi', fourcc, fps, (width, height), 1)

        if not MCAST:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setblocking(0)
            #self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(('', VIDEO_PORT))
                        
        else:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self.sock.setblocking(0)
            try:
                self.sock.seckopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except AttributeError:
                pass

            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32) 
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
            
            self.sock.bind(('', VIDEO_PORT))
            host = '192.168.1.2' 
            self.sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, socket.inet_aton(host))
            self.sock.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP, 
                            socket.inet_aton(MCAST_GRP) + socket.inet_aton(host))
    
    
    def initVideo(self, i):
        init_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        init_sock.setblocking(0)
        init_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        init_sock.bind(('', VIDEO_PORT))
        if i:
            init_sock.sendto("\x02\x00\x00\x00", ('192.168.1.1', VIDEO_PORT))
        else:
            init_sock.sendto("\x01\x00\x00\x00", ('192.168.1.1', VIDEO_PORT))

        init_sock.close()


    def run(self):
        
        data = 0
        while not self.stopping:
            
            try:
                data, addr = self.sock.recvfrom( 65535 )
            except socket.error, e:
                Utils.dprint(DEBUG,  e)
            if data:
                self.runs += 1
                self.t += self.updateScreen(data)
                if self.runs % self.wakeup == 0:
                    Utils.dprint(DEBUG, 'sending wakeup' )
                    if MCAST:
                        self.sock.sendto("\x02\x00\x00\x00", ('192.168.1.1', VIDEO_PORT))
                    else:
                        self.sock.sendto("\x01\x00\x00\x00", ('192.168.1.1', VIDEO_PORT))
            else:
                Utils.dprint(DEBUG, 'not receiving video data')
    
            time.sleep(0.01)
    


    def stop(self):
        self.stopping = True
        if self.t:
            print
            print 'avg time:\t', self.t / self.runs, 'sec'
            print 'avg fps:\t', 1 / (self.t / self.runs), 'fps'
        self.sock.close()    
        
    def updateScreen(self, data):
        w, h, img, ti = decoder.read_picture(data)

        cvShowImage(self.window, img);
        
        if RECORD:
            cvWriteFrame(self.writer, img)

        return ti
