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

d2r = (math.pi/180.0) # ratio for switching from degrees to radians

#******************************************
# context format: ['point of blob', root task reference, currect distance travelled, ....]
#******************************************
class Task(threading.Thread):
    
    def __init__(self, drone, callback, context=None):
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
        self.tracker = None
        self.point = None

    def pre_loop(self):
        pass

    def loop(self):
        pass

    def post_loop(self):
        pass

    def run(self):
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
    
    def stop(self, args=None):
        while len(self.dep_subtasks) > 0:
            ds = self.dep_subtasks[0]
            ds.stop()
            ds.join()
            self.dep_subtasks.remove(ds)

        self.stopping = True

    def done(self, args=None):
        if args is not None:
            self.callback(self, args)
        else:
            self.callback(self)


class NoneTask(Task):
     def __init__(self, drone, callback):
        Task.__init__(self, drone, callback, None)

class MeasureDistanceTask(Task):
    def __init__(self, drone, callback, context):
        Task.__init__(self, drone, callback, context)
       
        self.dist_x = 0
        self.dist_y = 0
        self.last_time = None
        self.last_vx = 0
        self.last_vy = 0
        self.loop_sleep = 0.05

    def pre_loop(self):
        self.context[3] = (self.dist_x, self.dist_y)
        self.last_time = time.time()

    def loop(self):
        self.measure()
        self.context[2] = (self.dist_x, self.dist_y)

    def post_loop(self):
        self.context[2] = (0, 0)
        print 'moved: (', self.dist_x, ', ', self.dist_y, ')\r'

    def measure(self):
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

        self.last_vy = vy
        self.last_vx = vx
        self.last_time = now_time

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
        
    def move(self):
        if self.direction == 1:
            self.interface.set(0, -self.speed, None, None, True)
            #print 'moved forward\r'
        elif self.direction == 2 :
            self.interface.set(self.speed, 0, None, None, True)
            #print 'moved right\r'
        elif self.direction == 3:
            self.interface.set(0, self.speed, None, None, True)
            #print 'moved backward\r'
        elif self.direction == 4:
            self.interface.set(-self.speed, 0, None, None, True)
            #print 'moved left\r'
        elif self.direction == 5:
            self.interface.set(None, None, self.speed, None, True)
            #print 'moved up\r'
        elif self.direction == 6:
            self.interface.set(None, None, -self.speed, None, True)
            #print 'moved down\r'
        else:
            self.interface.set(0,0,0,None,False)

    def pre_loop(self):
        if self.timer is not None:
            self.timer.start()
        self.move() 

    def loop(self):
        if self.context[2] is not None and (math.fabs(self.context[2][0]) >= 1000 or math.fabs(self.context[2][1]) >= 1000):
             self.stop()
    
    def post_loop(self):
        self.interface.set(0,0,0,None,False)
        time.sleep(2.0)

class TakeoffTask(Task):
    
    def __init__(self, drone, callback, context, wait):
        Task.__init__(self, drone, callback, context)
        self.wait = wait

    def pre_loop(self):    
        self.interface.take_off()
        time.sleep(self.wait)
        self.stop()

class LandTask(Task):

    def __init__(self, drone, callback, context,wait):
        Task.__init__(self, drone, callback, context)
        self.wait = wait

    def pre_loop(self):
        self.interface.land()
        time.sleep(self.wait)
        self.stop()

class SearchMarkTask(Task):

    def __init__(self, drone, callback, context, markpics=None):
        Task.__init__(self, drone, callback, context)
        self.mark = []
        if markpics is None:
            self.mark.append(cv2.imread('./mark3e.png', 0))
            self.mark.append(cv2.imread('./mark3f.png', 0))
            self.mark.append(cv2.imread('./mark3g.png', 0))
            self.mark.append(cv2.imread('./mark3h.png', 0))
        else:
            self.mark = markpics

        self.loop_sleep = 0.05

    def loop(self):
        matching = self.search_for_mark()
        if matching is not None:
            #context[0] = something in matching
            self.stop()

    def search_for_mark(self):
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

    def __init__(self, drone, callback, context):
        Task.__init__(self, drone, callback, context)
        self.blob = None
        self.loop_sleep = 0.05

    def loop(self):
        img = self.video_sensor.get_data()
            #img = input_image = cv2.cvtColor(img, cv.CV_RGB2BGR)
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

        self.loop_sleep = 0.05
          
    def pre_loop(self):
        self.set_point_psi = (self.navdata_sensor.get_data()).get(0, dict()).get('psi', 0)

    def loop(self):
        val = self.update()
        self.interface.move(val[0], val[1], val[2], val[3])
        
    def post_loop(self):
        self.interface.move(None, None, None, 0.0,True)
            
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
      
        return (None, None, None, retval_psi)

