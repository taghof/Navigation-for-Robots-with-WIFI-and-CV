from __future__ import with_statement
import sys
import time
import threading
import datetime
import cv2.cv as cv
import cv2
import numpy as np
import math
from select import select
from collections import deque

import settings
import tasks

import time

d2r = (math.pi/180.0) # ratio for switching from degrees to radians

class Timer(object):
    def __enter__(self):
        self.__start = time.time()

    def __exit__(self, type, value, traceback):
        # Error handling here
        self.__finish = time.time()

    def duration_in_seconds(self):
        return self.__finish - self.__start




def dprint(d, t):
    if settings.DEBUG:
        print t

def ensure_dir(f):
    d = os.path.dirname(f)
    if not os.path.exists(d):
        os.makedirs(d)

def get_char():
    import sys, tty, termios
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def get_char_with_break():
    import sys, tty, termios, select
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        #while not self.stopping:
        rlist, _, _ = select.select([sys.stdin], [], [], 1)
        if rlist:
            s = sys.stdin.read(1)
            return s
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def get_random_num(self):
    return random.randint(-5, 5)

def cv2array(im): 
  depth2dtype = { 
        cv.IPL_DEPTH_8U: 'uint8', 
        cv.IPL_DEPTH_8S: 'int8', 
        cv.IPL_DEPTH_16U: 'uint16', 
        cv.IPL_DEPTH_16S: 'int16', 
        cv.IPL_DEPTH_32S: 'int32', 
        cv.IPL_DEPTH_32F: 'float32', 
        cv.IPL_DEPTH_64F: 'float64', 
    } 

  arrdtype=im.depth 
  a = np.fromstring( 
         im.tostring(), 
         dtype=depth2dtype[im.depth], 
         count=im.width*im.height*im.nChannels)

  if im.nChannels > 1:
      a.shape = (im.height,im.width,im.nChannels) 
  else:
      a.shape = (im.height,im.width) 
  return a 

def array2cv(a):
  dtype2depth = {
        'uint8':   cv.IPL_DEPTH_8U,
        'int8':    cv.IPL_DEPTH_8S,
        'uint16':  cv.IPL_DEPTH_16U,
        'int16':   cv.IPL_DEPTH_16S,
        'int32':   cv.IPL_DEPTH_32S,
        'float32': cv.IPL_DEPTH_32F,
        'float64': cv.IPL_DEPTH_64F,
    }
  try:
    nChannels = a.shape[2]
  except:
    nChannels = 1
  cv_im = cv.CreateImageHeader((a.shape[1],a.shape[0]),
          dtype2depth[str(a.dtype)],
          nChannels)
  cv.SetData(cv_im, a.tostring(),
             a.dtype.itemsize*nChannels*a.shape[1])
  return cv_im

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



