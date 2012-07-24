""" The tasks module contains the definition of the base Task class and its subclasses

classes:
Task                -- The base Task class, defines the basic task flow(pre_loop, loop, post_loop)
NoneTask            -- Test task which does nothing whatsoever
MeasureDistanceTask -- A task for measuring distance travelled
MoveTask            -- Simple move task which moves the robot in a given direction for a given time
TakeoffTask         -- Takes the robot off the ground
LandTask            -- Lands the robot
SearchMarkTask      -- Search the camera feed for a given mark
SearchTask          -- Search the camera feed for a red blob
KeepDirTask         -- Uses the robot navdata to keep the direction(not precise due to sensor drift)
HoverTrackTask      -- When presented with mark/blob coordinates, track the point and hover above it(PID controller)
CompoundTask        -- Base class for the compound(container) tasks
SeqCompoundTask     -- A container task which starts a list of subclasses in a sequential manner
ParCompoundTask     -- A container task which starts a list of subclasses in a parallel manner
FollowTourTask      -- A SeqCompoundTask subclass, reads a map, creates a list of subtasks based on the map and executes the subtasks(ie. follows a tour)

Functions:
get_all_tasks()     -- Returns a list of all Task subclasses

"""
from __future__ import with_statement
import threading
import datetime
import math
import time
import blobdetect as bd
import utils
import settings
import cv2
import cv2.cv as cv
import map
import os
import pickle
import Gnuplot, Gnuplot.funcutils
import pdb
import random


""" Context format : ['point of blob', root task reference, currect distance travelled ] """

d2r = (math.pi/180.0) # ratio for switching from degrees to radians

class TaskManager(object):    

    def __init__(self, drone):
        self.drone = drone
        self.control_interface = drone.get_interface()
        self.stopping = False
        self.active_tasks = []
        self.lock = threading.Lock()
        self.required_runlevel = 0

    def start(self):
        threading.Thread(target=self.runner).start()

    def runner(self):
       
        while not self.stopping:
            # for t in self.active_tasks:
            #     print t.level
            # print '************'
       
            for t in self.active_tasks:
                if t.domove():
                    break

    def kill_tasks(self):
        self.lock.acquire()
        while len(self.active_tasks) > 0:
            t = self.active_tasks.pop()
            print 'killing: ', t
            t.stop()
        self.lock.release()        
       
    def stop(self):
        print "Shutting down " + str(self) + "\r"
        self.stopping = True
        self.kill_tasks()
       
    def task_done(self, caller):
        print 'top level stopped: ', caller, '\r'
        if caller in self.active_tasks:
            self.active_tasks.remove(caller)

    def start_task(self, task):
        self.lock.acquire()
        if not self.stopping:
            task.parent = self
            task.init()
            self.active_tasks.append(task)
            self.active_tasks.sort(key=lambda x: x.level, reverse=False)
        self.lock.release()

    def start_task_num(self, num):
        if num == 1:
            t = SeqCompoundTask(self.drone, self.task_done, None)
            t.set_conf_1()
            self.start_task(t)
        elif num == 5:
            t = SeqCompoundTask(self.drone, self.task_done, None)
            t.set_conf_5()
            self.start_task(t)
        elif num == 6:
            t = FollowTourTask(self.drone, self.task_done, None)
            self.start_task(t)
        elif num == 3:
            t = None#indsaet thomas' task her
            #self.start_task(t)
        else:
            return

class Task(object):
    """ The base Task

    The Task class sets up the generic task behaviour. It sets the local references to
    receivers and control interface in the constructor and defines the task flow via the run() 
    method. Subclasses should only need to overwrite one or more of: self.pre_loop(), self.loop() 
    and self.post_loop().

    """

    def __init__(self, drone, callback, context, level):
        """ Constructor 

        The contructor takes references to the drone, a callback method and a context(a list).
        The drone references is used to gain access to receivers and control interface. In this base 
        subtasks and dependant subtasks are left as empty lists to be overridden.
        
        """
        self.parent = None
        self.drone = drone
        self.callback = callback
        if context is None:
            self.context = [None, self, None, None]
        else:
            self.context = context

        self.level = level
        self.interface = drone.get_interface()
        self.video_sensor = self.drone.get_video_sensor()
        self.navdata_sensor = self.drone.get_navdata_sensor()
        self.wifi_sensor = self.drone.get_wifi_sensor()
        self.detector = self.drone.get_detector_sensor()
        self.start_time = None
        self.active = True

    def init(self):
        pass

    def stop(self):
        print 'stopping: ', self, '\r' 
        self.active = False
        self.done()

    def domove(self):
        pass
       
    def done(self, args=None):
        """ done

        Done is called as the last thing in the run method, it just calls the supplied
        callback method, should probably be refactored out.

        """
        if args is not None:
            self.callback(self, args)
        else:
            self.callback(self)

