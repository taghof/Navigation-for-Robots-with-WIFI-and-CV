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
import random
from collections import OrderedDict
from copy import deepcopy

DEBUG = False

INIT = 0
STARTED = 1
PAUSED = 2
STOPPING = 3

NORMAL = 4
PRINT = 5

class WifiReceiver(multiprocessing.Process):
    
    def __init__(self):
        
        manager = multiprocessing.Manager()
        self.comlist = manager.list(range(4))
        self.comlist[0] = None
        self.comlist[1] = None
        self.comlist[2] = 0
        self.comlist[3] = 1

        multiprocessing.Process.__init__(self, target=self.runner, args=(self.comlist,))        
        
        self.DRONE_IP = '192.168.1.1'
        self.WIFI_PORT = 5551
                            
        self.lock = multiprocessing.Lock()
        self.state = INIT 
        self.wifiprints = OrderedDict()
    
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setblocking(0)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('', self.WIFI_PORT))
            
    def stop(self):
        self.state = STOPPING
        self.comlist[3] = 0 
        time.sleep(1)
        print 'rwstop'
        self.sock.close()    

    def getWifiSignals(self):
        index = self.comlist[2]
        return self.comlist[index]

    def recordWifiPrint(self):
        time = datetime.datetime.now()
        wifiprint = deepclone(getWifiSignals())
        self.wifiprints[time] = wifiprint
        print 'WIFI print recorded at: ', time
        
    def getWifiPrints(self):
        return self.wifiprints # should this be deepcloned?

    def getStatus(self):
        return self.comlist[3]

    def runner(self, l):
        wifimap = OrderedDict()
        currentbuffer = 0        
        l[currentbuffer] = wifimap
        runs = 0
        state = STARTED
        mode = NORMAL
        time_start = datetime.datetime.now()
                
        while l[3]:
            Utils.dprint(DEBUG, 'Wifisignal receiver started')
            inputready, outputready, exceptready = select.select([self.sock], [], [], 1)
            for i in inputready:
                
                if i == self.sock:
                    try:
                        data, addr = self.sock.recvfrom(100)
                    except socket.error, e:
                        Utils.dprint(DEBUG,  e)
            
                    if data:
                        Utils.dprint(DEBUG, 'Got WIFI data')
                        keyval = data.split('#')
                        # filter reflected packages
                        if wifimap.has_key(keyval[0]) and int(wifimap[keyval[0]]) - int(keyval[1]) > 15:
                            pass
                        else:
                            wifimap[keyval[0]] = int(keyval[1])
                        
                        l[currentbuffer] = wifimap
                        runs += 1
                               
        time_end = datetime.datetime.now()
        delta = (time_end - time_start)
        time_elapsed = (delta.microseconds + (delta.seconds*1000000.0))/1000000.0
        
        print 'ran for:\t', time_elapsed, ' secs'
