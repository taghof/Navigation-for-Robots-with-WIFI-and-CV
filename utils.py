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

    def __init__(self, source_method, move_method, degrees, P=2.0, I=0.0, D=1.0, Derivator=0, Integrator=0, Integrator_max=500, Integrator_min=-500, stable_point=0.02):
        threading.Thread.__init__(self)
        self.source_method = source_method
        self.move_method = move_method
        self.degrees = degrees

        self.Kp=P
        self.Ki=I
        self.Kd=D
        self.Derivator=Derivator
        self.Integrator=Integrator
        self.Integrator_max=Integrator_max
        self.Integrator_min=Integrator_min
        
        current = self.source_method()
      
        self.stable_point = stable_point
        self.set_point = 0.0# current + degrees
        self.error=0.0
        self.max_pid = 0.0
        self.max_error = 0.0
        self.error_vals = DiscardingQueue(10)

    def run(self):
        while not self.is_stable():
            #current = self.source_method()
            power = self.update()
            self.move_method(power)

    def update(self):#,current_value):
        """
        Calculate PID output value for given reference input and feedback
        """
        current_value = self.source_method()
        if self.set_point == 0.0:
            self.set_point = current_value + self.degrees

        self.error = self.set_point - current_value
        if self.max_error == 0.0:
            self.max_error = self.error
        
        if self.error > self.max_error:
             self.error = self.max_error
        elif self.error < -self.max_error:
            self.error = -self.max_error

        self.P_value = self.Kp * self.error
        self.D_value = self.Kd * ( self.error - self.Derivator)
        self.Derivator = self.error
        
        self.Integrator = self.Integrator + self.error

        if self.Integrator > self.Integrator_max:
            self.Integrator = self.Integrator_max
        elif self.Integrator < self.Integrator_min:
            self.Integrator = self.Integrator_min

        self.I_value = self.Integrator * self.Ki
        
        PID = self.P_value + self.I_value + self.D_value
        
        print PID

        if self.max_pid == 0.0:
            self.max_pid = self.Kp*self.error + self.Ki*self.Integrator_max
            self.error_vals.put(PID/self.max_pid)
            return 1.0
        else:
            self.error_vals.put(PID/self.max_pid)
            time.sleep(0.1)
            return PID/self.max_pid

    def is_stable(self):
        """
        Will return True if the average of the last 10 PID vals is below
        a certain threshold
        """
        return self.error_vals.get_avg() < self.stable_point and self.max_pid > 0.0

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