class MoveTask(Task):
    """ MoveTask

    The MoveTask takes the drone in one of six directions(forwards, right, backwards, left, up and down) at a given pace.
    The task can be time or distance limited, but is also able to continue until stopped by another task

    """
    def __init__(self, drone, callback, context, timeout=10.0, distance=None, speed=0.2, direction=1, level=0):
        """ constructor which besides the three common task parameters also takes time, speed and direction """

        Task.__init__(self, drone, callback, context, level)
        
        if timeout is not None:
            self.time = float(timeout)
        else:
            self.time = None

        if distance is not None:
            self.distance = float(distance)
        else:
            self.distance = None

        if speed is not None:
            self.speed = float(speed)
        else:
            self.speed = None

        if direction is not None:
            self.direction = int(direction)        
        else:
            self.direction = int(direction)        

    def domove(self):
        print 'moving'
        if self.distance is not None and self.context[2] is not None and (math.fabs(self.context[2][0]) >= self.distance or math.fabs(self.context[2][1]) >= self.distance):
            print 'stopped by condition\r' 
            self.stop()
            return False
        else:
             if self.direction == 1:
                 self.interface.move(0, -self.speed, None, 0.0, True)
                 return True
            #print 'moved forward\r'
             elif self.direction == 2 :
                 self.move(self.speed, 0, None, 0.0, True)
                 return True
            #print 'moved right\r'
             elif self.direction == 3:
                 self.move(0, self.speed, None, 0.0, True)
                 return True
            #print 'moved backward\r'
             elif self.direction == 4:
                 self.move(-self.speed, 0, None, 0.0, True)
                 return True
            #print 'moved left\r'
             elif self.direction == 5:
                 self.move(None, None, self.speed, 0.0, True)
                 return True
            #print 'moved up\r'
             elif self.direction == 6:
                 self.move(None, None, -self.speed, 0.0, True)
                 return True
            #print 'moved down\r'
             else:
                 self.move(0,0,0,0, True)
                 return True

    def init(self):
        """ Super override, starts the stop-timer if one is present and then uses the move method. """
        if self.time is not None:
            self.timer = threading.Timer(self.time, self.stop)
            self.timer.start()

class TakeoffTask(Task):
    """ TakeoffTask

    Basically sends the takeoff command to the drone and waits for a given time

    """
    def __init__(self, drone, callback, context, wait=7.0, level=0):
        """ One additional parameter; the time to wait before ending the task """
        Task.__init__(self, drone, callback, context, level)
        self.wait = float(wait)

    def domove(self):
        self.interface.take_off()
        time.sleep(self.wait)
        self.stop()
        return True

class LandTask(Task):
    """ LandTask

    The LandTask sends the land command to the drone via the control interface and 
    the waits for a given time to end

    """
    def __init__(self, drone, callback, context, wait=5.0, level=0):
        """ The constructor takes one extra parameter, the time to wait before ending. """
        Task.__init__(self, drone, callback, context, level)
        self.wait = float(wait)

    def domove(self):
        self.interface.land()
        time.sleep(self.wait)
        self.stop()
        return True

