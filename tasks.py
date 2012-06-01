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
import cv2
import cv2.cv as cv
import map
import os
import pickle
import Gnuplot, Gnuplot.funcutils

""" Context format : ['point of blob', root task reference, currect distance travelled ] """

d2r = (math.pi/180.0) # ratio for switching from degrees to radians

class Task(threading.Thread, object):
    """ The base Task

    The Task class sets up the generic task behaviour. It sets the local references to
    receivers and control interface in the constructor and defines the task flow via the run() 
    method. Subclasses should only need to overwrite one or more of: self.pre_loop(), self.loop() 
    and self.post_loop().

    """

    def __init__(self, drone, callback, context):
        """ Constructor 

        The contructor takes references to the drone, a callback method and a context(a list).
        The drone references is used to gain access to receivers and control interface. In this base 
        subtasks and dependant subtasks are left as empty lists to be overridden.
        
        """
        threading.Thread.__init__(self)
        
        self.drone = drone
        self.callback = callback
        self.context = context
        self.interface = drone.get_interface()
        
        self.video_sensor = drone.get_video_sensor()
        self.navdata_sensor = drone.get_navdata_sensor()
        self.wifi_sensor = drone.get_wifi_sensor()

        self.subtasks = []
        self.dep_subtasks = []
        
        self.loop_sleep = 0.1
        self.stopping = False
        #self.tracker = None
        self.point = None

    def get_point(self):
        """ returns the positions of the point currently tracked, only relevant for some subtasks. """
        return self.point

    def pre_loop(self):
        """ pre_loop

        This method should be overridden by subclasses, setup to be run immediately before the task
        main loop should be placed here.

        """
        pass

    def loop(self):
        """ loop

        This method should be overridden by subclasses. The loop method will be called continuously until
        self.stopping evaluates to True. If the subclass has no use for a main loop, be sure to make a call
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

        if self.dep_subtasks is not None:
            for t in self.dep_subtasks:
                t.start()

        print 'Starting ', self.__class__.__name__, '\r'
        self.pre_loop()

        while not self.stopping:
            self.loop()
            time.sleep(self.loop_sleep)

        self.post_loop()
        print 'Ending ', self.__class__.__name__, '\r'
        self.done()
    
    def stop(self):
        """ stop
        
        A rather obvious method, stops all dependant subtasks and sets the self.stopping flag to True

        """
        while len(self.dep_subtasks) > 0:
            ds = self.dep_subtasks[0]
            ds.stop()
            ds.join()
            self.dep_subtasks.remove(ds)

        self.stopping = True

    def done(self, args=None):
        """ done

        Done is called as the last thing in the run method, it just calls the supplied
        callback method, should probably be refactored out.

        """
        if args is not None:
            self.callback(self, args)
        else:
            self.callback(self)


class NoneTask(Task):
    """ NoneTask

    Does nothing, could be replaced with the base Task class.

    """
    def __init__(self, drone, callback, context):
         """ Just calls the super contructor, a very boring task indeed """
         Task.__init__(self, drone, callback, context)

class MeasureDistanceTask(Task):
    """ MeasureDistanceTask

    This class uses the velocities from the drone navdata to estimate the travelled distance(a basic integration),
    the class utilizes a shared context to make other tasks aware of the calculated distance. The task is well suited as 
    a dependent subtasks of a moveTask.

    """
    def __init__(self, drone, callback, context):
        
        Task.__init__(self, drone, callback, context)
       
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
    def __init__(self, drone, callback, context, time, distance, speed, direction):
        """ constructor which besides the three common task parameters also takes time, speed and direction """

        Task.__init__(self, drone, callback, context)
        if time is None:
            self.timer = None
        else:
            self.timer = threading.Timer(time, self.stop)

        if distance is not None:
            m = MeasureDistanceTask(drone, None, context)
            self.dep_subtasks.append(m)

        self.distance = distance
        self.context = context
        self.direction = direction
        self.speed = speed
        
    def move(self):
        """ based on the value of self.direction and self.speed, use the command interface to move """

        if self.direction == 1:
            self.interface.set(0, -self.speed, None, 0.0, True)
            #print 'moved forward\r'
        elif self.direction == 2 :
            self.interface.set(self.speed, 0, None, 0.0, True)
            #print 'moved right\r'
        elif self.direction == 3:
            self.interface.set(0, self.speed, None, 0.0, True)
            #print 'moved backward\r'
        elif self.direction == 4:
            self.interface.set(-self.speed, 0, None, 0.0, True)
            #print 'moved left\r'
        elif self.direction == 5:
            self.interface.set(None, None, self.speed, 0.0, True)
            #print 'moved up\r'
        elif self.direction == 6:
            self.interface.set(None, None, -self.speed, 0.0, True)
            #print 'moved down\r'
        else:
            self.interface.set(0,0,0,0,False)

    def pre_loop(self):
        """ Super override, starts the stop-timer if one is present and then uses the move method. """
        if self.timer is not None:
            self.timer.start()
        self.move() 

    def loop(self):
        """ Super override, checks if the given distance has been travelled. """

        # should be fixed to use the euclidian distance
        if self.distance is not None and self.context[2] is not None and (math.fabs(self.context[2][0]) >= self.distance or math.fabs(self.context[2][1]) >= self.distance):
             self.stop()
    
    def post_loop(self):
        """ Super override, stopping the drone after the task has been stopped. """
        self.interface.set(0,0,0,None,False)
        #time.sleep(2.0)

class TakeoffTask(Task):
    """ TakeoffTask

    Basically sends the takeoff command to the drone and waits for a given time

    """
    def __init__(self, drone, callback, context, wait):
        """ One additional parameter; the time to wait before ending the task """
        Task.__init__(self, drone, callback, context)
        self.wait = wait

    def pre_loop(self):
        """ Super override, only the pre_loop is necessary for this task. We must remember to call self.stop(). """
        
        self.interface.take_off()
        time.sleep(self.wait)
        self.stop()

class LandTask(Task):
    """ LandTask

    The LandTask sends the land command to the drone via the control interface and 
    the waits for a given time to end

    """
    def __init__(self, drone, callback, context, wait):
        """ The constructor takes one extra parameter, the time to wait before ending. """
        Task.__init__(self, drone, callback, context)
        self.wait = wait

    def pre_loop(self):
        """ Like in the TakeoffTask a main loop is unnecessary, the entire task is carried out here. """
        self.interface.land()
        time.sleep(self.wait)
        self.stop()

class SearchMarkTask(Task):
    """ SearchMarkTask
    
    Compares images from the camera feed with a given set of reference images, if a match is made
    the coordinate is shared through the context and the task stops 

    """
    def __init__(self, drone, callback, context, markpics=None):
        """ Beyond the standard parameters, the SearchMarkTask can be instantiated with a list of reference images """
        Task.__init__(self, drone, callback, context)
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
    def __init__(self, drone, callback, context, delay=0.0):
        """ The constructor can be supplied with an additional delay parameter, to delay the start of the task """
        Task.__init__(self, drone, callback, context)
        self.blob = None
        self.loop_sleep = 0.05
        self.delay = delay

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
                self.context[1].stop(MoveTask)
                self.context[0] = position
                self.stop()
            else:
                self.blob = None

class KeepDirTask(Task):
    """ KeepDirTask

    A more complicated task which implements a PID controller to keep a certain direction. The PID controller
    uses the drone navdata as input and the calculated engine response is fed to the control interface.

    """
    def __init__(self, drone, callback, context):
        """ The task constructor only takes the standard parameters """
        Task.__init__(self, drone, callback, context)
        self.verbose = False

        # variables used in calculating the PID output
        self.Kp = 0.125
        self.Ki = 0.0
        self.Kd = 0.05
        self.Derivator_psi = 0
        self.Integrator_psi = 0
        self.Integrator_max = 500
        self.Integrator_min = -500
        self.max_error_psi = 180

        self.loop_sleep = 0.05
          
    def pre_loop(self):
        """ Super override, sets the PID controller set point """
        self.set_point_psi = (self.navdata_sensor.get_data()).get(0, dict()).get('psi', 0)

    def loop(self):
        """ Super override, updates the PID and moves the drone accordingly """
        val = self.update()
        self.interface.move(val[0], val[1], val[2], val[3])
        
    def post_loop(self):
        """ Super override, stops the movement after task shutdown """
        self.interface.move(None, None, None, 0.0,True)
            
    def update(self):
        """ Calculate PID output using the psi value from the navdata and the set point """

        # Get the current reading
        psi   = (self.navdata_sensor.get_data()).get(0, dict()).get('psi', 0)
        self.error_psi = (360 + self.set_point_psi - psi)%360
        if self.error_psi > 180:
            self.error_psi = self.error_psi - 360

        # calculate the P term
        self.P_value_psi = self.Kp * (self.error_psi/self.max_error_psi)

        # calculate the I term, considering integrator max and min 
        self.Integrator_psi = self.Integrator_psi + self.error_psi

        if self.Integrator_psi > self.Integrator_max:
            self.Integrator_psi = self.Integrator_max
        elif self.Integrator_psi < self.Integrator_min:
            self.Integrator_psi = self.Integrator_min

        self.I_value_psi = self.Integrator_psi * self.Ki
       
        # calculate the D term
        self.D_value_psi = self.Kd * ((self.error_psi - self.Derivator_psi)/self.max_error_psi)
        self.Derivator_psi = self.error_psi

        # Sum the term values into one PID value
        PID_psi = self.P_value_psi + self.I_value_psi + self.D_value_psi
        retval_psi = PID_psi

        # print stuff for debugging purposes
        if self.verbose:
            print "Current psi: " + str(psi) + ", Error: " + str(self.error_psi) + ", Engine response: " + str(retval_psi)
      
        return (None, None, None, retval_psi)

class HoverTrackTask(Task):
    """
    Discrete PID control
    """

    def __init__(self, drone, callback, context, time=10.0, turn_delay=5.0):
        Task.__init__(self, drone, callback, context)
        self.tracker = None
        self.verbose = False
        if time is not None:
            self.timer = threading.Timer(time, self.stop_int)
        else:
            self.timer = None

        if turn_delay > 0.0:
            self.turn_timer = threading.Timer(turn_delay, self.start_turn)
        else:
            self.turn_timer = None
        self.turn = False

        # variables used in calculating the PID output
        self.Kp=2.0
        self.Ki=0.0
        self.Kd=0.5
        self.Derivator_x = 0
        self.Derivator_y = 0
        self.Derivator_psi = 0

        self.Integrator_x = 0
        self.Integrator_y = 0
        self.Integrator_psi = 0

        self.Integrator_max= 500
        self.Integrator_min= -500

        self.center = (88, 72)

        # we can never be more than 88 or 72 pixels from our target
        self.max_error_x = (4000*(math.tan(32*(math.pi/180))/88.0))*88.0#160.0 # 88
        self.max_error_y = (4000*(math.tan(26.18*(math.pi/180))/72.0))*72.0#120.0 # 72
        self.max_error_psi = 180
        self.psi_offset = 0
        self.loop_sleep = 0.05
        self.data_points = ([],[],[],[],[],[])

    def pre_loop(self):
        # t1 = datetime.datetime.now()
        while not self.stopping:
            if self.context[0] is not None:
                self.tracker = utils.PointTracker(self.drone.get_video_sensor(), self.drone.get_navdata_sensor(), self.context[0])
                self.tracker.init()
                self.source_method = self.tracker.track
                psi = self.navdata_sensor.get_data().get(0, dict()).get('psi', 0)
                self.set_point_psi = psi + self.psi_offset
                self.interface.set(0, 0, 0, 0, False)
                print 'Hovering...\r'
                if self.timer is not None:
                     self.timer.start()
                if self.turn_timer is not None:
                     self.turn_timer.start()
                break
            time.sleep(0.001)
        # t2 = datetime.datetime.now()
        # t_delta = (t2-t1).total_seconds()
        # print t_delta, '\r'

    def start_turn(self):
        """ Sets the self.turn flag to true allowing the psi val to corrected """
        print 'Activating turn'
        self.turn = True

    def stop_int(self):
        self.stop()
        print 'Stop called!\r'

    def loop(self):
        # Calculate PID output for this iteration
        powers = self.update()
        if powers is None:
            print 'powers was None\r'
            self.stop()
        else:
            # Use the calculated PID output to actually move
            if powers[0] == powers[1] == powers[2] == powers[3] == 0.0:
                self.interface.set(powers[0], powers[1], powers[2], powers[3], False)
            else:
                self.interface.set(powers[0], powers[1], powers[2], powers[3], True)
            
    def post_loop(self):       
        # remember to put the vehicle in hover mode after moving
        self.context[0] = None
        self.interface.set(0, 0, 0, 0, False)

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
        
        # timer = utils.Timer()

        # img = self.video_sensor.get_data()
        # with timer:
        #     blob = bd.detect_red_blob(img)
    
        # print timer.duration_in_seconds()

        # if blob is not None:
        #     (xpos, ypos), (width, height) = position, size = blob
        #     if width*height > 15:
        #         self.point = (xpos, ypos)
        #         self.set_point_x = xpos
        #         self.set_point_y = ypos

        #         navdata = self.navdata_sensor.get_data()
        #         angle_x   = (navdata.get(0, dict()).get('theta', 0))*d2r
        #         angle_y   = (navdata.get(0, dict()).get('phi', 0))*d2r
        #         psi_angle = navdata.get(0, dict()).get('psi', 0)
        #         alt = navdata.get(0, dict()).get('altitude', 0)

        #     else:
        #         return None
        # else:
        #     return None

        # with timer:
        currents = self.source_method()
                
        # print timer.duration_in_seconds()

        if currents is None:
            print 'Currents was None\r'
            return None

        self.point = (currents[0], currents[1])
        self.set_point_x = currents[0]
        self.set_point_y = currents[1]

        alt = currents[5]
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
        
        if self.turn:
            self.error_psi = (360 + self.set_point_psi - psi_angle)%360
            if self.error_psi > 180:
                self.error_psi = self.error_psi - 360
        else:
            self.error_psi = 0

        print 'error psi: ', self.error_psi, '\r'

        error_dist =  math.sqrt((self.error_y*self.error_y)+(self.error_x*self.error_x))
        self.data_points[0].append(time.time() - 1338000000.00)
        self.data_points[1].append(self.error_x)
        self.data_points[2].append(self.error_y)
        self.data_points[3].append(error_dist)
        self.data_points[4].append(0)
        self.data_points[5].append(0)

        # if error_dist < 30:
        #      return (0.0,0.0,0.0,0.0)

        # calculate the P term
        self.P_value_x = self.Kp * (self.error_x/self.max_error_x)
        self.P_value_y = self.Kp * (self.error_y/self.max_error_y)

        # if error_dist < 100:
        self.P_value_psi = self.Kp * (self.error_psi/self.max_error_psi)
        # else:
        #self.P_value_psi = 0.0

        # calculate the I term, considering integrator max and min 
        if self.Ki > 0:
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
        else:
            self.I_value_x, self.I_value_y, self.I_value_psi = 0.0, 0.0, 0.0
        
        # calculate the D term
        if self.Kd > 0:
            self.D_value_x = self.Kd * ((self.error_x - self.Derivator_x)/self.max_error_x)
            self.Derivator_x = self.error_x

            self.D_value_y = self.Kd * ((self.error_y - self.Derivator_y)/self.max_error_y)
            self.Derivator_y = self.error_y

            self.D_value_psi = self.Kd * ((self.error_psi - self.Derivator_psi)/self.max_error_psi)
            self.Derivator_psi = self.error_psi
        else:
            self.D_value_x, self.D_value_y, self.D_value_psi = 0.0, 0.0, 0.0

        # Sum the term values into one PID value
        PID_x = self.P_value_x + self.I_value_x + self.D_value_x
        PID_y = self.P_value_y + self.I_value_y + self.D_value_y
        PID_psi = self.P_value_psi + self.I_value_psi + self.D_value_psi

        # if PID_y < 0 and vx < 0:
        #     PID_y = PID_y - (vx/5000)/2
        #     #print 'added: ', (vx/5000), ' to y-power\r'
        # elif PID_y > 0 and vx > 0:
        #     PID_y = PID_y + (vx/5000)/2
        #     #print 'added: ', (vx/5000), ' to y-power\r'

        # if PID_x < 0 and vy < 0:
        #     PID_x = PID_x - (vy/5000)/2
        #     #print 'added: ', (vy/5000), ' to x-power\r'
        # elif PID_x > 0 and vy > 0:
        #     PID_x = PID_x + (vy/5000)/2
        #     #print 'added: ', (vy/5000), ' to x-power\r'
        
        # print stuff for debugging purposes
        if self.verbose:
            print "Error_x_pixels: " + str(self.read_error_x_pixels) + "\tError_x_mm:\t" + str(self.error_x) + "\tError_angle_x: " + str(angle_x/d2r) + "\tEngine response_x: " + str(PID_x) + "\r"
            print "Error_y_pixels: " + str(self.read_error_y_pixels) + "\tError_y_mm:\t" + str(self.error_y) + "\tError_angle_y: " + str(angle_y/d2r) + "\tEngine response_y: " + str(PID_y) + "\r"
            print "Error_combined: " + str(error_dist) + "\r"
            print "Altitude:\t", alt, "\r"
        t = time.time() - 1338000000.00
        # self.data_points[0].append(t)
        # self.data_points[1].append(self.error_x)
        # self.data_points[2].append(self.error_y)
        # self.data_points[3].append(error_dist)
        # self.data_points[4].append(PID_x*100)
        # self.data_points[5].append(PID_y*100)
        
        # if self.turn and -1.0 < self.error_psi < 1.0:
        #       self.stop()

        return (PID_x, PID_y, None, PID_psi/2)

    def correct_angle(self, val, angle, alt):
        alpha = math.atan2(alt, abs(val));
        if (angle > 0 and val < 0) or (angle < 0 and angle > 0):
            return val * math.sin(alpha) / math.sin(alpha - abs(angle)) - alt * math.sin(angle)
	else:
            return val * math.sin(alpha) / math.cos(abs(angle)) - alt * math.sin(angle)

    def toggle_verbose(self):
        self.verbose = not self.verbose

    def setPsi(self, degrees):
        self.set_point_psi = (360+(self.set_point_psi + degrees))%360
        print "moving to: " + str(self.set_point_psi) + "\r" 

class CompoundTask(Task):
    """ CompoundTask

    This is the base class for compound tasks, ie. tasks which manage a list of subtasks
    and and stops when either all subtasks has completed or it is stop method is called.

    """
    def __init__(self, drone, callback, context):
        """ The contructor will create a context if None was supplied, subtasks need the context for communicating """
        Task.__init__(self, drone, callback, context)
        if context is None:
            self.context = [None, self, None, None]
        else:
            self.context = context

        self.subtasks = []
        self.loop_sleep = 0.0001

    def add_subtask(self, task, index=None):
        task.drone = self.drone
        task.callback = self.sub_callback
        task.context = self.context
        self.subtasks.append(task)

    def sub_callback(self, caller):
        """ This method can be overridden if a subclass wishes for processing to happen when subtasks finish """
        pass
    
    def stop(self, ty=None):
        """ If the stop method is supplied with a type parameter all subtasks of this type will be terminated, else
        all subtasks will terminated and thus the compound task itself will end.
        """
        if ty is not None:
            for t in self.subtasks:
                if isinstance(t, ty) and t.is_alive():
                    t.stop()
                elif isinstance(t, CompoundTask):
                    t.stop(ty)
        else:
            self.stopping = True
            for t in self.subtasks:
                t.stop()
    
    def done(self, args=None):
        """ Super extension, adds some print to better localise compound stop. """
        Task.stop(self)
        print '*********************************************\r'
       
class SeqCompoundTask(CompoundTask):
    """ SeqCompoundTask

    A compound tasks which starts its subtasks one at a time and waits for its completions before
    starting another. Terminates when the lists of subtasks is empty.

    """
    def __init__(self, drone, callback, context):
        CompoundTask.__init__(self, drone, callback, context)
       
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
        if len(self.subtasks) > 0:
            t = self.subtasks[0]
            t.start()
            t.join()
            self.subtasks.remove(t)
        
        if len(self.subtasks) == 0:
            self.stop()

class ParCompoundTask(CompoundTask):

    def __init__(self, drone, callback, context):
        CompoundTask.__init__(self, drone, callback, context)
        self.subtasks = [MoveTask(self.drone, self.sub_callback, self.context, None, None, 0.075, 1), SearchTask(self.drone, self.sub_callback, self.context, 4.0)]
                  
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
            t.start()

    def loop(self):
        """ Super override, check if any subtasks has completed, if so remove from subtask list. 
        If subtasks list is empty call stop() and terminate.
        """
        for t in self.subtasks:
            if not t.is_alive():
                self.subtasks.remove(t)

        if len(self.subtasks) == 0:
            self.stop()


class FollowTourTask(SeqCompoundTask):
    """ FollowTourTask
    
    A task designed to make the drone follow a tour obtained from a map of points. 
    Based on the tour describtion the tasks creates the necessary subtasks.

    """
    def __init__(self, drone, callback, context, the_map=None):
        """ The constructor can be supplied with a map containing points and a tour """
        SeqCompoundTask.__init__(self, drone, callback, context)

        # If no map is supplied load one from file
        if the_map is None:
            if os.path.isfile('./testdata/map.data'):
                fileObj = open('./testdata/map.data')
                self.map = pickle.load(fileObj)
            else:
                self.map = map.PosMap()
        else:
            self.map = the_map
       
        # Tour and positions from the map
        self.tour = self.map.tour
        self.positions = self.map.positions
        
        # build subtasks
        self.subtasks = self.create_subtasks()

    def create_subtasks(self):
        res = []
        for i in range(len(self.tour)):

            if i+1 > len(self.tour)-1:
                turn_angle = 0
            else:
                current = self.tour[i]
                next = self.tour[i+1]

                x1 = current[1][1] - current[0][1]
                y1 = current[1][2] - current[0][2]
                
                x2 = next[1][1] - next[0][1]
                y2 = next[1][2] - next[0][2]
                
                dp = x1*x2 + y1*y2
                
                turn_angle = (math.atan2(y2,x2) - math.atan2(y1,x1))/d2r

                print '(',x1, ',', y1, ')\r'
                print '(',x2, ',', y2, ')\r'
                print '**************\r'
           
            print 'turn angle: ',turn_angle, '\r'

            # use modifiers to start movetasks with different algorithms
            modifiers = self.tour[i][2]
            t = ParCompoundTask(self.drone, self.sub_callback, self.context)
            h = HoverTrackTask(t.drone, self.hover_callback, t.context, time=10.0, turn_delay=5.0)
            h.psi_offset = turn_angle
            
            t.subtasks.append(h)
            res.append(t)

        res.append(LandTask(self.drone,self.sub_callback, self.context, 5))
        return res

    def hover_callback(self, caller):
        """ Sets the blob/mark coordinate to None after each hover task """
        self.context[0] = None




def get_all_tasks():
    """ returns a list of all the subtasks extending Task """
    res = globals()['Task'].__subclasses__()
    res.extend(globals()['CompoundTask'].__subclasses__())
    return res
