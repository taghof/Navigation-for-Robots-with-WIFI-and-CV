import sys
import time
import threading
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
        self.set_point = 0.0

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
        if self.set_point == 0.0:
            normed_setpoint = 
            self.set_point = (360+(current_value + self.degrees))%360
            print "moving to: " + str(self.set_point) + "\r" 

        # calculate the current error, must be between -180 and 180
        self.error = (360 + self.set_point - current_value)%360
        if self.error > 180:
            error = self.error - 360

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

    def getPoint(self):
        return self.set_point

    def getError(self):
        return self.error

    def getIntegrator(self):
        return self.Integrator

    def getDerivator(self):
        return self.Derivator

class DiscardingQueue(object):


    def __init__(self, max_size):
        self.max_size = max_size
        self.q = deque()
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
