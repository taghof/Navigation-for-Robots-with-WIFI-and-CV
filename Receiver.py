#!/usr/bin/env python2.7

import datetime
import time
import threading
import socket
import multiprocessing
import select
import cv
import math
import Utils
import decoder
import Queue
import Settings
import pickle
from collections import OrderedDict

class Receiver(multiprocessing.Process):

    def __init__(self, port):

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
        self.comlist[3] = Settings.INIT

        multiprocessing.Process.__init__(self, target=self.runner, args=(self.comlist,))        
        
        self.MCAST = Settings.MULTI
        self.TEST = Settings.TEST
        self.PORT = port 
        self.INIT_PORT = port
      
        self.DRONE_IP = Settings.DRONE_IP
        self.INITMSG = Settings.INITMSG
        self.MCAST_GRP = Settings.MCAST_GRP
        self.DEBUG = Settings.DEBUG
        
        self.samples = OrderedDict()
        self.targetSample = None
              
        # Standard socket setup for unicast
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setblocking(0)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
       
        if self.TEST:
            self.DRONE_IP = Settings.TEST_DRONE_IP
            self.INIT_PORT = Settings.TEST_DRONE_INIT_PORT

        # changing the socket setup to multicast
        if self.MCAST:
            self.INITMSG = Settings.INITMSG_MCAST
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32) 
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
            self.sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, socket.inet_aton('192.168.1.2'))
            self.sock.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(self.MCAST_GRP) + socket.inet_aton('192.168.1.2'))
        
        self.sock.bind(('', self.PORT))
        
    def init(self):
        self.sock.sendto(self.INITMSG, (self.DRONE_IP, self.INIT_PORT))
        self.sock.sendto(self.INITMSG, (self.DRONE_IP, self.INIT_PORT))
        self.sock.sendto(self.INITMSG, (self.DRONE_IP, self.INIT_PORT))
        Utils.dprint("", 'initing')

    def runner(self, l):
        print 'Starting receiver ', self.PORT, '\r'
        history = OrderedDict()
        currentbuffer = 1       
        runs = 0
        dumplist = []
        time_start = datetime.datetime.now()
        self.init()
        self.setStatus(Settings.RUNNING)
        while l[3]:
            
            inputready, outputready, exceptready = select.select([self.sock], [], [], 1)

            for i in inputready:
                
                if i == self.sock:
                    try:
                        data, addr = self.sock.recvfrom(65535)
                    except socket.error, e:
                        Utils.dprint("",  e)
            
                    if data:
                        Utils.dprint("", 'Got data')
                        if l[3] == Settings.CAPTURE:
                            dumplist.append(data)
                        l[2] = (runs+1)%2
                        l[currentbuffer] = self.onReceiveData(data, history)
                        currentbuffer = runs%2
                        runs += 1
            
            if runs % 50 == 0:
                self.init()


        if len(dumplist):
            ofile = open("./pickled_" + str(self.PORT) + ".data", "w")
            pickle.dump(dumplist, ofile)
            ofile.close()

        time_end = datetime.datetime.now()
        delta = (time_end - time_start)
        time_elapsed = (delta.microseconds + (delta.seconds*1000000.0))/1000000.0
        print 'Shutting down receiver ', self.PORT,'\t\t (' + str(runs), 'packets fetched in', time_elapsed, 'secs)\r'
 
    
    def stop(self):
        self.comlist[3] = Settings.STOPPING 
        self.join()
        self.sock.close()    

    def getData(self):
        index = self.comlist[2]
        data = self.comlist[index]
        return self.onRequestData(data)


    
    def recordSample(self):
        time = datetime.datetime.now()
        sample = self.getData()
        self.samples[time] = sample
        return sample

    def recordSamples(self, duration, repetitions):
        print "starting periodic wifi recording\r"
        t = PeriodicTimer(duration, repetitions, self.recordSample)
        t.start()

    def getSamples(self):
        return self.samples # should this be deepcloned?

    def setTargetSample(self):
        self.targetSample = self.recordSample()

    def getTargetSample(self):
        return self.targetSample
   
    
    def toggleCapture(self):
        print "toggleCapture\r"
        if self.getStatus() == Settings.CAPTURE:
            self.setStatus(Settings.RUNNING)
        else:
            self.setStatus(Settings.CAPTURE)
        
    
    def getStatus(self):
        return self.comlist[3]

    def setStatus(self, arg):
        self.comlist[3] = arg

    
    def onRequestData(self, data):
        return data

    def onReceiveData(self, data, history):
        return data
    
