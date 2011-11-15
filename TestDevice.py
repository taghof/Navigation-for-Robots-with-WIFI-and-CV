#!/usr/bin/env python2.7

import socket
import Utils
import time
import threading
import os

INIT_PORT = 5550
SEND_PORT = 5555
DEBUG = False

class TestDevice(threading.Thread):
    
    def __init__(self):
        threading.Thread.__init__(self)
        self.packets = []
        self.stopping = False
        self.timeout = 500
        self.i = 1
        
        while os.path.isfile('./testdata/' + str(self.i) + '.dat'):
            self.packets.append('./testdata/' + str(self.i) + '.dat')
            self.i += 1
        
        self.init_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.init_sock.bind(('', INIT_PORT))
        
        self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
    def run(self):
        print 'TestDevice waiting for incoming connection.'
        self.initpck, self.addr = self.init_sock.recvfrom(65535)
        self.init_sock.setblocking(0)
        print 'TestDevice connected, beginning transmission.'
        Utils.dprint(DEBUG, 'received: ' + str(self.initpck))
        
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
            
            f = open(self.packets[i % (self.i-1)], 'r')
            self.send_sock.sendto(f.read(), ('127.0.0.1', SEND_PORT))
            f.close()
            i += 1
            self.timeout -= 1
            time.sleep(0.1)

        print 'TestDevice stopping transmission'

    def stop(self):
        self.stopping = True
       
if __name__ == '__main__':
    dev = TestDevice()
    dev.start()