class HoverTrackTask(Task):
    """
    Discrete PID control
    """

    def __init__(self, drone, callback, context=None):
        Task.__init__(self, drone, callback, context)
        self.tracker = None
        self.verbose = False

        # variables used in calculating the PID output
        self.Kp=1.0
        self.Ki=0.0
        self.Kd=0.0
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
        self.running = False
        self.started = False
        self.loop_sleep = 0.05

    def is_started(self):
        return self.started

    def pre_loop(self):
        self.started = True

        while not self.stopping:
            if self.context[0] is not None:
                self.tracker = utils.PointTracker(self.drone.get_video_sensor(), self.drone.get_navdata_sensor(), self.context[0])
                self.tracker.init()
                self.source_method = self.tracker.track
                self.set_point_psi = self.navdata_sensor.get_data().get('psi', 0) + self.psi_offset
                self.interface.set(0, 0, 0, 0, False)
                print 'Hovering...\r'
                break
            time.sleep(0.001)
       
       
    def loop(self):
        # Calculate PID output for this iteration
        powers = self.update()
        if powers is None:
            self.stop()
        else:
            # Use the calculated PID output to actually move
            self.interface.set(powers[0], powers[1], powers[2], powers[3], True)

    def post_loop(self):       
        # remember to put the vehicle in hover mode after moving
        self.context[0] = None
        self.interface.set(0, 0, 0, 0, False)
        

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
        
        self.error_psi = (360 + self.set_point_psi - psi_angle)%360
        if self.error_psi > 180:
            self.error_psi = self.error_psi - 360

        error_dist =  math.sqrt((self.error_y*self.error_y)+(self.error_x*self.error_x))

        # if error_dist < 100:
        #     return (0.0,0.0,0.0,0.0)

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

        if PID_y < 0 and vx < 0:
            PID_y = PID_y - (vx/5000)
            #print 'added: ', (vx/5000), ' to y-power\r'
        elif PID_y > 0 and vx > 0:
            PID_y = PID_y + (vx/5000)
            #print 'added: ', (vx/5000), ' to y-power\r'


        if PID_x < 0 and vy < 0:
            PID_x = PID_x - (vy/5000)
            #print 'added: ', (vy/5000), ' to x-power\r'
        elif PID_x > 0 and vy > 0:
            PID_x = PID_x + (vy/5000)
            #print 'added: ', (vy/5000), ' to x-power\r'

        
        # print stuff for debugging purposes
        if self.verbose:
            print "Error_x_pixels: " + str(self.read_error_x_pixels) + "\tError_x_mm:\t" + str(self.error_x) + "\tError_angle_x: " + str(angle_x/d2r) + "\tEngine response_x: " + str(PID_x) + "\r"
            print "Error_y_pixels: " + str(self.read_error_y_pixels) + "\tError_y_mm:\t" + str(self.error_y) + "\tError_angle_y: " + str(angle_y/d2r) + "\tEngine response_y: " + str(PID_y) + "\r"
            print "Error_combined: " + str(math.sqrt((self.error_y*self.error_y)+(self.error_x*self.error_x))) + "\r"
            print "Altitude:\t", alt, "\r"
                
        return (PID_x, PID_y, None, PID_psi)

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
        self.loop_sleep = 0.0001

    def sub_callback(self, caller):
        pass
        #print caller, ' ended\r'

    def set_conf_1(self):
        self.subtasks = [SearchTask(self.drone, self.sub_callback, self.context), 
                         utils.PIDxy(self.drone, self.sub_callback, self.context)] 

    def set_conf_2(self):
        self.subtasks = [#TakeoffTask(self.drone, self.sub_callback, self.context, 5.0), 
            SearchTask(self.drone, self.sub_callback, self.context), 
            HoverTrackTask(self.drone, self.sub_callback, self.context),
            LandTask(self.drone, self.sub_callback, self.context, 5.0)]

    def set_conf_3(self):
        self.subtasks = [TakeoffTask(self.drone, self.sub_callback, self.context, 7),
                         MoveTask(self.drone, self.sub_callback, self.context, -1, 0.1, 1)]

    def set_conf_4(self):
        To = TakeoffTask(self.drone, self.sub_callback, self.context, 7)
        # Mf = MoveTask(self.drone, self.sub_callback, self.context, -1, 0.15, 1)
        # La = LandTask(self.drone, self.sub_callback, self.context, 5.0)
       
        # Par = ParCompoundTask(self.drone, self.sub_callback, self.context)
        Se = SearchTask(self.drone, self.sub_callback, self.context) 
        Ho = HoverTrackTask(self.drone, self.sub_callback, self.context)
        # Ho.verbose = True
        # Par.subtasks = [Se, Ho]
        b1 = MeasureDistanceTask(self.drone, self.sub_callback, self.context)
        b = MoveTask(self.drone, self.sub_callback, self.context, 2.0, 0.2, 5)
     
        self.subtasks = [Se, Ho]

    def set_conf_5(self):
        a = TakeoffTask(self.drone, self.sub_callback, self.context, 7)
        
        b = MoveTask(self.drone, self.sub_callback, self.context, -1, 0.1, 1)
        b1 = MeasureDistanceTask(self.drone, None, self.context)
        b.dep_subtasks = [b1]

        c = MoveTask(self.drone, self.sub_callback, self.context, -1, 0.1, 2)
        c1 = MeasureDistanceTask(self.drone, None, self.context)
        c.dep_subtasks = [c1]

        d = MoveTask(self.drone, self.sub_callback, self.context, -1, 0.1, 3)
        d1 = MeasureDistanceTask(self.drone, None, self.context)
        d.dep_subtasks = [d1]

        e = MoveTask(self.drone, self.sub_callback, self.context, -1, 0.1, 4)
        e1 = MeasureDistanceTask(self.drone, None, self.context)
        e.dep_subtasks = [e1]

        f = LandTask(self.drone, self.sub_callback, self.context, 5.0)
        self.subtasks = [b,e,d,c,f]


    def stop(self, ty=None):
        if ty is not None:
            for t in self.subtasks:
                if isinstance(t, ty):
                    t.stop()
                elif isinstance(t, SeqCompoundTask) or isinstance(t, ParCompoundTask):
                    t.stop(ty)
        else:
            self.stopping = True
            for t in self.subtasks:
                t.stop()

    def loop(self):
        if len(self.subtasks) > 0:
            t = self.subtasks[0]
            t.start()
            self.tracker = t.tracker
            t.join()
            self.subtasks.remove(t)
        
        if len(self.subtasks) == 0:
            self.stop()