class PID(threading.Thread):
    """
    Discrete PID control
    """

    def __init__(self, source_method, move_method, degrees, P=1.0, I=0.0, D=0.0, Derivator=0, Integrator=0, Integrator_max=500, Integrator_min=-500, stable_point=0.5):
        threading.Thread.__init__(self)
        self.source_method = source_method
        self.move_method = move_method
        self.degrees = degrees

        # variables used in calculating the PID output
        self.Kp=P
        self.Ki=I
        self.Kd=D
        self.Derivator=Derivator
        self.Integrator=Integrator
        self.Integrator_max=Integrator_max
        self.Integrator_min=Integrator_min
      
        # when do we consider the process stable enough to stop?
        self.stable_point = stable_point

        # we won't commit to a set point before we actually begin updating
        self.set_point = None

        # please turn this many degrees
        self.error = degrees
        
        # we can never be more than 180 degrees from our target
        self.max_error = 180
        
        # PID values above this max_pid will be cut off before returning,
        # This should happen only very rarely
        self.max_PID = self.Kp*self.max_error + self.Ki*self.Integrator_max
        self.error_vals = DiscardingQueue(11)

    def run(self):
        while not self.is_stable():
            # Calculate PID output for this iteration
            power = self.update()
            # Use the calculated PID output to actually move
            self.move_method(power)

        # remember to put the vehicle in hover mode after moving
        self.move_method(0)
        

    def update(self):
        """
        Calculate PID output using the input method and the set point
        """

        # Get the current reading
        current_value = self.source_method()

        # If we have not yet assigned a set point do it now, must be a number
        # between 0 and 360
        if self.set_point == None:
            self.set_point = (360+(current_value + self.degrees))%360
            print "moving to: " + str(self.set_point) + "\r" 

        # calculate the current error, must be between -180 and 180
        self.error = (360 + self.set_point - current_value)%360
        if self.error > 180:
            self.error = self.error - 360

        # calculate the P term
        self.P_value = self.Kp * self.error
        
        # calculate the I term, considering integrator max and min 
        self.Integrator = self.Integrator + self.error

        if self.Integrator > self.Integrator_max:
            self.Integrator = self.Integrator_max
        elif self.Integrator < self.Integrator_min:
            self.Integrator = self.Integrator_min

        self.I_value = self.Integrator * self.Ki
       
        # calculate the D term
        self.D_value = self.Kd * ( self.error - self.Derivator)
        self.Derivator = self.error
       
        # Sum the term values into one PID value
        PID = self.P_value + self.I_value + self.D_value

        # Record the current error value for figuring out when to stop
        self.error_vals.put(self.error)
        
        # Calculate a return value between -1 and 1, PID values above max_pid or
        # under -max_pid will be cut to 1 or -1
        retval = (PID/self.max_PID) if (-1 <= (PID/self.max_PID) <= 1) else (PID/abs(PID))

        # print stuff for debugging purposes
        print "Current value: " + str(current_value) + ", Error: " + str(self.error) + "Engine response: " + str(retval)

        # don't let thread suck all power, have a nap
        time.sleep(0.1)
        
        return retval

    def is_stable(self):
        """
        Will return True if the average of the last 10 PID vals is below
        a certain threshold
        """
        #retval = self.error_vals.get_avg() < self.stable_point and self.error_vals.get_std_dev() < self.stable_point and self.max_pid > 0.0
        retval = (-3 <= self.error <= 3)
        #print retval
        return retval

    def setPoint(self,set_point):
        """
        Initilize the setpoint of PID
        """
        self.set_point = set_point
        self.Integrator=0
        self.Derivator=0

    def setIntegrator(self, Integrator):
        self.Integrator = Integrator

    def setDerivator(self, Derivator):
        self.Derivator = Derivator

    def setKp(self,P):
        self.Kp=P

    def setKi(self,I):
        self.Ki=I
        
    def setKd(self,D):
        self.Kd=D

    def getKp(self):
        return self.Kp

    def getKi(self):
        return self.Ki

    def getKd(self):
        return self.Kd

    def getPoint(self):
        return self.set_point

    def getError(self):
        return self.error

    def getIntegrator(self):
        return self.Integrator

    def getDerivator(self):
        return self.Derivator



