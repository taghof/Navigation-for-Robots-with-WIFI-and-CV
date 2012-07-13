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


    def request_control(self, caller):
        # print 'caller: ', caller, '\r'
        # print 'caller level: ', caller.level, '\r'
        # print 'RL: ', self.required_runlevel, '\r'
        clear_below = caller.level >= self.required_runlevel
      
        if clear_below:
            self.required_runlevel = caller.level
            for st in self.active_tasks:
                if st != caller and st.level < self.required_runlevel:
                    st.required_runlevel = 1000
                    st.control = False
                    if issubclass(st.__class__, CompoundTask):
                        st.request_control(self)
                else:
                    st.control = True
            return True
        else:
            return False

    def release_control(self, caller):

        if caller.level >= self.required_runlevel:
            self.required_runlevel = 0
            for st in self.active_tasks:
                caller.control = False
                if issubclass(st.__class__, CompoundTask) and st.required_runlevel == 1000:
                    st.required_runlevel = 0
                    st.release_control(self)

    def kill_tasks(self):
        self.lock.acquire()
        for task in self.active_tasks:
            print 'killing: ', task, '\r'
            task.stop()
        self.lock.release()        
       
    def stop(self):
        print "Shutting down " + str(self) + "\r"
        self.stopping = True
        self.kill_tasks()
        while len(self.active_tasks) > 0:
            time.sleep(0.2)

    def task_done(self, caller):
        print 'top level stopped: ', caller, '\r'
        self.lock.acquire()
        self.active_tasks.remove(caller)
        self.lock.release()

    def start_task(self, task):
        self.lock.acquire()
        if not self.stopping:
            task.parent = self
            self.active_tasks.append(task)
            threading.Thread(target=task.run).start() 

        self.lock.release()
        return task

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
        self.zaplock = self.interface.get_zaplock()
        self.video_sensor = self.drone.get_video_sensor()
        self.navdata_sensor = self.drone.get_navdata_sensor()
        self.wifi_sensor = self.drone.get_wifi_sensor()
        self.detector = self.drone.get_detector_sensor()
        self.subtasks = []
        self.dep_subtasks = []
        self.start_time = None
        self.loop_sleep = 0.5
        self.stopping = False
        
        self.state = settings.INIT
        self.control = False

    def move(self, r, p, g, y ):

        if self.control:
            self.interface.move(r, p, g, y, True )
            #print self.level, ' moving\r'
            return True
        elif self.parent.request_control(self):
            self.interface.move(r, p, g, y, True)
            #print self.level, ' moving\r'
            return True
        else:
            #print self.level, ' no move, blocked\r'
            return False

    def depsub_callback(self, caller):
        """ The standard callback method for dependent subtasks """
        print 'Ending dependent task', caller, '\r'

    def pre_loop(self):
        """ pre_loop

        This method should be overridden by subclasses, setup to be run immediately before the task
        main loop should be placed here.

        """
        pass

    def loop(self):
        """ loop

        This method should be overridden by subclasses. The loop method will be called continuously until
        self.state is STOPPING. If the subclass has no use for a main loop, be sure to make a call
        to self.stop().

        """
        pass

    def post_loop(self):
        """ post_loop

        This method should be overridden by subclasses. Cleaning up after the task is performed by this method.

        """
        pass

    def run(self):
        """ run
        
        the run() method is inherited from threading.Thread. All task follow the pattern
        of pre_loop, loop, post_loop. Run also starts any dependant subtasks.

        """
        #if not self.state == settings.STOPPING:
        self.state = settings.RUNNING
        if self.dep_subtasks is not None:
            for t in self.dep_subtasks:
                threading.Thread(target=t.run).start()

        self.start_time = time.time()
        print 'Starting ', self.__class__.__name__, '\r'
        self.pre_loop()

        while not self.state == settings.STOPPING:

            self.loop()
            time.sleep(self.loop_sleep)
        
        self.post_loop()
        print 'Ending ', self.__class__.__name__, ', ran for ', time.time() - self.start_time, ' seconds \r'
        if not self.parent is None and self.control:
            self.parent.release_control(self)
        self.done()
        self.state = settings.STOPPED

    def stop(self):
        """ stop
        
        A rather obvious method, stops all dependant subtasks and sets the self.state flag to STOPPING

        """
        while len(self.dep_subtasks) > 0:
            ds = self.dep_subtasks[0]
            ds.stop()
            #ds.join()
            self.dep_subtasks.remove(ds)
        
        
        if self.state == settings.RUNNING:
            self.state = settings.STOPPING

    def done(self, args=None):
        """ done

        Done is called as the last thing in the run method, it just calls the supplied
        callback method, should probably be refactored out.

        """
        if args is not None:
            self.callback(self, args)
        else:
            self.callback(self)

