#!/usr/bin/env python2.7

import threading
import decoder
import socket
import Utils
import time
import os
import sys
import numpy
import cv
import TestDevice

#MCAST = False
#MCAST_GRP = '224.1.1.1' 
#DRONE_IP = '192.168.1.1'
#DRONE_IP = '127.0.0.1'
#VIDEO_PORT = 5555
#VIDEO_PORT = 5555
#INIT_PORT = 5550
DEBUG = False
#RECORD = False

class VideoThread(threading.Thread):

    def __init__(self, test, record, multicast):
        threading.Thread.__init__(self)
        self.lock = threading.Lock()

        if test:
            self.DRONE_IP = '127.0.0.1'
            self.INIT_PORT = 5550
            self.testdevice = TestDevice.TestDevice()
            self.testdevice.start()
        else:
            self.DRONE_IP = '192.168.1.1'
            self.INIT_PORT = 5555

        self.MCAST = multicast
        self.MCAST_GRP = '224.1.1.1'
        self.VIDEO_PORT = 5555
        self.RECORD = record
        self.window = "OpenCV window"

        cv.NamedWindow(self.window)
        cv.StartWindowThread()
        
        self.stopping = False 
        self.t = 0
        self.runs = 0
        self.wakeup = 100
        self.initVideo(self.MCAST)
        
        if self.RECORD:
            ensure_dir('./testdata')
            fps = 12
            width, height = int(320), int(240)
            fourcc = cv.CV_FOURCC('I','4','2','0')
            self.writer = cv.CreateVideoWriter('out.avi', fourcc, fps, (width, height), 1)

        if not self.MCAST:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setblocking(0)
            #self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            Utils.dprint(DEBUG, 'binding to:' + str(self.VIDEO_PORT))
            self.sock.bind(('', self.VIDEO_PORT))
                        
        else:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self.sock.setblocking(0)
            try:
                self.sock.seckopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except AttributeError:
                pass

            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32) 
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
            
            self.sock.bind(('', self.VIDEO_PORT))
            host = '192.168.1.2' 
            self.sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, socket.inet_aton(host))
            self.sock.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP, 
                            socket.inet_aton(self.MCAST_GRP) + socket.inet_aton(host))
    
    
    def initVideo(self, i):
        init_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        init_sock.setblocking(0)
        init_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        init_sock.bind(('', self.VIDEO_PORT))
        if i:
            init_sock.sendto("\x02\x00\x00\x00", (self.DRONE_IP, self.INIT_PORT))
        else:
            init_sock.sendto("\x01\x00\x00\x00", (self.DRONE_IP, self.INIT_PORT))

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
                    if self.MCAST:
                        self.sock.sendto("\x02\x00\x00\x00", (self.DRONE_IP, self.INIT_PORT))
                    else:
                        self.sock.sendto("\x01\x00\x00\x00", (self.DRONE_IP, self.INIT_PORT))
            else:
                Utils.dprint(DEBUG, 'not receiving video data')
    
            time.sleep(0.01)
    


    def stop(self):
        self.stopping = True
        self.testdevice.stop()
        self.testdevice.join()
        if self.t:
            print
            print 'avg time:\t', self.t / self.runs, 'sec'
            print 'avg fps:\t', 1 / (self.t / self.runs), 'fps'
        self.sock.close()    

      
    def updateScreen(self, data):
        w, h, img, ti = decoder.read_picture(data)
        
        if self.runs == 1 :
            pass
            # stuff to do with 1st frame only
        
        resized = cv.CreateMat(620, 960, cv.CV_8UC3)
        cv.Resize(img, resized)
        cv.ShowImage(self.window, resized);
                
        if self.RECORD:
            f = open('./testdata/' + str(self.runs) + '.dat', 'w')
            f.write(data)
            f.close()
            cv.WriteFrame(self.writer, img)

        return ti

def ensure_dir(f):
    d = os.path.dirname(f)
    if not os.path.exists(d):
        os.makedirs(d)

if __name__ == '__main__':

    vt = VideoThread(True, False, False)
    vt.start()
    s = raw_input('Push any key to stop video...')
    vt.stop()