class PIDxy(threading.Thread):
    """
    Discrete PID control
    """

    def __init__(self, drone, callback_method=None, context=None, P=1.0, I=0.0, D=0.0, Integrator_max=500, Integrator_min=-500):
        threading.Thread.__init__(self)

        self.drone = drone
        self.context = context
        self.callback_method = callback_method
        self.move_method = self.drone.get_interface().move
        self.tracker = None

        self.start_time = datetime.datetime.now()
        self.verbose = False

        # variables used in calculating the PID output
        self.Kp=P
        self.Ki=I
        self.Kd=D
        self.Derivator_x = 0
        self.Derivator_y = 0
        self.Derivator_psi = 0

        self.Integrator_x = 0
        self.Integrator_y = 0
        self.Integrator_psi = 0

        self.Integrator_max=Integrator_max
        self.Integrator_min=Integrator_min

        # we have the set point right in the middle of the picture
        # init_mes = self.source_method()
        # self.set_point_x = init_mes[0]
        # self.set_point_y = init_mes[1]
        # self.set_point_psi = init_mes[4]
        # our initial errors

        self.center = (88, 72)
        # self.pixelfactor_x = 3.8
        # self.pixelfactor_y = 4.035
        
        # angle_correction_x = (init_mes[2]*self.pixelfactor_x) 
        # angle_correction_y = (init_mes[3]*self.pixelfactor_y) 

        # TODO fix init val
        # calculate the current error, must be between -88 and 88 and -72 and 72
        # self.error_x = (self.set_point_x - (self.center[0]))# - angle_correction_x
        # self.error_y = (self.set_point_y - (self.center[1]))# - angle_correction_y
        # self.error_psi = 0

        # we can never be more than 88 or 72 pixels from our target
        self.max_error_x = (4000*(math.tan(32*(math.pi/180))/88.0))*88.0#160.0 # 88
        self.max_error_y = (4000*(math.tan(26.18*(math.pi/180))/72.0))*72.0#120.0 # 72
        self.max_error_psi = 180

        self.running = False
        self.started = False

        # PID values above this max_pid will be cut off before returning,
        # This should happen only very rarely
        #self.max_PID_x = self.Kp*self.max_error_x + self.Ki*self.Integrator_max
        #self.max_PID_y = self.Kp*self.max_error_y + self.Ki*self.Integrator_max

    def stop(self):
        self.running = False

    def is_started(self):
        return self.started

    def run(self):
        self.running = True
        self.started = True

        self.tracker = PointTracker(self.drone.get_video_sensor(), self.drone.get_navdata_sensor(), self.context[0])
        self.context[1].tracker = self.tracker
        self.tracker.start()
        self.source_method = self.tracker.get_point
        self.set_point_psi = self.source_method()[4]
       
        self.move_method(0, 0, 0, 0,False)
        print 'PIDxy running\r'
        while self.running:
            # Calculate PID output for this iteration
            powers = self.update()
            if powers is None:
                break
            else:
                # Use the calculated PID output to actually move
                self.move_method(powers[0], powers[1], powers[2], powers[3], True)

        # remember to put the vehicle in hover mode after moving
        self.context[0] = None
        self.tracker.stop()
        self.move_method(0, 0, 0, 0)
        if self.callback_method is not None:
            self.callback_method(self)
        print 'shutting down PIDxy\r'

    def update(self):
        """
        Calculate PID output using the input method and the set point
        """

        # Get the current reading
        currents = self.source_method()
        if currents is None:
            return None
        self.set_point_x = currents[0]
        self.set_point_y = currents[1]

        # angle_correction_x = (currents[2]*self.pixelfactor_x) 
        # angle_correction_y = (currents[3]*self.pixelfactor_y) 

        alt = currents[5]
        angle_x = currents[2]*d2r
        angle_y = currents[3]*d2r
        psi_angle = currents[4]

        #print '*****************************\r\r'
        self.read_error_x_pixels = self.set_point_x - self.center[0]
        c = (math.tan(32.0*d2r)/88.0) # error in the plane perpendicular to height
        #print c, "\r"
        self.read_error_x_mm = self.read_error_x_pixels*(alt*c)
        extra_angle_x = math.atan(alt/math.fabs(self.read_error_x_mm+0.0000000001))
        x_in_error = alt * math.sin(angle_x) # error contributed by the tilting itself
        real_alt = math.sqrt((alt*alt)-(x_in_error*x_in_error))
        #print 'real_alt:\t', real_alt, '\r'

        if angle_x < 0 and self.read_error_x_mm > 0 or angle_x > 0 and self.read_error_x_mm < 0:
            # print 'case x_out_1\r'
            a = math.sin(extra_angle_x)
            b = math.sin(extra_angle_x-angle_x)
            # print 'a:\t\t' + str(a) + '\r'
            # print 'b:\t\t' + str(b) + '\r'
            x_out_error = self.read_error_x_mm * (a / b)
        else:
            # print 'case x_out_2\r'
            a = math.sin(extra_angle_x)
            b = math.cos(angle_x)
            # print 'a:\t\t' + str(a) + '\r'
            # print 'b:\t\t' + str(b) + '\r'
            x_out_error = self.read_error_x_mm * (a / b) 
        self.error_x = x_out_error - x_in_error
        
        # *****************************
        
        self.read_error_y_pixels = self.set_point_y - self.center[1]
        c = (math.tan(26.18*d2r)/72.0) # error in the plane perpendicular to height
        #print c, "\r"
        self.read_error_y_mm = self.read_error_y_pixels*(alt*c)
        extra_angle_y = math.atan(alt/math.fabs(self.read_error_y_mm+0.0000000001))
        y_in_error = alt * math.sin(angle_y) # error contributed by the tilting itself
        
        
        if angle_y < 0 and self.read_error_y_mm > 0 or angle_y > 0 and self.read_error_y_mm < 0:
            # print 'case y_out_1\r'
            a = math.sin(extra_angle_y)
            b = math.sin(extra_angle_y-angle_y)
            # print 'a:\t\t' + str(a) + '\r'
            # print 'b:\t\t' + str(b) + '\r'
            y_out_error = self.read_error_y_mm * (a / b)
        else:
            # print 'case y_out_2\r'
            a = math.sin(extra_angle_y)
            b = math.cos(angle_y)
            # print 'a:\t\t' + str(a) + '\r'
            # print 'b:\t\t' + str(b) + '\r'
            y_out_error = self.read_error_y_mm * (a / b) 
        self.error_y = y_out_error - y_in_error
        
        # *****************************

        # calculate the current error, must be between -88 and 88 and -72 and 72
        # self.error_x = (self.set_point_x - (self.center[0])) - angle_correction_x
        # self.error_y = (self.set_point_y - (self.center[1])) - angle_correction_y
        self.error_psi = (360 + self.set_point_psi - psi_angle)%360
        if self.error_psi > 180:
            self.error_psi = self.error_psi - 360

        # calculate the P term
        self.P_value_x = self.Kp * (self.error_x/self.max_error_x)
        self.P_value_y = self.Kp * (self.error_y/self.max_error_y)
        self.P_value_psi = self.Kp * (self.error_psi/self.max_error_psi)

        # calculate the I term, considering integrator max and min 
        self.Integrator_x = self.Integrator_x + self.error_x
        self.Integrator_y = self.Integrator_y + self.error_y
        self.Integrator_psi = self.Integrator_psi + self.error_psi

        if self.Integrator_x > self.Integrator_max:
            self.Integrator_x = self.Integrator_max
        elif self.Integrator_x < self.Integrator_min:
            self.Integrator_x = self.Integrator_min
        
        if self.Integrator_y > self.Integrator_max:
            self.Integrator_y = self.Integrator_max
        elif self.Integrator_y < self.Integrator_min:
            self.Integrator_y = self.Integrator_min

        if self.Integrator_psi > self.Integrator_max:
            self.Integrator_psi = self.Integrator_max
        elif self.Integrator_psi < self.Integrator_min:
            self.Integrator_psi = self.Integrator_min

        self.I_value_x = self.Integrator_x * self.Ki
        self.I_value_y = self.Integrator_y * self.Ki
        self.I_value_psi = self.Integrator_psi * self.Ki
       
        # calculate the D term
        self.D_value_x = self.Kd * ((self.error_x - self.Derivator_x)/self.max_error_x)
        self.Derivator_x = self.error_x

        self.D_value_y = self.Kd * ((self.error_y - self.Derivator_y)/self.max_error_y)
        self.Derivator_y = self.error_y

        self.D_value_psi = self.Kd * ((self.error_psi - self.Derivator_psi)/self.max_error_psi)
        self.Derivator_psi = self.error_psi


        # Sum the term values into one PID value
        PID_x = self.P_value_x + self.I_value_x + self.D_value_x
        PID_y = self.P_value_y + self.I_value_y + self.D_value_y
        PID_psi = self.P_value_psi + self.I_value_psi + self.D_value_psi

        # Record the current error value for figuring out when to stop
        # self.error_vals.put(self.error)
        
        # Calculate a return value between -1 and 1, PID values above max_pid or
        # under -max_pid will be cut to 1 or -1
        retval_x = PID_x #(PID_x/self.max_PID_x) if (-1 <= (PID_x/self.max_PID_x) <= 1) else (PID_x/abs(PID_x))
        retval_y = PID_y #(PID_y/self.max_PID_y) if (-1 <= (PID_y/self.max_PID_y) <= 1) else (PID_y/abs(PID_y))
        retval_psi = PID_psi

        # print stuff for debugging purposes
        if self.verbose:
            print "Error_x_pixels: " + str(self.read_error_x_pixels) + "\tError_x_mm:\t" + str(self.error_x) + "\tError_angle_x: " + str(currents[2]) + "\tEngine response_x: " + str(retval_x) + "\r"
            print "Error_y_pixels: " + str(self.read_error_y_pixels) + "\tError_y_mm:\t" + str(self.error_y) + "\tError_angle_y: " + str(currents[3]) + "\tEngine response_y: " + str(retval_y) + "\r"
            print "Error_combined: " + str(math.sqrt((self.error_y*self.error_y)+(self.error_x*self.error_x))) + "\r"
            print "Altitude:\t", alt, "\r"
        #print "Current value_y: " + str(self.set_point_y) + ", Error_y: " + str(self.error_y) + ", Engine response_y: " + str(retval_y)

        # # don't let thread suck all power, have a nap
        time.sleep(0.05)
        return (retval_x, retval_y, 0.0, retval_psi)

    def toggle_verbose(self):
        self.verbose = not self.verbose

    def setPsi(self, degrees):
        self.set_point_psi = (360+(self.set_point_psi + degrees))%360
        print "moving to: " + str(self.set_point_psi) + "\r" 

    def getKp(self):
        return self.Kp

    def getKi(self):
        return self.Ki

    def getKd(self):
        return self.Kd

    def setKp(self,P):
        print "setting Kp to: " + str(P)
        self.Kp=P

    def setKi(self,I):
        print "setting Ki to: " + str(I)
        self.Ki=I
        
    def setKd(self,D):
        print "setting Kd to: " + str(D)
        self.Kd=D