class TestTask(Task):
    """ TestTask

    """
    def __init__(self, drone, callback, context, wait=0.0, timeout=0.0, level=0, reps=10000):
        """ The constructor takes one extra parameter, the time to wait before ending. """
        Task.__init__(self, drone, callback, context, level)
        self.wait = float(wait)
        self.timeout = float(timeout)
        self.reps = int(reps)

    def init(self):
        """ Like in the TakeoffTask a main loop is unnecessary, the entire task is carried out here. """

        if self.wait > 0.0:
            time.sleep(self.wait)

        if self.timeout > 0.0:
            threading.Timer(float(self.timeout), self.stop).start()

    def domove(self):

        if self.reps > 0:
            ran = random.randint(1, 10)
            if ran == 11:
                return False
            else:
                print 'test domove(): ', self.level
                self.interface.move(1,1,1,1,True)
                self.reps -= 1
                return True
        else:
            self.stop()
            return False

class HoverTrackTask(Task):
    """
    Discrete PID control
    """

    def __init__(self, drone, callback, context, time_out=-1.0, mode='detect', level=0):
        Task.__init__(self, drone, callback, context, level)
        self.drone.interface.zap(1)
        self.tracker = None
        self.verbose = False
        self.mode = mode
        print type(time_out)
        self.timeout = float(time_out)
        self.settled = False

        # variables used in calculating the PID output
        self.Kp=2.0
        self.Ki=0.1
        self.Kd=0.75

        self.Derivator_x = 0
        self.Derivator_y = 0
        self.Derivator_psi = 0
        self.Derivator_alt = 0

        self.Integrator_x = 0
        self.Integrator_y = 0
        self.Integrator_psi = 0
        self.Integrator_alt = 0
        
        self.Integrator_max= 0.5
        self.Integrator_min= -0.5

        self.center = (88, 72)

        # we can never be more than 88 or 72 pixels from our target
        self.max_error_x = (4000*(math.tan(32*(math.pi/180))/88.0))*88.0#160.0 # 88
        self.max_error_y = (4000*(math.tan(26.18*(math.pi/180))/72.0))*72.0#120.0 # 72
        self.max_error_psi = 180.0
        self.max_error_alt = 2000.0
        self.psi_offset = 0
        self.loop_sleep = 0.05
        self.data_points = ([],[],[],[],[],[])
        self.point = None
        self.last_errors = utils.DiscardingQueue(20)
        self.target_position = drone.get_map().positions[1]
        self.tracker = utils.PointTracker(self.drone)
        self.source_method = self.tracker.track

    def get_point(self):
        """ returns the positions of the point currently tracked, only relevant for some subtasks. """
        return self.point

    def init(self):
        self.current_pos = None
        self.timers = []
        if self.timeout > 0.0:
            threading.Timer(float(self.timeout), self.stop).start()
                
        psi = self.navdata_sensor.get_data().get(0, dict()).get('psi', 0)
        self.set_point_psi = psi + self.psi_offset
        self.set_point_alt = 1550.0
        self.recover_alt = 1800
   
    def domove(self):
        
        if self.mode == 'detect':
            self.settled = False
            pos = self.detector.points
            if len(pos) > 0:
                for p in pos:
                     if self.target_position.color == p[2]:
                         self.current_pos = p
                         print 'begin tracking\r'
                         self.mode = 'track'
                         self.tracker.init((p[0], p[1]), p[3])
                         self.t1 = time.time()
                         return self.domove()
            else:
                return False
                            
        elif self.mode == 'track':
            powers = self.update()
            if powers is not None:
                # check if we are within error limits
                #print 'xy_error: ', self.last_errors.get_avg(), ' (20), alt_error: ', self.error_alt, ' (20), psi_error: ', self.error_psi, ' (+/-0.5)\r'
                psi = self.error_psi is not None and -0.5 < self.error_psi < 0.5
                last_errors = self.last_errors.get_avg() <= 20.0
                alt_errors = self.error_alt <= 20
                                
                if (psi and last_errors and alt_errors) or settings.TEST: 
                    print 'settled'
                    self.settled = True
                    return False
                else:
                    self.settled = False

                # Use the calculated PID output to actually move
                if powers[0] == powers[1] == powers[2] == powers[3] == 0.0:
                    self.interface.move(powers[0], powers[1], powers[2], powers[3], False)
                    return True
                else:
                    self.interface.move(powers[0], powers[1], powers[2], powers[3], True)
                    return True
            else:
                # try to recover
                print 'Lost track, trying to recover\r'
                self.mode = 'recover'
                return self.domove()

        elif self.mode == 'recover':
            pos = self.detector.points
            if len(pos) > 0:
                for p in pos:
                    if self.target_position is not None and self.target_position.color == p[2]:
                        print 'Correct position found, done recovering\r'
                        self.current_pos = p
                        self.tracker.init((p[0], p[1]), p[3])
                        self.mode = 'track'
                        self.t1 = time.time()
                        return self.domove()

                    elif self.target_position is None:
                        print 'Some position found, done recovering\r'
                        self.tracker.init((p[0], p[1]), p[3])
                        self.current_pos = p
                        self.mode = 'track'
                        self.t1 = time.time()
                        return self.domove()
            else:
                if self.navdata_sensor.get_data().get(0, dict()).get('altitude', 0) >= self.recover_alt:
                    self.interface.move(0.0, 0.0, 0.0, 0.0, True)
                    return True
                else:
                    self.interface.move(0.0, 0.0, 0.2, 0.0, True)
                    return True
    
    def stop(self):
        Task.stop(self)
        # remember to cancel timers and to put the vehicle in hover mode after moving
        for t in self.timers:
            t.cancel()
                
        self.context[0] = None

        if len(self.data_points[0]) > 0:
            xrange = (self.data_points[0][0], self.data_points[0][len(self.data_points[0])-1])
            g = Gnuplot.Gnuplot(persist=1)
            g('set terminal gif')
            g('set output "test.gif"')
            g.title('Error measurements')
            g.set_range('xrange', xrange)
            g.set_range('yrange', (-100, 100))
            g.xlabel('Time')
            g.ylabel('Error Distances')
            d1 = Gnuplot.Data(self.data_points[0], self.data_points[1], title='error x')
            d2 = Gnuplot.Data(self.data_points[0], self.data_points[2], title='error y')
            d3 = Gnuplot.Data(self.data_points[0], self.data_points[4], title='engine x', with_='lines')
            d4 = Gnuplot.Data(self.data_points[0], self.data_points[5], title='engine y', with_='lines')
            g.plot(d1, d2, d3, d4)
       
    def update(self):
        """
        Calculate PID output using the input method
        """
        
        currents = self.source_method()
        
        navdata = self.navdata_sensor.get_data()
        if navdata is None:
            return None
        
        pos = self.detector.points
        if len(pos) > 0:
            for p in pos:
                if p[2] == self.target_position.color:
                    #self.tracker.init((p[0], p[1]), p[3])
                    self.set_point_x = p[0]
                    self.set_point_y = p[1]
                elif self.target_position is None:
                    #self.tracker.init((p[0], p[1]), p[3])
                    self.set_point_x = p[0]
                    self.set_point_y = p[1]

        elif currents is not None:
            self.set_point_x = currents[0]
            self.set_point_y = currents[1]
        else:
            return None
        
        self.point = (self.set_point_x, self.set_point_y)
                   
        alt     = navdata.get(0, dict()).get('altitude', 0)
        angle_x = navdata.get(0, dict()).get('phi', 0)*d2r
        angle_y = navdata.get(0, dict()).get('theta', 0)*d2r 
        psi_angle = navdata.get(0, dict()).get('psi', 0)
        vx = navdata.get(0, dict()).get('vx', 0)
        vy = navdata.get(0, dict()).get('vy', 0)

        self.read_error_x_pixels = self.set_point_x - self.center[0]
        self.read_error_x_mm = (self.read_error_x_pixels*alt) * math.tan(32.0*d2r) / 88
        self.error_x = self.correct_angle(self.read_error_x_pixels, angle_x, alt)

        self.read_error_y_pixels = self.set_point_y - self.center[1]
        self.read_error_y_mm = (self.read_error_y_pixels * alt) * math.tan(26.18*d2r) / 72
        self.error_y = self.correct_angle(self.read_error_y_pixels, angle_y, alt)
       
        error_dist =  math.sqrt((self.error_y*self.error_y)+(self.error_x*self.error_x))
        self.last_errors.put(error_dist)
        if error_dist <= 50.0:
            self.error_psi = (360 + self.set_point_psi - psi_angle)%360
            if self.error_psi > 180:
                self.error_psi = self.error_psi - 360
        else:
            self.error_psi = 0
                    
        self.error_alt = self.set_point_alt - alt
        
        # self.data_points[0].append(time.time() - 1338000000.00)
        # self.data_points[1].append(self.error_x)
        # self.data_points[2].append(self.error_y)
        # self.data_points[3].append(error_dist)
        # self.data_points[4].append(0)
        # self.data_points[5].append(0)

        if error_dist < 10:
            return (0.0,0.0,0.0,0.0)

        # calculate the P term
        self.P_value_x = self.Kp * (self.error_x/self.max_error_x)
        self.P_value_y = self.Kp * (self.error_y/self.max_error_y)

        if self.error_psi is not None:
            self.P_value_psi = self.Kp * (self.error_psi/self.max_error_psi)
        else:
            self.P_value_psi = 0.0

        self.P_value_alt = self.Kp * (self.error_alt/self.max_error_alt)
       
        # calculate the I term, considering integrator max and min 
        if self.Ki > 0:
            self.Integrator_x = self.Integrator_x + (self.error_x/self.max_error_x)#+ self.error_x
            self.Integrator_y = self.Integrator_y + (self.error_y/self.max_error_y)#+ self.error_y
            
            self.Integrator_psi = self.Integrator_psi + (self.error_psi/self.max_error_psi)#+self.error_psi
            self.Integrator_alt = self.Integrator_alt + (self.error_alt/self.max_error_alt)#+self.error_alt

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

            if self.Integrator_alt > self.Integrator_max:
                self.Integrator_alt = self.Integrator_max
            elif self.Integrator_alt < self.Integrator_min:
                self.Integrator_alt = self.Integrator_min

            self.I_value_x = self.Integrator_x * self.Ki
            self.I_value_y = self.Integrator_y * self.Ki
            self.I_value_psi = self.Integrator_psi * self.Ki
            self.I_value_alt = self.Integrator_psi * self.Ki
        else:
            self.I_value_x, self.I_value_y, self.I_value_psi, self.I_value_alt = 0.0, 0.0, 0.0, 0.0
        
        # calculate the D term
        if self.Kd > 0:
            self.D_value_x = self.Kd * ((self.error_x - self.Derivator_x)/self.max_error_x)
            self.Derivator_x = self.error_x

            self.D_value_y = self.Kd * ((self.error_y - self.Derivator_y)/self.max_error_y)
            self.Derivator_y = self.error_y
            
            if not self.error_psi is None:
                self.D_value_psi = self.Kd * ((self.error_psi - self.Derivator_psi)/self.max_error_psi)
                self.Derivator_psi = self.error_psi
                
            self.D_value_alt = self.Kd * ((self.error_alt - self.Derivator_alt)/self.max_error_alt)
            self.Derivator_alt = self.error_alt

        else:
            self.D_value_x, self.D_value_y, self.D_value_psi, self.D_value_alt = 0.0, 0.0, 0.0, 0.0

        # Sum the term values into one PID value
        PID_x = self.P_value_x + self.I_value_x + self.D_value_x
        PID_y = self.P_value_y + self.I_value_y + self.D_value_y
        if not self.error_psi is None:
            PID_psi = self.P_value_psi + self.I_value_psi + self.D_value_psi
        else:
            PID_psi = 0

        PID_alt = self.P_value_alt + self.I_value_alt + self.D_value_alt

        # if PID_y < 0 and vx < 0:
        #     PID_y = PID_y - (vx/5000)/4
        #     print 'added: ', (vx/5000), ' to y-power\r'
        # if PID_y > 0 and vx > 0:
        #     PID_y = PID_y + (vx/5000)
        #     print 'added: ', (vx/5000), ' to y-power\r'

        # if PID_x < 0 and vy < 0:
        #     PID_x = PID_x - (vy/5000)/1.5
        #     #print 'added: ', (vy/5000), ' to x-power\r'
        # elif PID_x > 0 and vy > 0:
        #     PID_x = PID_x + (vy/5000)/1.5
            #print 'added: ', (vy/5000), ' to x-power\r'
        
        # print stuff for debugging purposes
        if self.verbose:
            print "Error_x_pixels: " + str(self.read_error_x_pixels) + "\tError_x_mm:\t" + str(self.error_x) + "\tError_angle_x: " + str(angle_x/d2r) + "\tEngine response_x: " + str(PID_x) + "\r"
            print "Error_y_pixels: " + str(self.read_error_y_pixels) + "\tError_y_mm:\t" + str(self.error_y) + "\tError_angle_y: " + str(angle_y/d2r) + "\tEngine response_y: " + str(PID_y) + "\r"
            print "Error_combined: " + str(error_dist) + "\r"
            print "Altitude:\t", alt, "\r"

        t = (time.time() - self.start_time)
        print 't: ', t
        self.data_points[0].append(t)
        self.data_points[1].append(self.error_x)
        self.data_points[2].append(self.error_y)
        self.data_points[3].append(error_dist)
        self.data_points[4].append(PID_x*100)
        self.data_points[5].append(PID_y*100)
       
        time_spend = (time.time() - self.t1)
        if (not time_spend > 2.0) or not error_dist <= 30:
            PID_psi = 0

        return (PID_x, PID_y, PID_alt, PID_psi*0.5)

    def set_turn(self, degrees):
        self.set_point_psi = (360+(self.set_point_psi + degrees))%360
        print 'turning ', degrees , '. to: ' + str(self.set_point_psi) + '\r' 


    def correct_angle(self, val, angle, alt):
        alpha = math.atan2(alt, abs(val));
        if (angle > 0 and val < 0) or (angle < 0 and angle > 0):
            return val * math.sin(alpha) / math.sin(alpha - abs(angle)) - alt * math.sin(angle)
	else:
            return val * math.sin(alpha) / math.cos(abs(angle)) - alt * math.sin(angle)

    def toggle_verbose(self):
        self.verbose = not self.verbose


