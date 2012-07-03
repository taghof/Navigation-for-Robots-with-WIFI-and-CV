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

""" Context format : ['point of blob', root task reference, currect distance travelled ] """

d2r = (math.pi/180.0) # ratio for switching from degrees to radians

class TaskManager(object):    

    def __init__(self, drone):
        self.drone = drone
        self.control_interface = drone.get_interface()
        self.stopping = False
        self.active_tasks = []
        self.lock = threading.Lock()
    
    def set_required_runlevel(caller, level):
        if caller.level >= self.required_runlevel and level <= caller.level:
            self.required_level = caller.level
            for t in self.subtasks:
                if t.level < level:
                    t.suppress()
                else:
                    t.de_suppress()

    def start(self):
        threading.Thread(target=self.runner).start() 

    def runner(self):
        while not self.stopping:
            self.activate()
            time.sleep(1.01)

    def activate(self, goal=None):
        self.active = True
        maximp = None
        for t in self.active_tasks:
            timp = t.get_importance(goal) 
            print t, ' : ', timp, '\r'
            if  maximp is None or timp > maximp[0]:
                maximp = [timp, t]
            elif t == maximp[0]:
                if t.level > maximp[1].level:
                    maximp = [timp, t]
        if maximp is not None:    
            maximp[1].activate()
            for t in self.active_tasks:
                if t != maximp[1] and t.active:
                    t.de_activate()
                
    def de_activate(self):
        self.active = False
        for t in self.active_tasks:
            t.de_activate()


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

    def task_done(self, caller):
        print 'top level stopped: ', caller, '\r'
        self.active_tasks.remove(caller)

    def start_task(self, task):
        self.lock.acquire()
        if not self.stopping:
            task.parent = self
            self.active_tasks.append(task)
            threading.Thread(target=task.run).start() 

        self.lock.release()
        return task

    def start_task_num(self, num):
        if num == 4:
            t = SeqCompoundTask(self.drone, self.task_done, None)
            t.set_conf_4()
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
        
        self.loop_sleep = 0.1
        self.stopping = False
        
        self.state = settings.INIT
        
        self.active = False
        self.level = 0

    def get_importance(self):
        return self.level

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
        self.state = settings.RUNNING
        if self.dep_subtasks is not None:
            for t in self.dep_subtasks:
                threading.Thread(target=t.run).start()

        t1 = time.time()
        print 'Starting ', self.__class__.__name__, '\r'
        self.pre_loop()

        while not self.state == settings.STOPPING:

            self.loop()
            time.sleep(self.loop_sleep)
        
        self.post_loop()
        print 'Ending ', self.__class__.__name__, ', ran for ', time.time() - t1, ' seconds \r'
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

    def de_activate(self):
        if self.active:
            print 'de_activating: ' , self, '\r'
            self.active = False
    
    def activate(self):
        if not self.active:
            print 'activating: ' , self, '\r'
            self.active = True

