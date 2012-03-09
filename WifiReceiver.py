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
import random
import pickle
from collections import OrderedDict
from copy import deepcopy

DEBUG = False

STOPPING = 0
INIT = 1
RUNNING = 2
PAUSED = 3
CAPTURE = 4

class WifiReceiver(multiprocessing.Process):
    
    def __init__(self):
        
        manager = multiprocessing.Manager()
        self.comlist = manager.list(range(4))
        self.comlist[0] = None
        self.comlist[1] = None
        self.comlist[2] = 0
        self.comlist[3] = INIT

        multiprocessing.Process.__init__(self, target=self.runner, args=(self.comlist,))        
        
        self.DRONE_IP = '192.168.1.1'
        self.WIFI_PORT = 5551
        self.capture_all = False
        self.lock = multiprocessing.Lock()
        self.wifisamples = OrderedDict()
        self.targetWifiSample = None
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setblocking(0)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('', self.WIFI_PORT))
            
    def stop(self):
        self.comlist[3] = STOPPING 
        self.join()
        self.sock.close()    

    def getWifiSignals(self):
        index = self.comlist[2]
        return self.comlist[index]

    def toggleCaptureAll(self):
        print "toggleCaptureAll\r"
        if self.capture_all:
            self.comlist[3] = RUNNING
        else:
            self.comlist[3] = CAPTURE
        
        self.capture_all = not self.capture_all


    def recordWifiSample(self):
        time = datetime.datetime.now()
        wifisample = deepcopy(self.getWifiSignals())
        self.wifisamples[time] = wifisample
        print 'WIFI sample recorded at: ', time, "\r"
        return wifisample

    def getWifiSamples(self):
        return self.wifisamples # should this be deepcloned?

    def startPeriodicWifiRecording(self, duration, repetitions):
        print "starting periodic wifi recording\r"
        t = PeriodicTimer(duration, repetitions, self.recordWifiSample)
        t.start()

    def startPeriodicWifiMatching(self, duration, repetitions):
        pass

    def setTargetWifiSample(self):
        print "Setting target wifi sample\r"
        self.targetWifiSample = self.recordWifiSample()

    def getTargetWifiSample(self):
        return self.targetWifiSample

    def matchCurrentWifiSample(self):
        if self.targetWifiSample == None:
            print "Can't match, target sample not set\r"
            return 0
        else:
            res = self.matchWifiSample(3, self.targetWifiSample, self.getWifiSignals())
            print "match score: ", res, "%\r"
            return res

    def matchWifiSample(self, min_match_len, p1, p2):
        match_set = OrderedDict()
        threshold = 20
        current_time = datetime.datetime.now()
        for key, val in p2.iteritems():
            signal_time_stamp = val[1]
            time_difference = (current_time - signal_time_stamp).total_seconds()
            if p1.has_key(key):
                if 0 < time_difference < threshold :
                    significance = (threshold-time_difference) / threshold
                    match_set[key] = (val[0], significance)
                elif time_difference > threshold:
                    significance = 0
                    match_set[key] = (val[0], significance)
                else:
                    significance = 1
                    match_set[key] = (val[0], significance)
        mval = 0
        maxmval = 0
        for k, v in match_set.iteritems():
            dif = abs((v[0]+100)-(p1.get(k)[0]+100))
            mval += (v[0]+100)*v[1] - dif
            maxmval += (p1.get(k)[0]+100)

        print "mval: ", mval, "maxmval: ", maxmval, "\r"
        pval = (mval / maxmval) * 100
        
        return pval

    def getStatus(self):
        return self.comlist[3]

    def setStatus(self, arg):
        self.comlist[3] = arg

    def runner(self, l):
        Utils.dprint(True, 'Starting wifi receiver\r')
        wifimap = OrderedDict()
        currentbuffer = 0        
        l[currentbuffer] = wifimap
        runs = 0
        wifilist_all = []
        time_start = datetime.datetime.now()
        self.setStatus(RUNNING)
        while l[3]:

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
                        if wifimap.has_key(keyval[0]) and int(wifimap[keyval[0]][0]) - int(keyval[1]) > 40:
                            #print "**filtered** src: ", keyval[0], "  old: ", int(keyval[1]), " old: ",(wifimap[keyval[0]][0]), "\r" 
                            pass
                        else:
                            wifimap[keyval[0]] = (int(keyval[1]), datetime.datetime.now())
                            if l[3] == CAPTURE:
                                wifilist_all.append(data)

                        l[currentbuffer] = wifimap
                        runs += 1

        if len(wifilist_all):
            ofile = open("./pickled_wifi.data", "w")
            pickle.dump(wifilist_all, ofile)
            ofile.close()

        time_end = datetime.datetime.now()
        delta = (time_end - time_start)
        time_elapsed = (delta.microseconds + (delta.seconds*1000000.0))/1000000.0
        print 'Shutting down wifireceiver\t\t (' + str(runs), 'packets fetched in', time_elapsed, 'secs)\r'


class PeriodicTimer(threading.Thread):
    
    def __init__(self, duration, repetitions, function):
        threading.Thread.__init__(self)
        self.duration = duration
        self.repetitions = repetitions
        self.function = function

    def run(self):
        while self.repetitions > 0:
            time.sleep(self.duration)
            self.function()
            self.repetitions -= 1
