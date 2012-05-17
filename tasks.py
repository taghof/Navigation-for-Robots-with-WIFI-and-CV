from __future__ import with_statement
import threading
import datetime
import math
import time
import blobdetect as bd
import utils
import cv2
import cv2.cv as cv

d2r = (math.pi/180.0) # ratio for switching from degrees to radians

class Task(threading.Thread):
    
    def __init__(self, drone, callback, context=None,interface=None):
        threading.Thread.__init__(self)
        
        self.drone = drone
        self.callback = callback
        self.context = context
        if interface is None:
            self.interface = drone.get_interface()
        else:
            self.interface = interface

        self.video_sensor = drone.get_video_sensor()
        self.navdata_sensor = drone.get_navdata_sensor()
        self.wifi_sensor = drone.get_wifi_sensor()

        self.subtasks = None
        self.dep_subtasks = None

        self.stopping = False
        self.tracker = None
        self.point = None

    def run(self):
        pass
    
    def stop(self, args=None):
        self.stopping = True

    def done(self, args=None):
        if args is not None:
            self.callback(self, args)
        else:
            self.callback(self)


class MeasureDistanceTask(Task):
     def __init__(self, drone, callback, context):
        Task.__init__(self, drone, callback, context)
       
        self.dist_x = 0
        self.dist_y = 0
        self.last_time = None
        self.last_vx = 0
        self.last_vy = 0

     def run(self):
         print 'starting measurement\r'
         self.last_time = time.time()
         while not self.stopping:
             self.measure()
             self.context[3] = (self.dist_x, self.dist_y)
             time.sleep(0.05)
         print 'moved: (', self.dist_x, ', ', self.dist_y, ')\r'

     def measure(self):
         now_time = time.time()
         elapsed_time = self.last_time - now_time
         vx = self.navdata_sensor.get_data().get(0, dict()).get('vx', 0)
         vy = self.navdata_sensor.get_data().get(0, dict()).get('vy', 0)
         
         small_vx = min(vx, self.last_vx) 
         small_vy = min(vy, self.last_vy) 

         rect_x = small_vx*elapsed_time
         rect_y = small_vy*elapsed_time
         
         tri_x = ((max(vx, self.last_vx)-small_vx)/2)*elapsed_time
         tri_y = ((max(vy, self.last_vy)-small_vy)/2)*elapsed_time

         self.dist_x += tri_x + rect_x
         self.dist_y += tri_y + rect_y

         self.last_time = now_time
         self.last_vx = vx
         self.last_vy = vy

     def reset(self):
         self.dist_x = 0
         self.dist_y = 0

class MoveTask(Task):

    def __init__(self, drone, callback, context, time, speed, direction):
        Task.__init__(self, drone, callback)
        self.time = time
        if time == -1:
            self.timer = None
        else:
            self.timer = threading.Timer(time, self.stop)

        self.context = context
        self.direction = direction
        self.speed = speed
        

    def stop(self):
        while len(self.dep_subtasks) > 0:
            ds = self.dep_subtasks[0]
            ds.stop()
            self.dep_subtasks.remove(ds)
                        
        self.direction = 0
        self.stopping = True
        
    def move(self):
        if self.direction == 1:
            self.interface.move(0, -self.speed, None, None, True)
            #print 'moved forward\r'
        elif self.direction == 2 :
            self.interface.move(self.speed, 0, None, None, True)
            #print 'moved right\r'
        elif self.direction == 3:
            self.interface.move(0, self.speed, None, None, True)
            #print 'moved backward\r'
        elif self.direction == 4:
            self.interface.move(-self.speed, 0, None, None, True)
            #print 'moved left\r'
        elif self.direction == 5:
            self.interface.move(None, None, self.speed, None, True)
            #print 'moved up\r'
        elif self.direction == 6:
            self.interface.move(None, None, -self.speed, None, True)
            #print 'moved down\r'
        else:
            self.interface.move(0,0,0,None,False)
                  
    def run(self):
        if self.dep_subtasks is not None:
            for t in self.dep_subtasks:
                t.start()

        if self.timer is not None:
            self.timer.start()

        while not self.stopping:
            self.move()
            time.sleep(0.1)
        
        self.interface.move(0,0,0,None,False)
        self.interface.move(0,0,0,None,False)
        self.interface.move(0,0,0,None,False)
        print 'stopped moving\r'
        time.sleep(2.0)
        self.done()
        
