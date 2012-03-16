#!/usr/bin/env python2.7
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
import math
import threading
import socket
import multiprocessing
import select
import Queue
import pickle
from collections import OrderedDict
from collections import deque

import cv

import utils
import decoder
import settings

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
        self.comlist[3] = settings.INIT
        
        multiprocessing.Process.__init__(self, target=self.runner, args=(self.comlist,))        

        self.PORT = port 
        self.INIT_PORT = port
        
        self.DRONE_IP = settings.DRONE_IP
        self.INITMSG = settings.INITMSG
        self.MCAST_GRP = settings.MCAST_GRP
        self.DEBUG = settings.DEBUG
        
        self.samples = OrderedDict()
        self.target_sample = None
             
        # Standard socket setup for unicast
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setblocking(0)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
       
        if settings.TEST:
            self.DRONE_IP = settings.TEST_DRONE_IP
            self.INIT_PORT = settings.TEST_DRONE_INIT_PORT

        # changing the socket setup to multicast
        if settings.MULTI:
            self.INITMSG = settings.INITMSG_MCAST
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32) 
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
            self.sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, socket.inet_aton('192.168.1.2'))
            self.sock.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(self.MCAST_GRP) + socket.inet_aton('192.168.1.2'))
        
        self.sock.bind(('', self.PORT))
        
    def init(self):
        self.sock.sendto(self.INITMSG, (self.DRONE_IP, self.INIT_PORT))
        self.sock.sendto(self.INITMSG, (self.DRONE_IP, self.INIT_PORT))
        self.sock.sendto(self.INITMSG, (self.DRONE_IP, self.INIT_PORT))
        utils.dprint("", 'initing')

    def runner(self, l):
        print 'Starting receiver ', self.PORT, '\r'
        history = OrderedDict()
        currentbuffer = 1       
        runs = 0
        dumplist = []
        time_start = datetime.datetime.now()
        self.init()
        self.set_status(settings.RUNNING)
        while l[3]:
            
            inputready, outputready, exceptready = select.select([self.sock], [], [], 1)

            for i in inputready:
                
                if i == self.sock:
                    try:
                        data, addr = self.sock.recvfrom(65535)
                    except socket.error, e:
                        utils.dprint("",  e)
            
                    if data:
                        utils.dprint("", 'Got data')
                        if l[3] == settings.CAPTURE:
                            dumplist.append(data)
                        l[2] = (runs+1)%2
                        l[currentbuffer] = self.on_receive_data(data, history)
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
        self.comlist[3] = settings.STOPPING 
        self.join()
        self.sock.close()    

    def get_data(self):
        index = self.comlist[2]
        data = self.comlist[index]
        return self.on_request_data(data)
    
    def record_sample(self):
        sample = self.get_data()
        processed_sample = self.on_record_sample(sample)
        self.samples[datetime.datetime.now()] = processed_sample
        return processed_sample

    def record_samples(self, duration, repetitions):
        print "starting periodic sample recordings\r"
        t = PeriodicTimer(duration, repetitions, self.record_sample)
        t.start()

    def get_samples(self):
        return self.samples # should this be deepcloned?

    def set_target_sample(self):
        self.target_sample = self.record_sample()

    def get_target_sample(self):
        return self.target_sample
   
    def toggle_capture(self):
        print "toggleCapture\r"
        if self.get_status() == settings.CAPTURE:
            self.set_status(settings.RUNNING)
        else:
            self.set_status(settings.CAPTURE)
    
    def get_status(self):
        return self.comlist[3]

    def set_status(self, arg):
        self.comlist[3] = arg

    
    def on_request_data(self, data):
        return data

    def on_receive_data(self, data, history):
        return data

    def on_record_sample(self, sample):
        return sample

    
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

    def on_record_sample(self, data):
        print 'VIDEO sample recorded at: ', time, "\r"
        img = data
        cv.SaveImage("../images/target-image-"+ str(time.time()) + ".png", img)    
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
        
        return (p, coords, img)

    def on_request_data(self, data):
        if data:
            if self.display_capture:
                self.display_dump.append(data)
            w, h, img, ti = decoder.read_picture(data)
            return img
        else:
            return None

    def toggle_display_capture(self):
        print "toggleDislayCapture\r"
        if self.display_capture:
            fileObj = open("./pickled.data", "a")
            pickle.dump(self.display_dump, fileObj)
            fileObj.close()

        self.display_capture = not self.display_capture


class WifiReceiver(Receiver):
    
    def __init__(self, port):
        Receiver.__init__(self, port)
                    
    def start_periodic_wifi_matching(self, duration, repetitions):
        pass

    def match_current_wifi_sample(self):
        if self.target_sample is None:
            print "Can't match, target sample not set\r"
            return 0
        else:
            res = self.matchWifiSample(3, self.target_sample, self.get_data())
            print "match score: ", res, "%\r"
            return res

    def match_wifi_sample(self, min_match_len, p1, p2):
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

    def on_receive_data(self, data, history):
        time = datetime.datetime.now()
        keyval = data.split('#')
        key = keyval[0]
        val = int(keyval[1])

        if history.has_key(keyval[0]):
            if not ((history[key][0] - val) > 40):
                old_avg = history[key][2]
                num_avg = history[key][3]
                last10 = history[key][4]
                time_delta = (time - history[key][1]).total_seconds()
                new_avg = ((old_avg*num_avg)+time_delta)/(num_avg+1)
                last10.put(val)
                history[key] = (val, datetime.datetime.now(), new_avg, num_avg+1, last10, last10.get_avg())
                
        else:
            last10 = DiscardingQueue(10)
            last10.put(val)
            history[key] = (val, datetime.datetime.now(), 0, 0, last10)

        return history

class NavdataReceiver(Receiver):



    def __init__(self, port):
        Receiver.__init__(self, port)
        
    def on_request_data(self, data):
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



class DiscardingQueue(object):


    def __init__(self, max_size):
        self.max_size = max_size
        self.q = deque()

    def put(self, item):
        if len(self.q) >= self.max_size:
            self.q.popleft()
        self.q.append(item)
        
    def get_avg(self):
        total = 0
        for elem in self.q:
            total += elem
        if total:
            return total/len(self.q)
        else:
            return None

    def get_vals(self):
        return self.q
            

    def get_var(self):
        avg = self.get_avg()
        total = 0
        if len(self.q):
            for elem in self.q:
                total += (elem - avg) ** 2#(elem - avg)
            return total/len(self.q)
        else:
            return None

    def get_std_dev(self):
        return self.get_var() ** (0.5)
