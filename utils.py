import sys
import time
import threading
import datetime
import cv2.cv as cv
import numpy as np
from select import select
from collections import deque

import settings

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

def get_char_with_break(self):
    import sys, tty, termios, select
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        while not self.stopping:
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

    def __init__(self, tracker, move_method, callback_method=None, P=0.125, I=0.0, D=0.05, Integrator_max=500, Integrator_min=-500):
        threading.Thread.__init__(self)
        self.tracker = tracker
        self.callback_method = callback_method
        self.source_method = tracker.get_point
        self.move_method = move_method
        self.start_time = datetime.datetime.now()
        self.tracker.start()


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
        init_mes = self.source_method()
        self.set_point_x = init_mes[0]
        self.set_point_y = init_mes[1]
        self.set_point_psi = init_mes[4]
        # our initial errors

        self.center = (88, 72)
        self.pixelfactor_x = 3.8
        self.pixelfactor_y = 4.035
        
        angle_correction_x = (init_mes[2]*self.pixelfactor_x) 
        angle_correction_y = (init_mes[3]*self.pixelfactor_y) 

        # calculate the current error, must be between -88 and 88 and -72 and 72
        self.error_x = (self.set_point_x - (self.center[0])) - angle_correction_x
        self.error_y = (self.set_point_y - (self.center[1])) - angle_correction_y
        self.error_psi = 0

        # we can never be more than 88 or 72 pixels from our target
        self.max_error_x = 88.0
        self.max_error_y = 72.0
        self.max_error_psi = 180
        self.running = False
        self.started = False

        # PID values above this max_pid will be cut off before returning,
        # This should happen only very rarely
        #self.max_PID_x = self.Kp*self.max_error_x + self.Ki*self.Integrator_max
        #self.max_PID_y = self.Kp*self.max_error_y + self.Ki*self.Integrator_max

    def stop(self):
        print '*** stopping ***'
        self.running = False

    def is_started(self):
        return self.started

    def run(self):
        self.running = True
        self.started = True
        print 'Tracking...'
        while self.running:
            # Calculate PID output for this iteration
            powers = self.update()
            if powers is None:
                break
            else:
                # Use the calculated PID output to actually move
                self.move_method(powers[0], powers[1], powers[2], powers[3])

        # remember to put the vehicle in hover mode after moving
        self.tracker.stop()
        self.move_method(0, 0, 0, 0)
        if self.callback_method is not None:
            self.callback_method(self)

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

        angle_correction_x = (currents[2]*self.pixelfactor_x) 
        angle_correction_y = (currents[3]*self.pixelfactor_y) 

        # calculate the current error, must be between -88 and 88 and -72 and 72
        self.error_x = (self.set_point_x - (self.center[0])) - angle_correction_x
        self.error_y = (self.set_point_y - (self.center[1])) - angle_correction_y
        self.error_psi = (360 + self.set_point_psi - currents[4])%360
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
            print "Current value_x: " + str(self.set_point_x) + ", Error_x: " + str(self.error_x) + "(" + str(angle_correction_x) +") , Engine response_x: " + str(retval_x)
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

    def __init__(self, videoreceiver, navdatareceiver, point):
        threading.Thread.__init__(self)
        
        self.videoreceiver = videoreceiver
        self.navdatareceiver = navdatareceiver
        self.original_point = point
        self.point = point
        print point
        self.frame0 = None
        self.frame1 = None
        self.running = True

    def set_point(self, p):
        self.original_point = p

    def get_point(self):
        p = self.point
        navdata = self.navdatareceiver.get_data()
        if not p is None and not navdata is None and self.running:
            retval = []
            theta   = navdata.get(0, dict()).get('theta', 0)
            phi     = navdata.get(0, dict()).get('phi', 0)
            psi     = navdata.get(0, dict()).get('psi', 0)
            retval.append(p[0])
            retval.append(p[1])
            retval.append(phi)
            retval.append(theta)
            retval.append(psi)
            return retval
        else:
            return None

    def stop(self):
        self.running = False

    def run(self):
        
        #self.running = True
        # Get image from video sensor
        frame0_org = self.videoreceiver.get_data()

        # Convert image to gray
        self.frame0 = cv.CreateImage ((frame0_org.width, frame0_org.height), cv.IPL_DEPTH_8U, 1)
        cv.CvtColor(frame0_org, self.frame0, cv.CV_RGB2GRAY)

        self.point = self.original_point
        while self.running:
            # Get image from video sensor
            frame1_org = self.videoreceiver.get_data()

            # Convert image to gray
            self.frame1 = cv.CreateImage ((frame0_org.width, frame0_org.height), cv.IPL_DEPTH_8U, 1)
            cv.CvtColor(frame1_org, self.frame1, cv.CV_RGB2GRAY)

            points = []
            points.append(self.point)

            (features, status, error) = cv.CalcOpticalFlowPyrLK(
                self.frame0, self.frame1, 
                None, None, points, 
                (15, 15), 5, 
                (cv.CV_TERMCRIT_ITER | cv.CV_TERMCRIT_EPS, 20, 0.03),
                0) 

            # Put the good features in a list to be returned and draw them in a
            # circle on the original iplimage
            processed_features = []
            for i in range(len(features)):
                if status[i]: 
                    processed_features.append(features[i])

            if len(processed_features) == 0:
                self.point = None
                break
            elif len(processed_features) == 1:
                self.point = processed_features[0]
            else:
                self.point = processed_features[0]
                print "suddenly more points... weird"

            # Set frames up for next round
            if self.frame0.width == self.frame1.width and self.frame0.height == self.frame1.height:
                cv.Copy(self.frame1, self.frame0) 
            else:
                self.frame0 = cv.CreateImage ((frame1_org.width, frame1_org.height), cv.IPL_DEPTH_8U, 1)
                cv.Copy(self.frame1, self.frame0) 

            time.sleep(0.05)
            
        print 'Shutting down PointTracker'