class TakeoffTask(Task):
    
    def __init__(self, drone, callback, context, wait):
        Task.__init__(self, drone, callback, context)
        self.wait = wait

    def run(self):
        self.interface.take_off()
        time.sleep(self.wait)
        self.done()

class LandTask(Task):

    def __init__(self, drone, callback, context,wait):
        Task.__init__(self, drone, callback, context)
        self.wait = wait

    def run(self):
        self.interface.land()
        time.sleep(self.wait)
        self.done()

class SearchTask(Task):

    def __init__(self, drone, callback, context):
        Task.__init__(self, drone, callback, context)
        
    def run(self):
        print 'Search task started\r'
        blob = None
        while not self.stopping:
            img = self.video_sensor.get_data()
            #img = input_image = cv2.cvtColor(img, cv.CV_RGB2BGR)
            blob = bd.detect_red_blob(img)
            if blob is not None:
                (xpos, ypos), (width, height) = position, size = blob
                if width*height > 15:
                    self.context[1].stop(MoveTask)
                    break
                else:
                    blob = None
            time.sleep(0.05)

        self.context[0] = position
        self.done()

class KeepDirTask(Task):
    
    def __init__(self, drone, callback):
        Task.__init__(self, drone, callback)
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
                
    def run(self):
        self.set_point_psi = (self.navdata_sensor.get_data()).get(0, dict()).get('psi', 0)
        while not self.stopping:
            val = self.update()
            self.interface.move(val[0], val[1], val[2], val[3])
        
        self.interface.move(None, None, None, 0.0,True)
        self.done()
    
    def update(self):
        """
        Calculate PID output using the input method and the set point
        """

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
      
        # # don't let thread suck all power, have a nap
        time.sleep(0.05)
        return (None, None, None, retval_psi)

