#!/usr/bin/env python2.7

import socket
import Utils
import time
import threading
import os
import random

INIT_PORT = 5550
VIDEO_SEND_PORT = 5555
WIFI_SEND_PORT = 5551

DEBUG = False

class TestDevice(threading.Thread):
    
    def __init__(self, runalone):
        threading.Thread.__init__(self)
        self.run_alone = runalone
        self.packets = []
        self.stopping = False
        self.timeout = 100
        self.i = 1
        
        while os.path.isfile('../testdata/' + str(self.i) + '.dat'):
            self.packets.append('../testdata/' + str(self.i) + '.dat')
            self.i += 1
        
        self.init_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.init_sock.bind(('', INIT_PORT))
        
        self.video_send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.wifi_send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def run(self):
        if not self.run_alone:
            print 'TestDevice waiting for incoming connection.'
            self.initpck, self.addr = self.init_sock.recvfrom(65535)
            
            print 'TestDevice connected, beginning transmission.'
            Utils.dprint(DEBUG, 'received: ' + str(self.initpck))
        
        self.init_sock.setblocking(0)
        i = 0
        while self.timeout and not self.stopping:
            data = 0
            try:
                data, addr = self.init_sock.recvfrom(65535)
            except socket.error, e:
                Utils.dprint(DEBUG,  e)
            
            if data:
                Utils.dprint(DEBUG, data)
                Utils.dprint(DEBUG, 'TestDevice resetting shutdown timer')
                self.timeout = 500
            
            # transmit video data
            f = open(self.packets[i % (self.i-1)], 'r')
            self.video_send_sock.sendto(f.read(), ('127.0.0.1', VIDEO_SEND_PORT))
            f.close()
            
            # transmit WIFI data
            wifidata = "00:10:20:30:40:" + str(random.randint(10,16)) +" # " + str(random.randint(-75, 0))          
            self.video_send_sock.sendto(wifidata, ('127.0.0.1', WIFI_SEND_PORT))

            i += 1
            self.timeout -= 1
            time.sleep(0.1)

        print 'TestDevice stopping transmission'

    def stop(self):
        print 'TestDevice kindly asked to stop...'
        self.stopping = True
       
if __name__ == '__main__':
    dev = TestDevice(True)
    dev.start()