class NoneTask(Task):
    """ NoneTask

    Does nothing, could be replaced with the base Task class.

    """
    def __init__(self, drone, callback, context, level=0):
         """ Just calls the super contructor, a very boring task indeed """
         Task.__init__(self, drone, callback, context, level)

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

    def get_importance(self, goal=None):
        val = 2
        s = 0
        g = 0
        l = 0
       
        if self.detector.points is None:
            s += 1
        if goal is not None and goal=='move':
            g += 1
        
        if not self.interface.get_landed():
            l += 1

        return (g+s)/val and l 

    def move(self):
        """ based on the value of self.direction and self.speed, use the command interface to move """
        if self.direction == 1:
            self.interface.move(0, -self.speed, None, 0.0, True)
            #print 'moved forward\r'
        elif self.direction == 2 :
            self.interface.move(self.speed, 0, None, 0.0, True)
            #print 'moved right\r'
        elif self.direction == 3:
            self.interface.move(0, self.speed, None, 0.0, True)
            #print 'moved backward\r'
        elif self.direction == 4:
            self.interface.move(-self.speed, 0, None, 0.0, True)
            #print 'moved left\r'
        elif self.direction == 5:
            self.interface.move(None, None, self.speed, 0.0, True)
            #print 'moved up\r'
        elif self.direction == 6:
            self.interface.move(None, None, -self.speed, 0.0, True)
            #print 'moved down\r'
        else:
            self.interface.move(0,0,0,0,False)

    def pre_loop(self):
        """ Super override, starts the stop-timer if one is present and then uses the move method. """
        if self.time is not None:
            self.timer = threading.Timer(self.time, self.stop)
            self.timer.start()

    def loop(self):
        """ Super override, checks if the given distance has been travelled. """
        if self.active:
            self.move()

        # should be fixed to use the euclidian distance
        if self.distance is not None and self.context[2] is not None and (math.fabs(self.context[2][0]) >= self.distance or math.fabs(self.context[2][1]) >= self.distance):
            print 'stopped by condition\r' 
            self.stop()
    
    def post_loop(self):
        """ Super override, stopping the drone after the task has been stopped. """
        self.interface.move(0,0,0,None,False)
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
        if self.active:
            self.interface.take_off()
            time.sleep(self.wait)
            self.stop()

    def get_importance(self, goal=None):
        val = 3.0
        s = 0
        g = 0
        l = 0
       
        if self.detector.points is None:
            s += 1

        if goal is not None and goal=='takeoff':
            g += 1
        
        if self.interface.get_landed():
            l += 1
            
        print 'l: ', l, '\r'
        return (g+s+l)/val and l

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

    def get_importance(self, goal=None):
        val = 2
        s = 0
        g = 0
        l = 0
       
        if self.detector.silhouets is not None:
            s += 1
        if goal is not None and goal=='land':
            g += 1
        
        if not self.interface.get_landed():
            l += 1

        return (g+s)/val and l


class SearchMarkTask(Task):
    """ SearchMarkTask
    
    Compares images from the camera feed with a given set of reference images, if a match is made
    the coordinate is shared through the context and the task stops 

    """
    def __init__(self, drone, callback, context, markpics=None, level=0):
        """ Beyond the standard parameters, the SearchMarkTask can be instantiated with a list of reference images """
        Task.__init__(self, drone, callback, context, level)
        self.mark = []

        # if not supplied with reference images use some test images
        if markpics is None:
            self.mark.append(cv2.imread('./mark3e.png', 0))
            self.mark.append(cv2.imread('./mark3f.png', 0))
            self.mark.append(cv2.imread('./mark3g.png', 0))
            self.mark.append(cv2.imread('./mark3h.png', 0))
        else:
            self.mark = markpics

        self.loop_sleep = 0.05

    def loop(self):
        """ Super override, performs a matching and stops if a match is returned """
        matching = self.search_for_mark()
        if matching is not None:
            context[0] = matching[2]
            self.stop()

    def search_for_mark(self):
        """ This method filters the results from the matching module, so that only matches conforming to
        certain criterias is returned. The matching module compares SURF features from two images and use opencvs findHomology method
        to detect a homology between the two.
        """
        matching = None
        frame_org = self.video_sensor.get_data()
        frame = cv2.cvtColor(frame_org, cv.CV_RGB2GRAY)
        num = 0
       
        for m in self.mark:
            matching = matcher.match(m, frame)
            if matching is not None and matching[1] > num:
                num = matching[1]
                matching = matching
        if num:
            self.last_match_image = matching[0]

        if matching is not None and matching[1] >= 5:
            self.last_match_image = None
            return matching
        else:
            return None