class CompoundTask(Task):
    """ CompoundTask

    This is the base class for compound tasks, ie. tasks which manage a list of subtasks
    and stops when either all subtasks has completed or it is stop method is called.

    """
    def __init__(self, drone, callback, context, level= 0):
        """ The contructor will create a context if None was supplied, subtasks need the context for communicating """
        Task.__init__(self, drone, callback, context, level)
        self.subtasks = []
        self.parent = None

    def add_subtasks(self, tasks):
        for t in tasks:
             t.parent = self
             t.drone = self.drone
             if t.callback is None:
                 t.callback = self.sub_callback
             t.context = self.context
        self.subtasks.extend(tasks)
        self.subtasks.sort(key=lambda x: x.level, reverse=True)

    def remove_subtask(self, t):
        print 'removing\r'
        #if t in self.subtasks:
        self.subtasks.remove(t)
        self.subtasks.sort(key=lambda x: x.level, reverse=True)

    def sub_callback(self, caller):
        """ This method can be overridden if a subclass wishes for processing to happen when subtasks finish """
        pass
    
    def stop(self):
        """ If the stop method is supplied with a type parameter all subtasks of this type will be terminated, else
        all subtasks will terminated and thus the compound task itself will end.
        """
        for t in self.subtasks:
            t.stop()
        Task.stop(self)

    def done(self, args=None):
        """ Super extension, adds some print to better localise compound stop. """
        Task.done(self)
        print '*********************************************\r'
       