class MeasureDistanceTask(Task):
    """ MeasureDistanceTask

    This class uses the velocities from the drone navdata to estimate the travelled distance(a basic integration),
    the class utilizes a shared context to make other tasks aware of the calculated distance. The task is well suited as 
    a dependent subtasks of a moveTask.

    """
    def __init__(self, drone, callback, context, level=0):
        
        Task.__init__(self, drone, callback, context, level)
       
        self.dist_x = 0
        self.dist_y = 0
        self.last_time = None
        self.last_vx = 0
        self.last_vy = 0
        self.loop_sleep = 0.05

    def pre_loop(self):
        """ This method overrides the super method """

        # Set context[2] to (0.0) instead of None, set last_time to now
        self.context[2] = (self.dist_x, self.dist_y)
        self.last_time = time.time()

    def loop(self):
        """ This method overrides the super method to use self.measure to provide an integrated distance
        in the x and y directions"""
        self.measure()
        self.context[2] = (self.dist_x, self.dist_y)

    def post_loop(self):
        """ This method overrides the super method to clean up the shared context after use """

        self.context[2] = None
        print 'moved: (', self.dist_x, ', ', self.dist_y, ')\r'

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

    def reset(self):
        """ resets the distance travelled, so far this has been of little use """

        self.dist_x = 0
        self.dist_y = 0

class MoveTask(Task):
    """ MoveTask

    The MoveTask takes the drone in one of six directions(forwards, right, backwards, left, up and down) at a given pace.
    The task can be time or distance limited, but is also able to continue until stopped by another task

    """
    def __init__(self, drone, callback, context, timeout=10.0, distance=None, speed=0.2, direction=1, level=0):
        """ constructor which besides the three common task parameters also takes time, speed and direction """

        Task.__init__(self, drone, callback, context, level)
       
        if distance is not None:
            print 'should not happen in FollowTour\r'
            m = MeasureDistanceTask(drone, self.depsub_callback, context)
            self.dep_subtasks.append(m)
        
        
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

    def do_move(self):
        """ based on the value of self.direction and self.speed, use the command interface to move """
        if self.direction == 1:
            self.move(0, -self.speed, None, 0.0)
            #print 'moved forward\r'
        elif self.direction == 2 :
            self.move(self.speed, 0, None, 0.0)
            #print 'moved right\r'
        elif self.direction == 3:
            self.move(0, self.speed, None, 0.0)
            #print 'moved backward\r'
        elif self.direction == 4:
            self.move(-self.speed, 0, None, 0.0)
            #print 'moved left\r'
        elif self.direction == 5:
            self.move(None, None, self.speed, 0.0)
            #print 'moved up\r'
        elif self.direction == 6:
            self.move(None, None, -self.speed, 0.0)
            #print 'moved down\r'
        else:
            self.move(0,0,0,0)

    def pre_loop(self):
        """ Super override, starts the stop-timer if one is present and then uses the move method. """
        if self.time is not None:
            self.timer = threading.Timer(self.time, self.stop)
            self.timer.start()

    def loop(self):
        """ Super override, checks if the given distance has been travelled. """
        if self.parent.request_control(self):
            self.do_move()
        # should be fixed to use the euclidian distance
        if self.distance is not None and self.context[2] is not None and (math.fabs(self.context[2][0]) >= self.distance or math.fabs(self.context[2][1]) >= self.distance):
            print 'stopped by condition\r' 
            self.stop()
    
    def post_loop(self):
        """ Super override, stopping the drone after the task has been stopped. """
        self.move(0,0,0,0)
        #time.sleep(2.0)