class DiscardingQueue(object):


    def __init__(self, max_size):
        self.max_size = max_size
        self.q = deque()
        self.lock = threading.Lock()

    def __getstate__(self):
        state = self.__dict__.copy()
        del state['lock']
        return state

    def __setstate__(self, state):
        self.__dict__ = state
        self.lock = threading.Lock()

    def get_len(self):
        self.lock.acquire()
        retval = len(self.q)
        self.lock.release()
        return retval

    def put(self, item):
        self.lock.acquire()
        if len(self.q) >= self.max_size:
            self.q.popleft()
        self.q.append(item)
        self.lock.release()

    def get_avg(self):
        self.lock.acquire()
        total = 0
        for elem in self.q:
            total += elem
        if total:
            self.lock.release()
            return total/len(self.q)
        else:
            self.lock.release()
            return None

    def get_vals(self):
        return self.q
            

    def get_var(self):
        avg = self.get_avg()
        self.lock.acquire()
        total = 0
        if len(self.q):
            for elem in self.q:
                total += (elem - avg) ** 2#(elem - avg)
            self.lock.release()
            return total/len(self.q)
        else:
            self.lock.release()
            return None
        

    def get_std_dev(self):
        var = self.get_var()
        if var:
            return var ** (0.5)
        else:
            return 0