class SeqCompoundTask(CompoundTask):
    """ SeqCompoundTask

    A compound tasks which starts its subtasks one at a time and waits for its completions before
    starting another. Terminates when the lists of subtasks is empty.

    """
    def __init__(self, drone, callback, context, level=0):
        CompoundTask.__init__(self, drone, callback, context, level)
        self.current_subtask_index = 0
       
    def set_conf_1(self):
        """ Sets a specific list of subtasks """
        a = TakeoffTask(self.drone, self.sub_callback, self.context, 2) 
        h = HoverTrackTask(self.drone, self.sub_callback, self.context, -1, mode='recover')
        self.add_subtasks([a,h])

    def set_conf_3(self):
        """ Sets a specific list of subtasks """
        self.subtasks = [TakeoffTask(self.drone, self.sub_callback, self.context, 7),
                         MoveTask(self.drone, self.sub_callback, self.context, None, 0.1, 1)]

    def set_conf_4(self):
        """ Sets a specific list of subtasks """
        #To = TakeoffTask(self.drone, self.sub_callback, self.context, 7)
        # Mf = MoveTask(self.drone, self.sub_callback, self.context, -1, 0.15, 1)
        # La = LandTask(self.drone, self.sub_callback, self.context, 5.0)
        # Par = ParCompoundTask(self.drone, self.sub_callback, self.context)
        
        Se = SearchTask(self.drone, self.sub_callback, self.context) 
        Ho = HoverTrackTask(self.drone, self.sub_callback, self.context, time=None)
        Ho.psi_offset = 90

        # Ho.verbose = True
        # Par.subtasks = [Se, Ho]
        #b1 = MeasureDistanceTask(self.drone, self.sub_callback, self.context)
        #b = MoveTask(self.drone, self.sub_callback, self.context, 2.0, 0.2, 5)
        self.subtasks = [Se, Ho]

    def set_conf_5(self):
        """ Sets a specific list of subtasks """
        a = TakeoffTask(self.drone, self.sub_callback, self.context, 7)
        
        b = MoveTask(self.drone, self.sub_callback, self.context, None, 0.1, 1)
        b1 = MeasureDistanceTask(self.drone, None, self.context)
        b.dep_subtasks = [b1]

        c = MoveTask(self.drone, self.sub_callback, self.context, None, 0.1, 2)
        c1 = MeasureDistanceTask(self.drone, None, self.context)
        c.dep_subtasks = [c1]

        d = MoveTask(self.drone, self.sub_callback, self.context, None, 0.1, 3)
        d1 = MeasureDistanceTask(self.drone, None, self.context)
        d.dep_subtasks = [d1]

        e = MoveTask(self.drone, self.sub_callback, self.context, None, 0.1, 4)
        e1 = MeasureDistanceTask(self.drone, None, self.context)
        e.dep_subtasks = [e1]

        f = LandTask(self.drone, self.sub_callback, self.context, 5.0)
        self.subtasks = [b,e,d,c,f]

    def init(self):
        """ Super override, start all subtasks to run parallel, perhaps some compatibilty check 
        between subtasks should be performed 
        """
        for t in self.subtasks:
            t.init()

    def domove(self):
        if self.current_subtask_index < len(self.subtasks):
            if self.subtasks[self.current_subtask_index].active:
                return self.subtasks[self.current_subtask_index].domove()
            else:
                self.current_subtask_index += 1
                return self.domove()
        else:
            self.active = False
            self.done()
            return False