class TakeoffTask(Task):
    """ TakeoffTask

    Basically sends the takeoff command to the drone and waits for a given time

    """
    def __init__(self, drone, callback, context, wait=7.0, level=0):
        """ One additional parameter; the time to wait before ending the task """
        Task.__init__(self, drone, callback, context, level)
        self.wait = float(wait)

    def pre_loop(self):
        """ Super override, only the pre_loop is necessary for this task. We must remember to call self.stop(). """
        
        pass
    
    def loop(self):
        control = self.parent.request_control(self)
        if control:
            self.interface.take_off()
            time.sleep(self.wait)
            self.stop()

class LandTask(Task):
    """ LandTask

    The LandTask sends the land command to the drone via the control interface and 
    the waits for a given time to end

    """
    def __init__(self, drone, callback, context, wait=5.0, level=0):
        """ The constructor takes one extra parameter, the time to wait before ending. """
        Task.__init__(self, drone, callback, context, level)
        self.wait = float(wait)

    def pre_loop(self):
        """ Like in the TakeoffTask a main loop is unnecessary, the entire task is carried out here. """
        self.interface.land()
        time.sleep(self.wait)
        self.stop()

class TestTask(Task):
    """ LandTask

    The LandTask sends the land command to the drone via the control interface and 
    the waits for a given time to end

    """
    def __init__(self, drone, callback, context, wait=0.0, timeout=0.0, level=0):
        """ The constructor takes one extra parameter, the time to wait before ending. """
        Task.__init__(self, drone, callback, context, level)
        self.wait = float(wait)
        self.timeout = float(timeout)

    def pre_loop(self):
        """ Like in the TakeoffTask a main loop is unnecessary, the entire task is carried out here. """

        if self.wait > 0.0:
            time.sleep(self.wait)

        if self.timeout > 0.0:
            threading.Timer(float(self.timeout), self.stop).start()
        self.reps = 10

    def loop(self):
        if self.reps > 0:
            ran = random.randint(1, 10)
            if ran == 1:
                if self.control:
                    self.parent.release_control(self)
                    print self.level, ' released control\r'
                    time.sleep(2)
            else:
                moved = self.move(1,1,1,1)
                if moved:
                    self.reps -= 1
        else:
            self.stop()

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

    def get_point(self):
        """ returns the positions of the point currently tracked, only relevant for some subtasks. """
        return self.point

    def pre_loop(self):
        self.current_pos = None
        self.timers = []
        if self.timeout > 0.0:
            threading.Timer(float(self.timeout), self.stop).start()
              
        self.tracker = utils.PointTracker(self.drone)
        self.source_method = self.tracker.track
        
        psi = self.navdata_sensor.get_data().get(0, dict()).get('psi', 0)
        self.set_point_psi = psi + self.psi_offset
        self.set_point_alt = 1550.0
        self.recover_alt = 1800

    def loop(self):
        
        if self.mode == 'detect':
            print 'detecting'
            self.settled = False
            if self.control: 
                self.parent.release_control(self)
                self.control = False

            pos = self.detector.points #bd.detect_position(img)
            if pos is not None:
                for p in pos:
                     if self.target_position.color == p[2]:
                         self.current_pos = p
                         print 'begin tracking\r'
                         self.mode = 'track'
                         self.move(0, 0, 0, 0)
                         self.tracker.init((p[0], p[1]), p[3])

                self.t1 = time.time()
           
        elif self.mode == 'track':
            
            powers = self.update()
            if powers is not None and self.parent.request_control(self):
                # check if we are within error limits
                #print 'xy_error: ', self.last_errors.get_avg(), ' (20), alt_error: ', self.error_alt, ' (20), psi_error: ', self.error_psi, ' (+/-0.5)\r'
                psi = self.error_psi is not None and -0.5 < self.error_psi < 0.5
                last_errors = self.last_errors.get_avg() <= 20.0
                alt_errors = self.error_alt <= 20
                
                # print 'psi: ' , psi
                # print 'errors: ', last_errors
                # print 'alt errors: ', alt_errors
                
                if psi and last_errors and alt_errors: 
                    print 'Settled!'
                    self.settled = True
                else:
                    self.settled = False

                print 'settled: ', self.settled
                # Use the calculated PID output to actually move
                if powers[0] == powers[1] == powers[2] == powers[3] == 0.0:
                    self.interface.move(powers[0], powers[1], powers[2], powers[3], False)
                else:
                    self.interface.move(powers[0], powers[1], powers[2], powers[3], True)
      
            elif powers is None and self.parent.request_control(self):
                # try to recover
                print 'Lost track, trying to recover\r'
                self.mode = 'recover'

        elif self.mode == 'recover':
            print 'searching' 
            if self.navdata_sensor.get_data().get(0, dict()).get('altitude', 0) >= self.recover_alt:
                self.move(0.0, 0.0, 0.0, 0.0)
            else:
                self.move(0.0, 0.0, 0.2, 0.0)
          
            pos = self.detector.points
            if pos is not None:
                for p in pos:
                    if self.target_position is not None and self.target_position.color == p[2]:
                        print 'Correct position found, done recovering\r'
                        self.current_pos = p
                        self.tracker.init((p[0], p[1]), p[3])
                        self.mode = 'track'
                        self.t1 = time.time()
                        return
                    elif self.target_position is None:
                        print 'Some position found, done recovering\r'
                        self.tracker.init((p[0], p[1]), p[3])
                        self.current_pos = p
                        self.mode = 'track'
                        self.t1 = time.time()
                        return
         

    def post_loop(self):
        # remember to cancel timers and to put the vehicle in hover mode after moving
        for t in self.timers:
            t.cancel()
                
        self.context[0] = None
        self.interface.move(0, 0, 0, 0, False)

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
            #raw_input('Please press return to continue...\n')
       
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
        self.loop_sleep = 0.0001

        self.parent = None
        self.required_runlevel = 0
        self.control = False

    def request_control(self, caller):
        # demand from above
        if caller == self.parent:
            self.control = False
            if self.level < self.parent.required_runlevel:
                self.required_runlevel = 1000
                for st in self.subtasks:
                    st.control = False
                    if issubclass(st.__class__, CompoundTask):
                        st.request_control(self)
            return True

        # call from below
        else:
            clear_below = caller.level >= self.required_runlevel
            if not self.control:
                clear_above = self.parent.request_control(self)
            else:
                clear_above = True

            if clear_below and clear_above:
                self.required_runlevel = caller.level
                for st in self.subtasks:
                    if st != caller:
                        st.control = False
                        if issubclass(st.__class__, CompoundTask):
                            st.request_control(self)
                    else:
                        st.control = True
                return True
            else:
                return False

    def release_control(self, caller):
        if caller == self.parent:
            if self.required_runlevel == 1000:
               self.required_runlevel = 0
               for st in self.subtasks:
                   caller.control = False
                   if issubclass(st.__class__, CompoundTask):
                       st.required_runlevel
                       st.release_control(self)

        elif caller.level >= self.required_runlevel:
            for st in self.subtasks:
                caller.control = False
                if issubclass(st.__class__, CompoundTask):
                    st.required_runlevel
                    st.release_control(self)

            self.required_runlevel = 0
            self.parent.release_control(self)

    def add_subtasks(self, tasks):
        for t in tasks:
             t.parent = self
             t.drone = self.drone
             if t.callback is None:
                 t.callback = self.sub_callback
             t.context = self.context
        self.subtasks.extend(tasks)

    def remove_subtask(self, t):
        print 'removing\r'
        if t in self.subtasks:
            self.subtasks.remove(t)

    def sub_callback(self, caller):
        """ This method can be overridden if a subclass wishes for processing to happen when subtasks finish """
        pass
    
    def stop(self, ty=None):
        """ If the stop method is supplied with a type parameter all subtasks of this type will be terminated, else
        all subtasks will terminated and thus the compound task itself will end.
        """
        if ty is not None:
            for t in self.subtasks:
                if isinstance(t, ty):
                    t.stop()
                elif isinstance(t, CompoundTask):
                    t.stop(ty)
        else:
            self.state = settings.STOPPING
            for t in self.subtasks:
                t.stop()

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
        self.current_subtask = None
       
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

    def pre_loop(self):
        threading.Thread(target=self.starter).start()

    def loop(self):
        """ Super override, if the list of subtasks is not empty start next task, wait for it to complete 
        and then remove it from subtasks list. If subtasks list is empty call stop() and terminate. 
        """
        pass

       
    def starter(self):
         for t in self.subtasks:
            if self.state == settings.RUNNING:
                print self.state, '\r'
                self.current_subtask = t
                th = threading.Thread(target=t.run)
                th.start()
                th.join()

         self.state = settings.STOPPING

   