class HoverTrackTask(Task):
    """
    Discrete PID control
    """

    def __init__(self, drone, callback, context=None, P=0.10, I=0.0, D=0.20, Integrator_max=500, Integrator_min=-500):
        Task.__init__(self, drone, callback, context)
        self.tracker = None
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

        self.center = (88, 72)

        # we can never be more than 88 or 72 pixels from our target
        self.max_error_x = (4000*(math.tan(32*(math.pi/180))/88.0))*88.0#160.0 # 88
        self.max_error_y = (4000*(math.tan(26.18*(math.pi/180))/72.0))*72.0#120.0 # 72
        self.max_error_psi = 180

        self.running = False
        self.started = False

    def stop(self):
        self.running = False

    def is_started(self):
        return self.started

    def run(self):
        self.running = True
        self.started = True

        while self.context[0] is None:
            time.sleep(0.001)

        self.tracker = utils.PointTracker(self.drone.get_video_sensor(), self.drone.get_navdata_sensor(), self.context[0])
        # print self.tracker
        # self.context[1].tracker = self.tracker
        self.tracker.init()
        self.source_method = self.tracker.track
        #navdata = self.navdata_sensor.get_data()

        self.set_point_psi = self.source_method()[4]#navdata.get(0, dict()).get('psi', 0)#
        self.interface.move(0, 0, 0, 0,False)

        print 'Starting HoverTrackTask\r'
        while self.running:
            # Calculate PID output for this iteration
            powers = self.update()
            if powers is None:
                break
            else:
                # Use the calculated PID output to actually move
                self.interface.move(powers[0], powers[1], powers[2], powers[3], True)
            time.sleep(0.005)
        # remember to put the vehicle in hover mode after moving
        self.context[0] = None
        # print self.tracker.maxvx, '\r'
        # print self.tracker.maxvy, '\r'

        #self.tracker.stop()
        self.interface.move(0, 0, 0, 0)
        self.done()
        print 'shutting down HoverTrackTask\r'

    def update(self):
        """
        Calculate PID output using the input method
        """
        
        timer = utils.Timer()

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

        with timer:
            currents = self.source_method()
                
        print timer.duration_in_seconds()

        if currents is None:
            return None

        self.point = (currents[0], currents[1])
        self.set_point_x = currents[0]
        self.set_point_y = currents[1]

        alt = currents[5]
        angle_x = currents[2]*d2r
        angle_y = currents[3]*d2r
        psi_angle = currents[4]

        self.read_error_x_pixels = self.set_point_x - self.center[0]
        c = (math.tan(32.0*d2r)/88.0) # error in the plane perpendicular to height
        self.read_error_x_mm = self.read_error_x_pixels*(alt*c)
        extra_angle_x = math.atan(alt/math.fabs(self.read_error_x_mm+0.0000000001))
        x_in_error = alt * math.sin(angle_x) # error contributed by the tilting itself

        if angle_x < 0 and self.read_error_x_mm > 0 or angle_x > 0 and self.read_error_x_mm < 0:
            a = math.sin(extra_angle_x)
            b = math.sin(extra_angle_x-angle_x)
            x_out_error = self.read_error_x_mm * (a / b)
        else:
            a = math.sin(extra_angle_x)
            b = math.cos(angle_x)
            x_out_error = self.read_error_x_mm * (a / b) 

        self.error_x = x_out_error - x_in_error

        self.read_error_y_pixels = self.set_point_y - self.center[1]
        c = (math.tan(26.18*d2r)/72.0) # error in the plane perpendicular to height
        self.read_error_y_mm = self.read_error_y_pixels*(alt*c)
        extra_angle_y = math.atan(alt/math.fabs(self.read_error_y_mm+0.0000000001))
        y_in_error = alt * math.sin(angle_y) # error contributed by the tilting itself
        
        
        if angle_y < 0 and self.read_error_y_mm > 0 or angle_y > 0 and self.read_error_y_mm < 0:
            a = math.sin(extra_angle_y)
            b = math.sin(extra_angle_y-angle_y)
            y_out_error = self.read_error_y_mm * (a / b)
        else:
            a = math.sin(extra_angle_y)
            b = math.cos(angle_y)
            y_out_error = self.read_error_y_mm * (a / b) 

        self.error_y = y_out_error - y_in_error

        self.error_psi = (360 + self.set_point_psi - psi_angle)%360
        if self.error_psi > 180:
            self.error_psi = self.error_psi - 360

        error_dist =  math.sqrt((self.error_y*self.error_y)+(self.error_x*self.error_x))

        if error_dist < 100:
            return (0.0,0.0,0.0,0.0)

        # calculate the P term
        self.P_value_x = self.Kp * (self.error_x/self.max_error_x)
        self.P_value_y = self.Kp * (self.error_y/self.max_error_y)
        self.P_value_psi = self.Kp * (self.error_psi/self.max_error_psi)

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
        
        # print stuff for debugging purposes
        if self.verbose:
            print "Error_x_pixels: " + str(self.read_error_x_pixels) + "\tError_x_mm:\t" + str(self.error_x) + "\tError_angle_x: " + str(angle_x) + "\tEngine response_x: " + str(PID_x) + "\r"
            print "Error_y_pixels: " + str(self.read_error_y_pixels) + "\tError_y_mm:\t" + str(self.error_y) + "\tError_angle_y: " + str(angle_y) + "\tEngine response_y: " + str(PID_y) + "\r"
            print "Error_combined: " + str(math.sqrt((self.error_y*self.error_y)+(self.error_x*self.error_x))) + "\r"
            print "Altitude:\t", alt, "\r"
                
        return (PID_x, PID_y, None, PID_psi)

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