class VideoReceiver(Receiver):

    def __init__(self, port):
        Receiver.__init__(self, port)
        self.display_capture = False
        self.display_dump = []
        
    def stop(self):
        Receiver.stop(self)    
        if self.display_capture:
            fileObj = open("./pickled_played_video.data", "a")
            pickle.dump(self.display_dump, fileObj)
            fileObj.close()

    def recordSample(self):
        time = datetime.datetime.now()
        print 'VIDEO sample recorded at: ', time, "\r"
        img = self.getData()
        gray  = cv.CreateImage ((320, 240), cv.IPL_DEPTH_8U, 1)
        canny = cv.CreateImage ((320, 240), cv.IPL_DEPTH_8U, 1)
        cv.CvtColor(img, gray,cv.CV_BGR2GRAY)
        cv.Canny(gray, canny, 10, 15)
        
        li = cv.HoughLines2(canny, cv.CreateMemStorage(), cv.CV_HOUGH_STANDARD, 1, math.pi/180, 100, 0, 0)
              
        p = {}
        coords =  []
        for (rho,theta) in li:
           
            if theta < 0.04:
                c = math.cos(theta)
                s = math.sin(theta)
                x0 = c*rho
                y0 = s*rho
                cv.Line(img,
                        ( int(x0 + 1000*(-s)) , int(y0 + 1000*c) ),
                        (int(x0 + -1000*(-s)), int( y0 - 1000*c)),
                        (0,0,255))
                index = int(min([int(x0 + 1000*(-s)), int(x0 + -1000*(-s))]) + (abs((x0 + 1000*(-s)) - (x0 + -1000*(-s))) / 2))
                p[index] = 1
                coords.append( ( (int(x0 + 1000*(-s)) , int(y0 + 1000*c)) , (int(x0 + -1000*(-s)), int( y0 - 1000*c)) ) )
              
        self.samples[time] = (p, coords) 
        return (p, coords, img)

    def onRequestData(self, data):
        if data:
            if self.display_capture:
                self.display_dump.append(data)
            w, h, img, ti = decoder.read_picture(data)
            return img
        else:
            return None

    def toggleDisplayCapture(self):
        print "toggleDislayCapture\r"
        if self.display_capture:
            fileObj = open("./pickled.data", "a")
            pickle.dump(self.display_dump, fileObj)
            fileObj.close()

        self.display_capture = not self.display_capture


class WifiReceiver(Receiver):
    
    def __init__(self, port):
        Receiver.__init__(self, port)
                    
    def startPeriodicWifiMatching(self, duration, repetitions):
        pass

    def matchCurrentWifiSample(self):
        if self.targetSample == None:
            print "Can't match, target sample not set\r"
            return 0
        else:
            res = self.matchWifiSample(3, self.targetSample, self.getData())
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

    def onReceiveData(self, data, history):
        keyval = data.split('#')
        if not (history.has_key(keyval[0]) and int(history[keyval[0]][0]) - int(keyval[1]) > 40):
            history[keyval[0]] = (int(keyval[1]), datetime.datetime.now())
        return history



class NavdataReceiver(Receiver):

    def __init__(self, port):
        Receiver.__init__(self, port)
        
    def onRequestData(self, data):
        if  data:
            nd = decoder.decode_navdata(data)
            return nd
        else:
            return None

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
