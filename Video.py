2#!/usr/bin/env python2.7

import datetime
import time
import os
import sys
import threading
import socket
import numpy
import multiprocessing
import select
import cv

import TestDevice
import Utils
import decoder

DEBUG = False

INIT = 0
STARTED = 1
PAUSED = 2
STOPPING = 3

class VideoThread(multiprocessing.Process):

    def __init__(self, test, record, multicast):
        multiprocessing.Process.__init__(self)
               
        self.DRONE_IP = '192.168.1.1'
        self.INIT_PORT = 5555
        self.INITMSG = "\x01\x00\x00\x00"
        self.MCAST_GRP = '224.1.1.1'
        self.VIDEO_PORT = 5555
        
        self.window = "OpenCV window: " + str(datetime.datetime.now())
        
        self.com_pipe, self.com_pipe_other = multiprocessing.Pipe() 
        self.state = INIT 
        self.wakeup = 2500

        self.MCAST = multicast       
        self.RECORD = record
        self.TEST = test

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setblocking(0)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        #self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 200000)
        Utils.dprint(DEBUG, 'buffer:\t' + str(self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)))

        if self.TEST:
            self.DRONE_IP = '127.0.0.1'
            self.INIT_PORT = 5550
            self.testdevice = TestDevice.TestDevice(False)
            self.testdevice.start()
            while not self.testdevice.isAlive():
                pass

        if self.RECORD:
            Utils.ensure_dir('./testdata')
            fps = 12
            width, height = int(320), int(240)
            fourcc = cv.CV_FOURCC('I','4','2','0')
            self.writer = cv.CreateVideoWriter('out.avi', fourcc, fps, (width, height), 1)

        if self.MCAST:
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

    def run(self):
        
        cv.NamedWindow(self.window)
        #cv.SetMouseCallback(self.window, self.callBack, None)
        runs = 0
        state = STARTED
        time_start = datetime.datetime.now()
        
        self.initVideo()
        while not state == STOPPING:
            Utils.dprint(DEBUG, 'started')
            inputready, outputready, exceptready = select.select([self.sock, self.com_pipe], [], [], 1)
            
            if len(inputready) == 0:
                self.initVideo()
        
            for i in inputready:
                
                if i == self.sock:
                    try:
                        data, addr = self.sock.recvfrom( 65535 )
                    except socket.error, e:
                        Utils.dprint(DEBUG,  e)
            
                    if data:
                        runs += 1
                        self.updateScreen(data, runs)
                    else:
                        Utils.dprint(DEBUG, 'not receiving video data, though select said so...')
                
                elif i == self.com_pipe:
                    state = STOPPING

        time_end = datetime.datetime.now()
        delta = (time_end - time_start)
        time_elapsed = (delta.microseconds + (delta.seconds*1000000.0))/1000000.0
        
        cv.DestroyWindow(self.window)
        print
        print 'frames:\t', runs
        print 'avg time:\t', time_elapsed / runs, 'sec'
        print 'avg fps:\t', runs / time_elapsed, 'fps'
    
    def stop(self):
        self.state = STOPPING
        if self.TEST:
            self.testdevice.stop()
            self.testdevice.join()
        self.com_pipe_other.send('derp')
        self.sock.close()    
        
    def pause(self):
        if not self.state == PAUSED:
            self.state = PAUSED
            self.updateScreen(self.data)
        else:
            self.state = STARTED
           
    def updateScreen(self, data, num):
        w, h, img, ti = decoder.read_picture(data)
        
        #self.findGoodFeatures(img)
        #self.findFaces(img)
        
        rfactor = 3
        resized = cv.CreateMat(img.height*rfactor, img.width*rfactor, cv.CV_8UC3)
        cv.Resize(img, resized)

        cv.ShowImage(self.window, resized);
        cv.WaitKey(1)
        
        if self.RECORD:
            f = open('./testdata/' + str(num) + '.dat', 'w')
            f.write(data)
            f.close()
            cv.WriteFrame(self.writer, img)

        return ti

    def printButtons(self, img):
        font = cv.InitFont(cv.CV_FONT_HERSHEY_SIMPLEX, 1.0, 1.0)
        cv.Rectangle(img, (850, 660), (950, 710),  cv.RGB(17, 110, 255)) 
        cv.Rectangle(img, (740, 660), (840, 710),  cv.RGB(17, 110, 255)) 
        
        if self.state == PAUSED:
            cv.PutText(img, 'Play', (742, 700), font, cv.RGB(17, 110, 255))
        else:
            cv.PutText(img, 'Pause', (742, 700), font, cv.RGB(17, 110, 255))

        cv.PutText(img, 'Stop', (852, 700), font, cv.RGB(17, 110, 255))


    def findGoodFeatures(self, img):
        gray  = cv.CreateImage ((320, 240), cv.IPL_DEPTH_8U, 1)
        cv.CvtColor(img, gray,cv.CV_BGR2GRAY)
        eig_image = cv.CreateImage(cv.GetSize(img), cv.IPL_DEPTH_32F, 1)
        temp_image = cv.CreateImage(cv.GetSize(img), cv.IPL_DEPTH_32F ,1)
        for (x,y) in cv.GoodFeaturesToTrack(gray, eig_image, temp_image, 10, 0.04, 1.0, useHarris = True):
             Utils.dprint(DEBUG, "good feature at ("+ str(x)+"," + str(y))
             cv.Circle(img, (int(x), int(y)), 10, cv.RGB(17, 110, 255))
        Utils.dprint(DEBUG, '=====================================================')

    def findFaces(self, img):
        gray  = cv.CreateImage ((320, 240), cv.IPL_DEPTH_8U, 1)
        cv.CvtColor(img, gray,cv.CV_BGR2GRAY)
        cascade = cv.Load('./haarcascade_frontalface_alt.xml')
        faces = cv.HaarDetectObjects(gray, cascade, cv.CreateMemStorage(0), 1.2, 2, 0, (20, 20))
        
        if faces:
            for face in faces:
                rect = face[0]
                cv.Rectangle(img, (rect[0], rect[1]), (rect[0]+rect[2], rect[1]+rect[3]),  cv.RGB(17, 110, 255)) 
                
    def callBack(self, event, x, y, flags, param):
        if x > 850 and x < 950 and y > 660 and y < 710 and event == cv.CV_EVENT_LBUTTONDOWN:
            self.stop()
        elif x > 740 and x < 840 and y > 660 and y < 710 and event == cv.CV_EVENT_LBUTTONDOWN:
            self.pause()


def main():
    
    vt = VideoThread(True, False, False)
    vt.start()
    #while not vt.state == STARTED:
        #pass

    s = raw_input('Push any key to stop video...')
    vt.stop()
    vt.join()
    
if __name__ == '__main__':
    main()