class SearchTask(Task):
    """ SearchTask

    Searches the camera feed for red blobs of a certain size, if successful the coordinate is shared in the context
    and the task stops.

    """
    def __init__(self, drone, callback, context, delay=0.0, level=0):
        """ The constructor can be supplied with an additional delay parameter, to delay the start of the task """
        Task.__init__(self, drone, callback, context, level)
        self.blob = None
        self.loop_sleep = 0.05
        self.delay = float(delay)
        print 'delay: ', self.delay, '\r'

    def pre_loop(self):
        """ Super override, delays task execution if a delay is given """
        if self.delay > 0.0:
            time.sleep(self.delay)

    def loop(self):
        """ Super override, reads picture, detects red blob, shares and stops if successfull """
        img = self.video_sensor.get_data()
        self.blob = bd.detect_red_blob(img)
        if self.blob is not None:
            (xpos, ypos), (width, height) = position, size = self.blob
            if width*height > 15:
                print 'Blob found\r' #, stopping movetasks\r'
                # self.interface.move(0.0, 0.0, 0.0, 0.0, True)
                # self.context[1].stop(MoveTask)
                # self.context[0] = position
                self.stop()
            else:
                self.blob = None

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
        self.timeout = time_out
                
        # variables used in calculating the PID output
        self.Kp=2.0
        self.Ki=0.0
        self.Kd=0.75
        self.Derivator_x = 0
        self.Derivator_y = 0
        self.Derivator_psi = 0
        self.Derivator_alt = 0

        self.Integrator_x = 0
        self.Integrator_y = 0
        self.Integrator_psi = 0
        self.Integrator_alt = 0
        
        self.Integrator_max= 500
        self.Integrator_min= -500

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
        self.target_position = None

    def get_importance(self, goal=None):
        val = 3
        p = 0
        s = 0
        g = 0
        l = 0

        if self.detector.points is not None:
            p += 1
        if self.detector.silhouets is None:
            s += 1
        if goal is not None and goal=='hover':
            g += 1
        
        if not self.interface.get_landed():
            l += 1

        return (g+s)/val and l


    def get_point(self):
        """ returns the positions of the point currently tracked, only relevant for some subtasks. """
        return self.point

    def pre_loop(self):
        self.first = True
        self.current_pos = None
        self.timers = []
        if self.timeout > 0.0:
            self.timers.append(threading.Timer(self.timeout, self.stop))
              
        self.tracker = utils.PointTracker(self.drone.get_video_sensor(), self.drone.get_navdata_sensor())
        self.source_method = self.tracker.track
        
        psi = self.navdata_sensor.get_data().get(0, dict()).get('psi', 0)
        self.set_point_psi = psi + self.psi_offset
        self.set_point_alt = 1400.0


    def loop(self):
        
        if self.mode == 'detect':
            if self.first:
                self.first = False
                self.recover()
                return
            #print 'detecting\r'
            self.zaplock.acquire()
            self.interface.zap(1)
            img = self.video_sensor.get_data()
            while img.shape[1] != 176 and not self.state == settings.STOPPING:
                img = self.video_sensor.get_data()
            self.zaplock.release()
            pos = bd.detect_position(img)
           
            # we have a new blob
            if pos is not None:
                print self.target_position.color, '\r'
                print pos[2], '\r'

            if pos is not None and self.target_position.color == pos[2]:
                self.current_pos = pos
                print 'begin tracking\r'
                self.mode = 'track'
                if self.parent is not None:
                    self.parent.set_required_runlevel(self, 1)
                self.interface.move(0, 0, 0, 0, True)
                self.tracker.init((pos[0], pos[1]), img)
                print 'Hovering...\r'
                self.t1 = time.time()
                for t in self.timers: t.start()
           
        elif self.mode == 'track':
            self.interface.zap(1)
            powers = self.update()
            
            if powers is not None and self.active:
                # check if we are within error limits
                if self.error_psi is not None and -0.5 < self.error_psi < 0.5 and self.last_errors.get_avg() <= 20 and self.error_alt <= 20:
                    if not self.parent is None:
                        print 'begin detect\r'
                        self.mode = 'detect'
                        self.parent.set_required_runlevel(self, 0)
                        self.callback(self)
                        return
                    else:
                        self.stop()
                        return
                else:
                    print 'xy_error: ', self.last_errors.get_avg(), ' (20), alt_error: ', self.error_alt, ' (20), psi_error: ', self.error_psi, ' (+/-0.5)\r'
                # Use the calculated PID output to actually move
                if powers[0] == powers[1] == powers[2] == powers[3] == 0.0:
                    self.interface.move(powers[0], powers[1], powers[2], powers[3], False)
                else:
                    self.interface.move(powers[0], powers[1], powers[2], powers[3], True)
      
            elif powers is None and not self.suppressed:
                # try to recover
                self.recover()
        
     
    def post_loop(self):
        # remember to cancel timers and to put the vehicle in hover mode after moving
        for t in self.timers:
            t.cancel()
                
        self.context[0] = None
        self.interface.move(0, 0, 0, 0, False)

        # if len(self.data_points[0]) > 0:
        #     xrange = (self.data_points[0][0], self.data_points[0][len(self.data_points[0])-1])
        #     g = Gnuplot.Gnuplot(persist=1)
        #     g('set terminal gif')
        #     g('set output "test.gif"')
        #     g.title('Error measurements')
        #     g.set_range('xrange', xrange)
        #     g.set_range('yrange', (-100, 100))
        #     g.xlabel('Time')
        #     g.ylabel('Error Distances')
        #     d1 = Gnuplot.Data(self.data_points[0], self.data_points[1], title='error x')
        #     d2 = Gnuplot.Data(self.data_points[0], self.data_points[2], title='error y')
        #     d3 = Gnuplot.Data(self.data_points[0], self.data_points[4], title='engine x', with_='lines')
        #     d4 = Gnuplot.Data(self.data_points[0], self.data_points[5], title='engine y', with_='lines')
        #     g.plot(d1, d2, d3, d4)
            #raw_input('Please press return to continue...\n')

    def recover(self):
        print 'Lost track, trying to recover\r'
        self.interface.move(0.0, 0.0, 0.0, 0.0, True)
        time.sleep(1.0)
        self.interface.move(0.0, 0.0, 0.2, 0.0, True)
        while not self.state == settings.STOPPING and self.active:
            print 'searching...\r'
            if self.navdata_sensor.get_data().get(0, dict()).get('altitude', 0) >= 1500:
                self.interface.move(0.0, 0.0, 0.0, 0.0, True)
            else:
                self.interface.move(0.0, 0.0, 0.2, 0.0, True)
            self.zaplock.acquire()
            self.interface.zap(1)
            img = self.video_sensor.get_data()
            while img.shape[1] != 176 and not self.state == settings.STOPPING:
                img = self.video_sensor.get_data()
            self.zaplock.release()
            pos = bd.detect_position(img)
            if pos is not None and self.target_position.color == pos[2]:
                print 'Position found, done recovering\r'
                self.current_pos = pos
                self.tracker.init((pos[0], pos[1]), img)
                return

    def update(self):
        """
        Calculate PID output using the input method
        """
        
        currents = self.source_method()
        
        # if currents is None:
        #     print 'Currents was None\r'
        #     return None

        self.zaplock.acquire()
        self.interface.zap(1)
        tries=0
        img = self.video_sensor.get_data()
        pos = None
        while img.shape[1] != 176 and not self.state == settings.STOPPING:
            self.interface.zap(1)
            img = self.video_sensor.get_data()
        self.zaplock.release()

        pos = bd.detect_position(img)
        if pos is not None and currents is not None:
            self.set_point_x = pos[0]
            self.set_point_y = pos[1]
        elif currents is not None and currents[0] is not None:
            self.set_point_x = currents[0]
            self.set_point_y = currents[1]
        else:
            return None
        
        self.point = (self.set_point_x, self.set_point_y)
        # print 'point: ', self.point, '\r'
        # self.point = (pos[0], pos[1])
        # print 'point: ', self.point, '\r'
        # print '******\r'
        #
        alt = currents[5]
        if alt == 0:
            alt = 150
        angle_x = currents[2]*d2r
        angle_y = currents[3]*d2r
        psi_angle = currents[4]

        vx = currents[6]
        vy = currents[7]

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
            self.error_psi = None
                    
        self.error_alt = self.set_point_alt - alt
        
        self.data_points[0].append(time.time() - 1338000000.00)
        self.data_points[1].append(self.error_x)
        self.data_points[2].append(self.error_y)
        self.data_points[3].append(error_dist)
        self.data_points[4].append(0)
        self.data_points[5].append(0)

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
            self.Integrator_x = self.Integrator_x + self.error_x
            self.Integrator_y = self.Integrator_y + self.error_y
            self.Integrator_psi = self.Integrator_psi + self.error_psi
            self.Integrator_alt = self.Integrator_alt + self.error_alt

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

        if PID_y < 0 and vx < 0:
            PID_y = PID_y - (vx/5000)/4
            print 'added: ', (vx/5000), ' to y-power\r'
        if PID_y > 0 and vx > 0:
            PID_y = PID_y + (vx/5000)
            print 'added: ', (vx/5000), ' to y-power\r'

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

        time_spend = (time.time() - self.t1)
        # self.data_points[0].append(time_spend)
        # self.data_points[1].append(self.error_x)
        # self.data_points[2].append(self.error_y)
        # self.data_points[3].append(error_dist)
        # self.data_points[4].append(PID_x*100)
        # self.data_points[5].append(PID_y*100)
        

       
        time_spend = (time.time() - self.t1)
        if (not time_spend > 2.0) or not error_dist <= 50:
            PID_psi = 0

        return (PID_x, PID_y, PID_alt, PID_psi)

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
        self.minimum_level = 0
        self.active = False

    def set_required_runlevel(caller, level):
        if caller.level >= self.required_runlevel and level <= caller.level:
            self.required_level = caller.level
            for t in self.subtasks:
                if t.level < level:
                    t.suppress()
                else:
                    t.de_suppress()
        
    

    def de_activate(self):
        self.activate = False
        for t in self.subtasks:
            t.de_activate()

    def add_subtask(self, task, index=None):
        task.parent = self
        task.drone = self.drone
        if task.callback is None:
            task.callback = self.sub_callback
        task.context = self.context
        self.subtasks.append(task)

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

            # stopped = False
            # while not stopped:
            #     stopped = True
            #     for t in self.subtasks:
            #         if not (t.state == settings.STOPPED or t.state == settings.INIT):
            #             # print t, ' not dead!\r'
            #             # if t.state == settings.STOPPED:
            #             #     print 'settings.STOPPED\r'
            #             # elif t.state == settings.INIT:
            #             #     print 'settings.INIT\r'
            #             # elif t.state == settings.RUNNING:
            #             #     print 'settings.RUNNING\r'
            #             # else:
            #             #     print t.state, '\r'
            #             stopped = False

            # if self.state == settings.RUNNING:
            #     self.state = settings.STOPPING

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
        self.subtasks = [SearchTask(self.drone, self.sub_callback, self.context), 
                         utils.PIDxy(self.drone, self.sub_callback, self.context)] 

    def set_conf_2(self):
        """ Sets a specific list of subtasks """
        self.subtasks = [#TakeoffTask(self.drone, self.sub_callback, self.context, 5.0), 
            SearchTask(self.drone, self.sub_callback, self.context), 
            HoverTrackTask(self.drone, self.sub_callback, self.context),
            LandTask(self.drone, self.sub_callback, self.context, 5.0)]

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

    def loop(self):
        """ Super override, if the list of subtasks is not empty start next task, wait for it to complete 
        and then remove it from subtasks list. If subtasks list is empty call stop() and terminate. 
        """
        for t in self.subtasks:
            if not self.state == settings.STOPPING:
                self.current_subtask = t
                th = threading.Thread(target=t.run)
                th.start()
                th.join()

        self.state = settings.STOPPING

    def get_importance(self, goal=None):
        return self.current_subtask.get_importance(goal)

    
    def activate(self, goal=None):
        self.active = True
        self.current_subtask.activate()

    def de_activate(self):
        self.active = False
        self.current_subtask.de_activate()
   