class ParCompoundTask(CompoundTask):

    def __init__(self, drone, callback, context, level=0):
        CompoundTask.__init__(self, drone, callback, context, level)
        self.subtasks = []
        self.threads = []
        
    def stop(self):
        """ If the stop method is supplied with a type parameter all subtasks of this type will be terminated, else
        all subtasks will terminated and thus the compound task itself will end.
        """
        for t in self.subtasks:
            t.stop()
        Task.stop(self)

    def set_conf_1(self):
        """ Sets a specific list of subtasks """
        task1 = SeqCompoundTask(drone, self.sub_callback, self.context)
        task1.set_conf_2()
        task2 = SeqCompoundTask(drone, self.sub_callback, self.context)
        task1.set_conf_3()
        self.add_subtasks = [task1, task2]
        
    def init(self):
        """ Super override, start all subtasks to run parallel, perhaps some compatibilty check 
        between subtasks should be performed 
        """
        for t in self.subtasks:
            t.init()

    def domove(self):
        print self.subtasks
        active = False
        for st in self.subtasks:
            if st.active:
                active = True
                if st.domove():
                    return True
        if not active:
            self.active = False
            self.done()
        return False

class FollowTourTask(SeqCompoundTask):
    """ FollowTourTask
    
    A task designed to make the drone follow a tour obtained from a map of points. 
    Based on the tour describtion the tasks creates the necessary subtasks.

    """
    def __init__(self, drone, callback, context, level=0):
        """ The constructor can be supplied with a map containing points and a tour """
        SeqCompoundTask.__init__(self, drone, callback, context, level)

        self.map = self.drone.get_map()
       
        # Tour and positions from the map
        self.tour = self.map.tour
        self.positions = self.map.positions
        self.state = 'hover'
        self.current_segment = 0
        # build subtasks
        self.add_subtasks(self.create_subtasks())

    def domove(self):
        retval = SeqCompoundTask.domove(self)
        if self.h.settled:
            print 'Next segment'
            self.setup_next_segment()
        return retval
           
    def setup_next_segment(self):
        if not self.current_segment < len(self.tour):
            self.p.stop()
            self.current_segment = 0
            self.h.target_position = self.tour[0][0]
            self.h.mode = 'recover'
            return

        if self.current_segment < len(self.tour):
            self.h.set_turn(self.angles[self.current_segment])
            self.h.target_position = self.tour[self.current_segment][1]
            self.h.settled = False
            self.h.mode = 'detect'
            print 'begin detection'
            self.current_segment += 1

    def create_subtasks(self):
        self.angles = []
        self.modifiers = []
        res = []

        self.to = TakeoffTask(self.drone, self.sub_callback, self.context, 2.0)
        self.to.level = 0

        self.la = LandTask(self.drone,self.sub_callback, self.context, 5)
        self.la.level = 0

        self.p = ParCompoundTask(self.drone, self.sub_callback, self.context)
        self.p.level = 0

        self.h = HoverTrackTask(self.p.drone, self.sub_callback, self.p.context, -1, mode='recover')
        self.h.target_position = self.tour[0][0]
        self.h.level = 1

        self.m = MoveTask(self.p.drone, self.p.sub_callback, self.p.context, None, None, 0.065, 1)
        self.m.level = 0
        
        self.p.add_subtasks([self.h, self.m])
        
        res.append(self.to)
        res.append(self.p)
        res.append(self.la)

        for i in range(len(self.tour)):

            if i+1 > len(self.tour)-1:
                turn_angle = 0
            else:
                current = self.tour[i]
                next = self.tour[i+1]

                x1 = current[1].x - current[0].x
                y1 = current[1].y - current[0].y
                
                x2 = next[1].x - next[0].x
                y2 = next[1].y - next[0].y
                
                dp = x1*x2 + y1*y2
                
                turn_angle = (math.atan2(y2,x2) - math.atan2(y1,x1))/d2r
           
            print 'turn angle: ',turn_angle, '\r'
            self.angles.append(turn_angle)
            self.modifiers.append(self.tour[i][2])
           
        return res