class SeqCompoundTask(Task):

    def __init__(self, drone, callback, context=None):
        Task.__init__(self, drone, callback, context)
        # self.subtasks = [#TakeoffTask(drone, self.sub_callback, 5), MoveTask(drone, self.sub_callback, 0.5, 5), MoveTask(drone, self.sub_callback, 0.35, 1), MoveTask(drone, self.sub_callback, 0.35, 2), MoveTask(drone, self.sub_callback, 0.35, 3), MoveTask(drone, self.sub_callback, 0.35, 4), LandTask(drone, self.sub_callback)]
        if context is None:
            self.context = [None, self, None, None]
        else:
            self.context = context

        self.subtasks = [SearchTask(self.drone, self.sub_callback, self.context), 
                         HoverTrackTask(self.drone, self.sub_callback, self.context)] 

    def sub_callback(self, caller):
        print caller, ' ended\r'

    def set_conf_1(self):
        self.subtasks = [SearchTask(self.drone, self.sub_callback, self.context), 
                         utils.PIDxy(self.drone, self.sub_callback, self.context)] 

    def set_conf_2(self):
        self.subtasks = [#TakeoffTask(self.drone, self.sub_callback, self.context, 5.0), 
            MoveTask(self.drone, self.sub_callback, self.context, 2.0, 0.8, 5),
            SearchTask(self.drone, self.sub_callback, self.context), 
                         HoverTrackTask(self.drone, self.sub_callback, self.context),
                         LandTask(self.drone, self.sub_callback, self.context, 5.0)]

    def set_conf_3(self):
        self.subtasks = [TakeoffTask(self.drone, self.sub_callback, self.context, 5)]

    def set_conf_4(self):
        #To = TakeoffTask(self.drone, self.sub_callback, self.context, 7)
        # Mf = MoveTask(self.drone, self.sub_callback, self.context, -1, 0.15, 1)
        # La = LandTask(self.drone, self.sub_callback, self.context, 5.0)
       
        # Par = ParCompoundTask(self.drone, self.sub_callback, self.context)
        # Se = SearchTask(self.drone, Par.sub_callback, self.context) 
        # Ho = HoverTrackTask(self.drone, Par.sub_callback, self.context)
        # Ho.verbose = True
        # Par.subtasks = [Se, Ho]
        b1 = MeasureDistanceTask(self.drone, self.sub_callback, self.context)
        self.subtasks = [b1]

    def set_conf_5(self):
        a = TakeoffTask(self.drone, self.sub_callback, self.context, 7)
        
        b = MoveTask(self.drone, self.sub_callback, self.context, 1.0, 0.2, 1)
        b1 = MeasureDistanceTask(self.drone, None, self.context)
        b.dep_subtasks = [b1]

        c = MoveTask(self.drone, self.sub_callback, self.context, 1.0, 0.2, 2)
        c1 = MeasureDistanceTask(self.drone, None, self.context)
        c.dep_subtasks = [c1]

        d = MoveTask(self.drone, self.sub_callback, self.context, 1.0, 0.2, 3)
        d1 = MeasureDistanceTask(self.drone, None, self.context)
        d.dep_subtasks = [d1]

        e = MoveTask(self.drone, self.sub_callback, self.context, 1.0, 0.2, 4)
        e1 = MeasureDistanceTask(self.drone, None, self.context)
        e.dep_subtasks = [e1]

        f = LandTask(self.drone, self.sub_callback, self.context, 5.0)
        self.subtasks = [b,e,d,c]

    def stop(self, ty=None):
        if ty is not None:
            for t in self.subtasks:
                if isinstance(t, ty):# add recursive for containers
                    t.stop()
                elif isinstance(t, SeqCompoundTask) or isinstance(t, ParCompoundTask):
                    t.stop(ty)
        else:
            self.stopping = True
            for t in self.subtasks:
                t.stop()
            
    def run(self):
        while len(self.subtasks) > 0 and not self.stopping:
            t = self.subtasks[0]
            t.start()
            self.tracker = t.tracker

            t.join()
            self.subtasks.remove(t)
        print 'Sequencial Compound task done\r'
        self.done()

class ParCompoundTask(Task):

    def __init__(self, drone, callback, context=None):
        Task.__init__(self, drone, callback)
        if context is None:
            self.context = [None, self, None, None]
        else:
            self.context = context
            
       #  task1 = SeqCompoundTask(drone, self.sub_callback, self.context)
#         task1.set_conf_1()
#         task2 = SeqCompoundTask(drone, self.sub_callback, self.context)
#         task2.set_conf_2()
# #        self.subtasks = [MoveTask(drone, self.sub_callback, self.context, -1, 1), SeqCompoundTask(drone, self.sub_callback, self.context)]
#         self.subtasks = [task1, task2]

    def sub_callback(self, caller):
        self.subtasks.remove(caller)
        print 'len of par.subtasks: ', len(self.subtasks), '\r'
        if len(self.subtasks) == 0:
            print 'Parallel Compound task done\r'
            self.done()
          
    def run(self):
        for t in self.subtasks:
            t.start()

        while len(self.subtasks) > 0:
            self.subtasks[0].join()

    def stop(self, ty=None):
        if ty is not None:
            for t in self.subtasks:
                if isinstance(t, ty):# add recursive for containers
                    t.stop()
                elif isinstance(t, SeqCompoundTask) or isinstance(t, ParCompoundTask):
                    t.stop(ty)
        else:
            for t in self.subtasks:
                t.stop()
       

def get_all_tasks():
    return vars()['Task'].__subclasses__()