class ParCompoundTask(CompoundTask):

    def __init__(self, drone, callback, context, level=0):
        CompoundTask.__init__(self, drone, callback, context, level)
        self.subtasks = []
        self.threads = []

    def get_importance(self, goal=None):
        imp = o
        for st in self.subtasks:
            timp = st.get_importance(goal)
            if timp > imp:
                imp = timp

        return imp

    def activate(self, goal=None):
        self.active = True
        maximp = None
        for t in self.subtasks:

            timp = t.get_importance(goal) 
            if  maximp is None or timp > maximp[0]:
                maximp = [timp, t]
            elif t == maximp[0]:
                if t.level > maximp[1].level:
                    maximp = [timp, t]
            
        if maximp is not None:
            maximp[1].activate()
            for t in self.subtasks:
                if t != maximp[1]:
                    t.de_activate()
                
    def de_activate(self):
        self.active = False
        for t in self.subtasks:
            t.de_activate()

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

            # stopped = False
            # while not stopped:
            #     stopped = True
            #     for t in self.subtasks:
            #         if not (t.state == settings.STOPPED or t.state == settings.INIT):
            #             stopped = False


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
    def __init__(self, drone, callback, context, the_map=None, level=0):
        """ The constructor can be supplied with a map containing points and a tour """
        SeqCompoundTask.__init__(self, drone, callback, context, level)

        # If no map is supplied load one from file
        if the_map is None:
            self.map = map.PosMap()
        else:
            self.map = the_map
       
        # Tour and positions from the map
        self.tour = self.map.tour
        self.positions = self.map.positions

        self.current_segment = 0
        # build subtasks
        self.add_subtasks(self.create_subtasks())
        

    def get_importance(self, goal=None):
        val = 3.0
        p = 0
        s = 0
        g = 0
        l = 0

        if self.detector.points is not None:
            p += 2
        if self.detector.silhouets is None:
            s += 1
        if goal is not None and goal=='followtour':
            g += 1
        
        if not self.interface.get_landed():
            l += 1

        return (p+s+g+l)/val 



    def setup_next_segment(self, caller):
        if not self.current_segment < len(self.tour):
            self.p.stop()
            return

        if self.current_segment < len(self.tour):
            self.h.set_turn(self.angles[self.current_segment])
            self.h.target_position = self.tour[self.current_segment][1]
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

        self.h = HoverTrackTask(self.p.drone, self.setup_next_segment, self.p.context, None, mode='detect')
        self.h.target_position = self.tour[0][0]
        self.h.level = 1

        self.m = MoveTask(self.p.drone, self.p.sub_callback, self.p.context, None, None, 0.065, 1)
        self.m.level = 0
        self.m.suppressed = True
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

    # def hover_callback(self, caller):
    #     """ Sets the blob/mark coordinate to None after each hover task """
    #     self.context[0] = None
    #     self.context[2] = None

