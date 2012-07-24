import drone
import settings
import threading
import cv2
import cv2.cv as cv
import numpy as np
import time
import datetime
import math
import random
import blobdetect as bd
from collections import OrderedDict

class PositionDetector(object):

    def __init__(self, drone):
        self.drone = drone
        self.video_sensor = self.drone.get_video_sensor()
        self.wifi_sensor = self.drone.get_wifi_sensor()
        self.navdata_sensor = self.drone.get_navdata_sensor()
        self.interface = self.drone.get_interface()
        self.map = self.drone.get_map()
        #self.show = True
        self.show = False
        self.loop_sleep = 0.03
        if settings.TEST:
            self.mode = 'normal'
        else:
            self.mode = 'wifi'

        self.silhouets = []
        self.points = []
        self.last_small = None
        self.last_large = None
        self.status = settings.INIT

        self.cascade = cv2.CascadeClassifier('./haarcascade_mcs_upperbody.xml')
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector( cv2.HOGDescriptor_getDefaultPeopleDetector() )

        def alternate():
            while True:
                yield 0
                yield 1
                yield 1

        self.channel = alternate()

    def runner(self):

        if self.show:
            win1 = cv2.namedWindow('win1')
            win2 = cv2.namedWindow('win2')
            win3 = cv2.namedWindow('win3')

        self.status = settings.RUNNING
        frames = 0
        pf = 0
        sf = 0
        
        if self.mode == 'combo' or self.mode == 'combosimple':
            self.interface.zap(2)
            time.sleep(2)
        else:
            self.interface.zap(1)
            time.sleep(2)

        while not self.status == settings.STOPPING:
            
            if frames >= 199:
                pass
                #self.drone.stop()
            frames += 1
            #print 'frames: ',frames
            img = self.video_sensor.get_data()
                      
            if img is None:
                frames -= 1
                print 'no images'
                pass
                       
            elif self.mode == 'normal':
                #self.interface.zap(self.channel.next())
                if img.shape[1] == 176:
                        self.last_small = img
                        self.points = self.detect_position_img(img)
                        if len(self.points) > 0:
                            p = self.points[0]
                        #for p in self.points:
                            if self.show:
                                cv2.circle(img, (int(p[0]), int(p[1])), 2, (255, 255, 255), 10)
                               
                            if p[2] == settings.GREEN:
                                pf += 1
                                print 'green'
                            # elif p[2] == settings.BLUE:
                            #     print 'blue\r'
                   
                elif img.shape[1] == 320:
                    # minipic = img[0:88, 0:72]
                    # self.points = self.detect_position_img(minipic)
                    # if self.points is not None:
                    #     pf += 1
                    #     for p in self.points:
                    #         print 'color: ', p[2]
                    self.last_large = img
                    self.silhouets = self.detect_silhouets(img)
                    if len(self.silhouets) > 0:
                        sf += 1
                        print 'sil: ' , len(self.silhouets) , '\r'
                   
            elif self.mode == 'simple':
                 blob = bd.detect_red_blob(img)
                 if blob is not None:
                     (xpos, ypos), (width, height) = position, size = blob
                     if width*height > 15:
                         pf += 1

            elif self.mode == 'combo':
                 if img.shape[1] == 320:
                    minipic = img[0:72, 0:88]
                    self.points = self.detect_position_img(minipic)
                    if len(self.points) >= 1:
                        p = self.points[0]
                        if p[2] == settings.GREEN:
                            pf += 1
                            #print 'green'

            elif self.mode == 'combosimple':
                 if img.shape[1] == 320:
                    minipic = img[0:88, 0:72]
                    blob = bd.detect_red_blob(minipic)
                    if blob is not None:
                        (xpos, ypos), (width, height) = position, size = blob
                        if width*height > 15:
                            pf += 1

            elif self.mode == 'wifi':
                wifi_pos = self.detect_position_wifi()
                if wifi_pos is not None:
                    #print wifi_pos.name 
                    if wifi_pos.name == 'pos3':
                        pf += 1
           
            elif self.mode == 'test':
                ran = random.randint(0, 50)
                if ran in [48, 1, 4, 7, 22, 30]:
                    color = random.randint(0, 4)
                    img = img[0:176, 0:144]
                    self.points = [(88.0, 72.0, color, img)]
                    self.last_small = img
                elif ran == 50:
                    self.silhouets = [[88.0, 20, 200, 100]]
                else:
                    self.points = []
                    self.silhouets = []

            if self.show and img is not None:
                cv2.imshow(win1 ,img)

            time.sleep(self.loop_sleep)
        
        # print frames
        # print 'pointrate: ', pf/float(frames), '\r'
        # print 'silrate: ', sf/float(frames), '\r'

    def get_status(self):
        return self.status

    def set_status(self, arg):
        self.status = arg

    def start(self):
        threading.Thread(target=self.runner).start() 
    
    def stop(self):
        self.status = settings.STOPPING
        print 'stopping PositionDetector\r'

    def detect_position_img(self, img):
        result = []
        org = img
        pic = cv2.cvtColor(org, cv2.COLOR_BGR2RGB)
        hsv = cv2.cvtColor(org, cv2.COLOR_RGB2HSV)
        thresh_l = cv2.inRange(hsv, np.asarray((0, 30, 30)), np.asarray((30, 150, 255)))
        thresh_h = cv2.inRange(hsv, np.asarray((169, 50, 50)), np.asarray((179, 150, 255)))
        thresh = cv2.add(thresh_l, thresh_h)
        #thresh = cv2.inRange(org, np.asarray((200, 200, 200)), np.asarray((255, 255, 255)))
        if self.show:
            cv2.imshow('win3' , thresh)
            cv2.waitKey(10)
        # cv2.imshow('win' , thresh)
        # cv2.waitKey(10)
          
        contours,hierarchy = cv2.findContours(thresh ,cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
       
        #print '*************'
        # alt = self.navdata_sensor.get_data().get(0, dict()).get('altitude', 0)
        # print 'alt: ', alt
        for cnt in contours:
            #print cv2.contourArea(cnt)
            if cv2.contourArea(cnt) >= 100:
                [x,y,w,h] = cv2.boundingRect(cnt)
                #if  h > 20 and w > 20:
                mini_pic = hsv[(y):(y+h),(x):(x+w)]
                res = self.detect_color(mini_pic)
                pad_w, pad_h = int(0.15*w), int(0.05*h)
                cv2.rectangle(org, (x+pad_w, y+pad_h), (x+w-pad_w, y+h-pad_h), (0, 255, 0), 2)

                if res is not None:
                    x = x + res[0]
                    y = y + res[1]
                    color = res[3]
                    result.append( (x, y, color, org) )
                    
                if self.show:
                    cv2.imshow('win2' , org)
                    cv2.waitKey(10)

        return result
        
    def detect_silhouets(self, img):
        res = []
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        img_gray = cv2.equalizeHist(img_gray)
       
        for x, y, w, h in self.cascade.detectMultiScale(img_gray, scaleFactor=1.3, minNeighbors=4, minSize=(30, 30), flags = cv.CV_HAAR_SCALE_IMAGE):
            res.append((x,y,w,h))

        # for x, y, w ,h in self.hog.detectMultiScale(img, winStride=(8,8), padding=(32,32), scale=1.05):
        #     res.append((x,y,w,h))
       
        return res
    
    def detect_color(self, img):

        pic = cv2.inRange(img, np.asarray((50, 10, 40)), np.asarray((80, 255, 255)))

        moments = cv2.moments(pic, 0)
        area = moments.get('m00')
        if(area > 10000):
            x = moments.get('m10')/area 
            y = moments.get('m01')/area
            #print 'green'
            return (x, y, pic, settings.GREEN)

        pic = cv2.inRange(img, np.asarray((97, 10, 40)), np.asarray((125, 255, 255)))
    
        moments = cv2.moments(pic, 0)
        area = moments.get('m00')
        if(area > 10000):
            x = moments.get('m10')/area 
            y = moments.get('m01')/area 
            #print 'blue'
            return (x, y, pic, settings.BLUE)

        pic = cv2.inRange(img, np.asarray((25, 20, 40)), np.asarray((50, 255, 255)))
    
        moments = cv2.moments(pic, 0)
        area = moments.get('m00')
        if(area > 10000):
            x = moments.get('m10')/area 
            y = moments.get('m01')/area 
            #print 'blue'
            return (x, y, pic, settings.YELLOW)


        return None

    def detect_position_wifi(self):
        maxmval = 100
        closest_pos = None
        val = 0
        #p2 = self.wifi_sensor.record_sample()
        #if p2 is not None and len(p2) > 0:
        #print '**********************'
        for p1 in self.map.positions:
            for i in range(1):
                p2 = self.wifi_sensor.record_sample()
                if len(p2) > 0:
                    
                    mval = self.match_wifi_sample(1, p1.wifi, p2)
         #           print p1.name, ' mval: ', mval, '\r'
                                       
                    if mval < maxmval:
                        maxmval = mval
                        closest_pos = p1
                        val = mval

        return closest_pos
                    
    def match_wifi_sample(self, min_match_len, p1, p2):
        if p1 is None or p2 is None:

            return 1000

        if len(p1) < min_match_len:

            return 1000

        match_set = OrderedDict()
        threshold = 5.0
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
                    #match_set[key] = (val[0], significance)
                else:
                    significance = 1
                    match_set[key] = (val[5], significance)
    
        mval = 0
        mval2 = 0
        maxmval = 0
        maxmval2 = 0
        watt_val = 0
        diffs = 0

        for k, v in match_set.iteritems():
            sig = v[1]
            val0 = v[0]
            val1 = p1.get(k)[5]
         
            dif = math.sqrt((float(val0) - float(val1))**2)
            
            watt_val = (10**(val1/10.0))*10

            # mval += ((val1+100-dif)*watt_val*sig)
            # maxmval += ((val1+100)*watt_val)
            diffs += (dif/sig)

            mval2 +=  ((val1-dif)*watt_val)/sig
            maxmval2 += (val1*watt_val)

            # print 'val1: ', val1, '\r' 
            # print 'dif: ', dif, '\r' 
            # print 'mval2: ', mval2, '\r'

        if len(match_set) > 0:
            difavg = diffs/len(match_set)
        else:
            difavg = 100

        #print 'wat_val: ', watt_val , '\r'
        #print "mval: ", mval, "maxmval: ", maxmval, "\r"
        if not maxmval2:
            return 1000
        else:
            pval2 = (maxmval2/mval2) * 100
            #pval1 = (mval / maxmval) * 100

            # print 'pval1: ', pval1, '\r'
            #print 'pval2: ', pval2, '\r'
            # print 'rel:', pval1/pval2 , '\r'
            #return pval2
            return difavg
        #     self.last_matches.put(pval)
        # return self.last_matches.get_avg()

    def record_target_sample(self):
        pass


class DistanceTracker(object):

    def __init__(self, drone):
        self.status = settings.INIT
        self.drone = drone
        self.video_sensor = self.drone.get_video_sensor()
        self.wifi_sensor = self.drone.get_wifi_sensor()
        self.navdata_sensor = self.drone.get_navdata_sensor()
        self.interface = self.drone.get_interface()
        self.map = self.drone.get_map()
       
        self.dist_x = 0
        self.dist_y = 0
        self.last_time = None
        self.last_vx = 0
        self.last_vy = 0
        self.loop_sleep = 0.03

    def runner(self):
        self.last_time = time.time()
        self.status = settings.RUNNING
        while not self.status == settings.STOPPING:
             self.measure()
             time.sleep(self.loop_sleep)
        print 'moved: (', self.dist_x, ', ', self.dist_y, ')'

    def measure(self):
        """ The measure method does the hard work of performing a crude integration of the
        velocities from the drone navdata """
       
        now_time = time.time()
        elapsed_time = self.last_time - now_time
        vx = self.navdata_sensor.get_data().get(0, dict()).get('vx', 0)
        vy = self.navdata_sensor.get_data().get(0, dict()).get('vy', 0)
         

        if (vx < 0) == (self.last_vx < 0): 
            small_vx = min(math.fabs(vx), math.fabs(self.last_vx)) 
            rect_x = small_vx*elapsed_time
            tri_x = ((max(math.fabs(vx), math.fabs(self.last_vx))-small_vx)/2)*elapsed_time
            if vx < 0:
                self.dist_x -= tri_x + rect_x
            else:
                self.dist_x += tri_x + rect_x
        else:
            time_fraction_x = (math.fabs(self.last_vx)/(math.fabs(self.last_vx)+ math.fabs(vx)))   
            area_vx_last = (self.last_vx * time_fraction_x)/2
            if self.last_vx < 0:
                area_vx_last *= (-1)
            area_vx = (vx * (1-time_fraction_x))/2
            if vx < 0:
                area_vx *= (-1)
            self.dist_x += (area_vx_last + area_vx)*elapsed_time


        if (vy < 0) == (self.last_vy < 0): 
            small_vy = min(math.fabs(vy), math.fabs(self.last_vy)) 
            rect_y = small_vy*elapsed_time
            tri_y = ((max(math.fabs(vy), math.fabs(self.last_vy))-small_vy)/2)*elapsed_time
             
            if vy < 0:
                self.dist_y -= tri_y + rect_y
            else:
                self.dist_y += tri_y + rect_y
        else:
            time_fraction_y = (math.fabs(self.last_vy)/(math.fabs(self.last_vy)+ math.fabs(vy)))*elapsed_time   
            area_vy_last = (self.last_vy * time_fraction_y)/2
            if self.last_vy < 0:
                area_vy_last *= (-1)
            area_vy = (vy * (1-time_fraction_y))/2
            if vy < 0:
                area_vy *= (-1)
            self.dist_y += (area_vy_last + area_vy)*elapsed_time

        # Make ready for next iteration
        self.last_vy = vy
        self.last_vx = vx
        self.last_time = now_time

    def get_status(self):
        return self.status

    def set_status(self, arg):
        self.status = arg

    def start(self):
        threading.Thread(target=self.runner).start() 
    
    def stop(self):
        self.status = settings.STOPPING
        print 'stopping DistanceTracker\r'

    def reset(self):
        """ resets the distance travelled, so far this has been of little use """

        self.dist_x = 0
        self.dist_y = 0