class AvoidTask(Task):
    """ AvoidTask
    
    A task designed to make the drone avoid an object by moving up.

    """
    def __init__(self, drone, callback, context, level=0):
        """ The constructor can be supplied with a map containing points and a tour """
        Task.__init__(self, drone, callback, context, level)
        self.level = 1
        self.current_silhouet = None
        self.detector = self.drone.get_detector_sensor()
        
    def init(self):
        self.current_silhouet = None

    def domove(self):
         silhouets = self.detector.silhouets
                    
         if len(silhouets) == 0 and self.current_silhouet is not None:
            print 'Blob avoided...\r'
            self.current_silhouet = None
            #self.move(0.0, 0.0, 0.0, 0.0)
            return False
         
         elif len(silhouets) == 0 :
             return False
         
         else:
             for s in silhouets:
                 (xpos, ypos, width, height) = s
                 if width*height > 500:
                     #print 'AVOIDING!!!'
                     self.current_silhouet = s
                     self.interface.move(0.0, 0.0, 0.5, 0.0, True)
                     return True
             return False
        

def get_all_tasks():
    """ returns a list of all the subtasks extending Task """
    res = globals()['Task'].__subclasses__()
    res.extend(globals()['CompoundTask'].__subclasses__())
    res.extend(globals()['SeqCompoundTask'].__subclasses__())
    res.extend(globals()['ParCompoundTask'].__subclasses__())
    return res