class ParCompoundTask(Task):

    def __init__(self, drone, callback, context=None):
        Task.__init__(self, drone, callback)
        if context is None:
            self.context = [None, self, None, None]
        else:
            self.context = context
        self.loop_sleep = 0.0001    
        task1 = SeqCompoundTask(drone, self.sub_callback, self.context)
        task1.set_conf_2()
        task2 = SeqCompoundTask(drone, self.sub_callback, self.context)
        task1.set_conf_3()
        self.subtasks = [MoveTask(self.drone, self.sub_callback, self.context, -1, 0.1, 1), SearchTask(self.drone, self.sub_callback, self.context)]
        #self.subtasks = [task1, task2]

    def sub_callback(self, caller):
        self.subtasks.remove(caller)
                  
    def pre_loop(self):
        for t in self.subtasks:
            t.start()

    def loop(self):
        if len(self.subtasks) > 0:
            self.subtasks[0].join()
        else:
            self.stop()

    def stop(self, ty=None):
        if ty is not None:
            for t in self.subtasks:
                if isinstance(t, ty):
                    t.stop()
                elif isinstance(t, SeqCompoundTask) or isinstance(t, ParCompoundTask):
                    t.stop(ty)
        else:
            self.stopping = True
            for t in self.subtasks:
                t.stop()

class FollowTourTask(SeqCompoundTask):

    def __init__(self, drone, callback, context=None, the_map=None):
        SeqCompoundTask.__init__(self, drone, callback, context)
        if the_map is None:
            if os.path.isfile('./testdata/map.data'):
                fileObj = open('./testdata/map.data')
                self.map = pickle.load(fileObj)
            else:
                self.map = map.PosMap()
        else:
            self.map = the_map
       
        self.tour = self.map.tour
        self.positions = self.map.positions
        self.subtasks = self.create_subtasks()

    def create_subtasks(self):
        res = []
        for i in range(len(self.tour)):

            if i+2 > len(self.tour)-1:
                turn_angle = 0
            else:
                previous = self.tour[i]
                current = self.tour[i+1]
                next = self.tour[i+2]

                x1 = current[1] - previous[1]
                y1 = current[2] - previous[2]
                
                x2 = next[1] - current[1]
                y2 = next[2] - current[2]
                
                dp = x1*x2 + y1*y2
                
                turn_angle = (math.atan2(y2,x2) - math.atan2(y1,x1))/d2r

                print '(',x1, ',', y1, ')\r'
                print '(',x2, ',', y2, ')\r'
                print '**************\r'
           
            print turn_angle, '\r'
            t = ParCompoundTask(self.drone, self.sub_callback, self.context)
            h = HoverTrackTask(t.drone, t.sub_callback, t.context)
            h.psi_offset = turn_angle
            
            t.subtasks.append(h)

            res.append(t)

        res.append(LandTask(self.drone,self.sub_callback, self.context, 5))
        return res

def get_all_tasks():
    print vars()['Task'].__subclasses__()