class PointTracker(threading.Thread):

    def __init__(self, videoreceiver, navdatareceiver, point=None):
        threading.Thread.__init__(self)
        
        self.videoreceiver = videoreceiver
        self.navdatareceiver = navdatareceiver
        self.original_point = point
        if point is None:
            print 'point from centext was None\r'
            self.point = (88,72)
        else:
            self.point = point

        self.frame0 = None
        self.frame1 = None
        self.running = True

    def set_point(self, p):
        self.original_point = p

    def get_point(self):
        p = self.point
        navdata = self.navdatareceiver.get_data()
        if not p is None and not navdata is None and self.running:
            theta   = navdata.get(0, dict()).get('theta', 0)
            phi     = navdata.get(0, dict()).get('phi', 0)
            psi     = navdata.get(0, dict()).get('psi', 0)
            alt     = navdata.get(0, dict()).get('altitude', 0)
            return [p[0], p[1], phi, theta, psi, alt]
        else:
            return None

    def stop(self):
        self.running = False

    def run(self):
        self.init()
        while self.running:
            res = self.track()
            time.sleep(0.05)
        print 'Shutting down PointTracker\r'

    def init(self):
        # Get image from video sensor
        self.frame0 = self.videoreceiver.get_data()
        self.org_width = self.frame0.width if type(self.frame0).__name__== 'iplimage' else self.frame0.shape[1]
        self.org_height = self.frame0.height if type(self.frame0).__name__== 'iplimage' else self.frame0.shape[0]

        self.point = self.original_point
        self.features = np.array([self.point], dtype=np.float32)
        self.lk_params = dict( winSize  = (29, 29), 
                              maxLevel = 2, 
                              criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03),
                              flags = 0)
      
        self.maxvx = 0
        self.maxvy = 0

    def track(self):

            # Get image from video sensor
            self.frame1 = self.videoreceiver.get_data()
            navdata = self.navdatareceiver.get_data()

            width = self.frame1.width if type(self.frame1).__name__== 'iplimage' else self.frame1.shape[1]
            height = self.frame1.height if type(self.frame1).__name__== 'iplimage' else self.frame1.shape[0]

            if self.org_width != width or self.org_height != height:
                return None

            (self.features, status, error) = cv2.calcOpticalFlowPyrLK(
                self.frame0, self.frame1, 
                self.features, None, **self.lk_params
                )
           
            self.features = np.hstack([self.features, status])
            self.features = (self.features[~(self.features == 0).any(1)])[:,:2]
                                        
            if len(self.features) == 0:
                self.point = None
                return None
            elif len(self.features) >= 1:
                self.point = self.features[0]

            self.frame0 = self.frame1.copy()
            self.maxvx = max(self.maxvx, navdata.get(0, dict()).get('vx', 0))
            self.maxvy = max(self.maxvy, navdata.get(0, dict()).get('vy', 0))

            
            if not self.point is None and not navdata is None:
                theta   = navdata.get(0, dict()).get('theta', 0)
                phi     = navdata.get(0, dict()).get('phi', 0)
                psi     = navdata.get(0, dict()).get('psi', 0)
                alt     = navdata.get(0, dict()).get('altitude', 0)
                return [self.point[0], self.point[1], phi, theta, psi, alt]
            else:
                return None