class ParCompoundTask(CompoundTask):

    def __init__(self, drone, callback, context, level=0):
        CompoundTask.__init__(self, drone, callback, context, level)
        self.subtasks = []
        self.threads = []


    def stop(self, ty=None):
        """ If the stop method is supplied with a type parameter all subtasks of this type will be terminated, else
        all subtasks will terminated and thus the compound task itself will end.
        """
        if ty is not None:
            for t in self.subtasks:
                if isinstance(t, ty):
                    t.stop()
                elif isinstance(t, CompoundTask):
                    t.stop(ty)
        else:
            for t in self.subtasks:
                print 'stopping: ', t, '\r' 
                t.stop()

    def set_conf_1(self):
        """ Sets a specific list of subtasks """
        task1 = SeqCompoundTask(drone, self.sub_callback, self.context)
        task1.set_conf_2()
        task2 = SeqCompoundTask(drone, self.sub_callback, self.context)
        task1.set_conf_3()
        self.subtasks = [task1, task2]
       
    def pre_loop(self):
        """ Super override, start all subtasks to run parallel, perhaps some compatibilty check 
        between subtasks should be performed 
        """
        for t in self.subtasks:
            th = threading.Thread(target=t.run)
            th.start()
            self.threads.append(th)

    def loop(self):
        """ Super override, check if any subtasks has completed, if so remove from subtask list. 
        If subtasks list is empty call stop() and terminate.
        """
        
        for t in self.threads:
            if t.is_alive():
                return

        self.state = settings.STOPPING


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

    def loop(self):

        if self.h.settled:
            print 'derp looping'
            self.setup_next_segment()
           
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
            # self.m.set_mode(self.angles[self.current_segment])
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
        self.m.dep_subtasks.append(MeasureDistanceTask(self.p.drone, self.p.sub_callback, self.p.context))
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
        self.loop_sleep = 0.01
        self.current_silhouet = None

    def pre_loop(self):
        self.detector = self.drone.get_detector_sensor()

    def loop(self):
        silhouets = self.detector.silhouets

        if len(silhouets) > 0 :
           for s in silhouets:
            (xpos, ypos, width, height) = s
            if width*height > 500:
                print 'AVOIDING!!!\r'
                self.current_silhouet = s
                self.move(0.0, 0.0, 0.5, 0.0)
               
        elif len(silhouets) < 1 and self.current_silhouet is not None:
            print 'Blob avoided...\r'
            self.current_silhouet = None
            self.move(0.0, 0.0, 0.0, 0.0)
            self.parent.release_control(self)
            

def get_all_tasks():
    """ returns a list of all the subtasks extending Task """
    res = globals()['Task'].__subclasses__()
    res.extend(globals()['CompoundTask'].__subclasses__())
    res.extend(globals()['SeqCompoundTask'].__subclasses__())
    res.extend(globals()['ParCompoundTask'].__subclasses__())
    return res

