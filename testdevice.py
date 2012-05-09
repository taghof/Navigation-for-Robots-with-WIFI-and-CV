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

import os
import socket
import time
import threading
import random
import pickle

import utils
import decoder
import settings

class TestDevice(threading.Thread):
    
    def __init__(self, runalone):
        threading.Thread.__init__(self)
        self.run_alone = runalone
        self.video_packets = []
        self.wifi_packets = []
        self.navdata_packets = []
        self.stopping = False
        self.timeout = 10000
        self.vi = 1
        self.wi = 1
        self.ni = 1
        self.pickled_video = True
        self.pickled_wifi = True
        self.pickled_navdata = True

        print 'Loading Test Data:\r'
        
        # Determine whether we should use data from a pickled file or from the raw video packet files
        if not os.path.isfile('./testdata/pickled_5555.data'):
            self.pickled_video = False
            while os.path.isfile('./testdata/' + str(self.vi) + '.dat'):
                self.video_packets.append('./testdata/' + str(self.vi) + '.dat')
                self.vi += 1
            print "video frames:\t", self.vi
        else:
            fileObj = open('./testdata/pickled_5555.data')
            self.video_packets = pickle.load(fileObj)
            fileObj.close()
            self.vi = len(self.video_packets)
            print "video frames:\t", self.vi

        # Determine whether we should use data from a pickled file or nothing at all
        if not os.path.isfile('./testdata/pickled_5551.data'):
            self.pickled_wifi = False
        else:
            fileObj = open('./testdata/pickled_5551.data')
            self.wifi_packets = pickle.load(fileObj)
            fileObj.close()
            self.wi = len(self.wifi_packets)
            print "Wifi frames:\t", self.wi

        # Determine whether we should use data from a pickled file or nothing at all
        if not os.path.isfile('./testdata/pickled_5554.data'):
            self.pickled_wifi = False
        else:
            fileObj = open('./testdata/pickled_5554.data')
            self.navdata_packets = pickle.load(fileObj)
            fileObj.close()
            self.ni = len(self.navdata_packets)
            print "Navdata frames:\t", self.ni

        print "********************************"
        # initialise the init and sending sockets
        self.init_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.init_sock.bind(('', settings.TEST_DRONE_INIT_PORT))
        
        self.video_send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.wifi_send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.navdata_send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def run(self):
        if not self.run_alone:
            print 'Starting TestDevice (waiting for incoming connection)\r'
            self.initpck, self.addr = self.init_sock.recvfrom(65535)
            
            print 'TestDevice connected, beginning transmission\r'
            utils.dprint("", 'received: ' + str(self.initpck))
        
        self.init_sock.setblocking(0)
        
        vi = 0
        wi = 0
        ni = 0
        
        while self.timeout and not self.stopping:
            data = 0
            try:
                data, addr = self.init_sock.recvfrom(65535)
            except socket.error, e:
                utils.dprint("",  e)
            
            if data:
                utils.dprint("", data)
                utils.dprint("", 'TestDevice resetting shutdown timer')
                self.timeout = 500
            
            # transmit video data
            if self.pickled_video:
                data = self.video_packets[vi][1]
            else:
                f = open(self.video_packets[vi % (self.vi-1)], 'r')
                data = f.read()
                f.close()
                
            self.video_send_sock.sendto(data, ('127.0.0.1', settings.VIDEO_PORT))
            
            # transmit WIFI data
            if self.pickled_wifi:
                wifidata = self.wifi_packets[wi][1]
            else:
                wifidata = "00:10:20:30:40:" + str(random.randint(10,30)) +" # " + str(random.randint(-75, 0))           
            
            self.wifi_send_sock.sendto(wifidata, ('127.0.0.1', settings.WIFI_PORT))
            
            # transmit navdata
            if self.pickled_wifi:
                navdata = self.navdata_packets[ni][1]
                self.navdata_send_sock.sendto(navdata, ('127.0.0.1', settings.NAVDATA_PORT))
           
            vi += 1
            if vi == self.vi:
                vi = 0
            
            wi += 1
            if wi == self.wi:
                wi = 0
            
            ni += 1
            if ni == self.ni:
                ni = 0

            self.timeout -= 1
            time.sleep(0.4)

        print 'Shutting down TestDevice\r'

    def stop(self):
        self.stopping = True
       
if __name__ == '__main__':
    dev = TestDevice(True)
    dev.start()