class AvoidTask(Task):
    """ AvoidTask
    
    A task designed to make the drone avoid an object by moving up.

    """
    def __init__(self, drone, callback, context, level=0):
        """ The constructor can be supplied with a map containing points and a tour """
        Task.__init__(self, drone, callback, context, level)
        self.level = 1
        self.loop_sleep = 0.01
    def pre_loop(self):
        self.current_blob = None

    def loop(self):
        self.zaplock.acquire()
        self.interface.zap(0)
        img = self.video_sensor.get_data()
        while img.shape[1] != 320:
            img = self.video_sensor.get_data()
        self.zaplock.release()
        blob = bd.detect_green_blob(img)
        # we have a new blob
        if blob is not None and self.current_blob is None:
                (xpos, ypos), (width, height) = position, size = blob
                if width*height > 500:
                    print 'AVOIDING!!!\r'
                    self.current_blob = blob
                    if self.parent is not None:
                        self.parent.set_required_runlevel(self, 1)
                    self.interface.move(0.0, 0.0, 0.5, 0.0, False)
        
        elif blob is not None and self.current_blob is None:
            print 'Still avoiding\r'
            self.interface.move(0.0, 0.0, 0.5, 0.0, False)

        elif blob is None and self.current_blob is not None:
            print 'Blob avoided...\r'
            self.current_blob = None
            if self.parent is not None:
                self.parent.set_required_runlevel(self, 0)
            self.interface.move(0.0, 0.0, 0.0, 0.0, False)

    
    def get_importance(self, goal=None):
        val = 3.0
        p = 0
        s = 0
        g = 0
        l = 0

        if self.detector.silhouets is not None :
            s += 2
        if goal is not None and goal=='avoid':
            g += 1
        
        if not self.interface.get_landed():
            l += 1

        return (s+g+l)/val 

def get_all_tasks():
    """ returns a list of all the subtasks extending Task """
    res = globals()['Task'].__subclasses__()
    res.extend(globals()['CompoundTask'].__subclasses__())
    res.extend(globals()['SeqCompoundTask'].__subclasses__())
    res.extend(globals()['ParCompoundTask'].__subclasses__())
    return res

