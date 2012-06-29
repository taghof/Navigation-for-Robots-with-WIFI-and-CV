#!/usr/bin/env python2.7
#
#    Copyright (c) 2012 Morten Daugaard
#
#    Permission is hereby granted, free of charge, to any person obtaining a copy
#    of this software and associated documentation files (the "Software"), to deal
#    in the Software without restriction, including without limitation the rights
#    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#    copies of the Software, and to permit persons to whom the Software is
#    furnished to do so, subject to the following conditions:
#
#    The above copyright notice and this permission notice shall be included in
#    all copies or substantial portions of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#    THE SOFTWARE.

import sys
import math
import datetime
import threading
import time
import random
from collections import OrderedDict
#from copy import deepcopy
try:
    import pygtk
    pygtk.require("2.0")
except:
    pass
try:
    import gtk
    import gobject
    import gtk.glade
    import gtk.gdk
except:
    sys.exit(1)

import cv2.cv as cv
import cv2
import pango
import numpy as np
import utils
import settings
import matcher

class PresenterGui(object):


    def __init__(self, drone=None):
            
        gobject.threads_init()
        if drone is not None:
            self.drone = drone
        else:
            import drone
            self.drone = drone.main()
 
        self.sensors = self.drone.get_sensors()
	self.wifi_sensor = self.drone.get_wifi_sensor()
	self.video_sensor = self.drone.get_video_sensor()
	self.navdata_sensor = self.drone.get_navdata_sensor()
        self.controller_manager = self.drone.get_controller_manager()

	self.show_targets = False
	self.show_significance = False

        # Glade stuff ---------
	# Set the Glade file
        self.gladefile = "demogui.glade"  
        self.wTree = gtk.glade.XML(self.gladefile)
        self.window = self.wTree.get_widget("mainWindow")

        if self.window:
            self.window.connect("destroy", self.stop)#gtk.main_quit)
            self.window.connect('key_press_event', self.handle_key_pressed) 

        self.drawing = self.wTree.get_widget("draw1")
	self.drawing.connect("configure-event", self.configure_event)
	self.drawing.connect("expose-event", self.expose_event)

	self.radiobutton1 = self.wTree.get_widget("radiobutton1")
	self.radiobutton2 = self.wTree.get_widget("radiobutton2")
	self.radiobutton3 = self.wTree.get_widget("radiobutton3")
	self.radiobutton4 = self.wTree.get_widget("radiobutton4")

	self.button1 = self.wTree.get_widget("button1")
	self.button2 = self.wTree.get_widget("button2")
	self.button3 = self.wTree.get_widget("button3")
        self.button4 = self.wTree.get_widget("button4")

	self.radiobutton1.connect("toggled", self.handle_radiobuttons_pressed)
	self.radiobutton2.connect("toggled", self.handle_radiobuttons_pressed)
	self.radiobutton3.connect("toggled", self.handle_radiobuttons_pressed)
	self.radiobutton4.connect("toggled", self.handle_radiobuttons_pressed)

	# The video window
	self.video_window = VideoWindow(self.video_sensor, self.controller_manager.get_controller(settings.AUTOCONTROL))   	
	self.video_window.hide_on_delete()
	self.video_window.connect('key_press_event', self.handle_key_pressed) 
	self.video_window.connect("delete_event", self.toggle_video_window)

	# Create our dictionary and connect it
        dic = {"btn1OnClick" : self.toggle_video_window,
	       "btn2OnClick" : self.toggle_targets,
	       "btn3OnClick" : self.toggle_significance,
	       "btn4OnClick" : self.take_sample,
	       "btn5OnClick" : self.set_target,
	       "btn6OnClick" : self.toggle_capture,
               "btn7OnClick" : self.start_auto_track}
	
        self.wTree.signal_autoconnect(dic)
	gtk.quit_add(0, self.drone.stop, True)

    def show(self):
        print "Starting GUI\r"
        self.window.show()
        self.gc = gtk.gdk.GC(self.drawing.window)
        self.white_gc = self.drawing.get_style().white_gc
        self.black_gc = self.drawing.get_style().black_gc
#        self.load_controllers(self.controller_manager.get_controllers())
        self.radiobutton3.set_active(True)
        #gobject.timeout_add(200, self.update_navdata, None)
        gtk.main()
	   
    def stop(self, widget, event=None):
        print "Shutting down GUI\r"
        gtk.main_quit()
        return True

    def load_controllers(self, controllers):
        for con in controllers:
            if con.get_control_method() is not None:
                meth = con.get_control_method()
                gobject.idle_add(meth)
               
    def take_sample(self, widget):
        for sensor in self.sensors:
            sensor.record_sample()
        
    def set_target(self, widget):
        for sensor in self.sensors:
            sensor.record_target_sample()

    def toggle_capture(self, widget):
        if widget is None:
            self.button6.set_active(not self.button2.get_active())
            return True
        for sensor in self.sensors:
            sensor.toggle_capture()
       
    def toggle_video_window(self, widget, event=None):
        if widget is None:
            self.button1.set_active(not self.button1.get_active())
            return True
        if event is not None:
            self.button1.set_active(not self.button1.get_active())
            self.video_window.hide()
            return True

        if self.video_window.get_visible():
            self.video_window.video_play_button.set_active(False)	
            self.video_window.hide()
            return True
        else:
            self.video_window.init_video()
            self.video_window.show_all()
            self.video_window.video_play_button.set_active(True)	
            return True

    def toggle_targets(self, widget): 
        if widget is None:
            self.button2.set_active(not self.button2.get_active())
            return True
        self.video_window.toggle_targets(None)
        self.show_targets = not self.show_targets

    def toggle_significance(self, widget): 
        if widget is None:
            self.button3.set_active(not self.button3.get_active())
            return True
        self.show_significance = not self.show_significance

    def start_auto_track(self, widget):
        auto_con = self.controller_manager.get_controller(settings.AUTOCONTROL)
        if not auto_con is None:
            auto_con.toggle_mark_search()
        else:
            print 'Auto controller not present!'

    def handle_radiobuttons_pressed(self, radio):
        if radio.get_active():
            if radio.get_name() == "radiobutton1" and self.wifi_sensor is not None:
                gobject.timeout_add(200, self.update_wifi, radio)
            elif radio.get_name() == "radiobutton2" and self.wifi_sensor is not None:
                gobject.timeout_add(200, self.update_samples, radio)
            elif radio.get_name() == "radiobutton3" and self.navdata_sensor is not None:
                #print 'started timer\r'
                #utils.PeriodicTimer(5, 10, self.time_psi).start()
                #threading.Timer(20, self.time_psi).start()
                gobject.timeout_add(200, self.update_navdata, radio)
            elif radio.get_name() == "radiobutton4" and self.navdata_sensor is not None and self.wifi_sensor is not None and self.video_sensor is not None:
                gobject.timeout_add(200, self.update_matching, radio)

    def handle_key_pressed(self, widget, event):
        keyname = gtk.gdk.keyval_name(event.keyval)
        
        if keyname == "Escape":
            self.stop(widget)
        elif keyname == "v":
            self.toggle_video_window(None)
        elif keyname == "w":
            self.radiobutton1.set_active(True)
        elif keyname == "s":
            self.radiobutton2.set_active(True)
        elif keyname == "p":
            self.toggle_targets(None)
        elif keyname == "t":
            self.set_target(None)
        elif keyname == "r":
            self.take_sample(None)
        elif keyname == "5":
            self.wifi_sensor.record_samples(5, 5)
        elif keyname == "m":
            self.wifi_sensor.match_current_wifi_sample()
   


    def show_map(self, widget):
        pass

    def update_matching(self, widget):
        match_val_video = self.video_sensor.match_target_sample()
        match_val_wifi = self.wifi_sensor.match_target_sample()
        match_val_navdata = 1

        x, y, width, height = self.drawing.get_allocation()
	pixmap.draw_rectangle(self.drawing.get_style().white_gc,
			      True, 0, 0, width, height)

        match_string = ""
        if match_val_video is not None:
            match_string += "Video Match:\t\t" + str(match_val_video*100) + "\r\r"
        if match_val_wifi is not None:
            match_string += "Wifi Match:\t\t" + str(match_val_wifi) + "\r\r"
        if match_val_navdata is not None:
            match_string += "Navdata Match:\t" + str(match_val_navdata) + "\r\r"
          
        colormap = gtk.gdk.colormap_get_system()
        color_black = colormap.alloc_color(gtk.gdk.Color(0, 0, 0))
        color_white = colormap.alloc_color(gtk.gdk.Color(65535, 65535, 65535))
        color_red = colormap.alloc_color(gtk.gdk.Color(65535, 0, 0))
        color_green = colormap.alloc_color(gtk.gdk.Color(0, 65535, 0))
        color_yellow = colormap.alloc_color(gtk.gdk.Color(65535, 65535, 0))
        margin = 25
        current_x = margin
        current_y = margin

        font_desc = pango.FontDescription('Serif 12')
        layout = self.drawing.create_pango_layout(match_string)
            
        # layout = self.drawing.create_pango_layout("derpa")
        layout.set_font_description(font_desc)
        # draw text below rectangle
        pixmap.draw_layout(self.gc, current_x, current_y, layout)

	self.drawing.queue_draw()
	return self.radiobutton4.get_active()

    def update_samples(self, widget):
        if self.wifi_sensor is None:
            print "Wifi sensor not present"
            return False
       
        wifisamples = self.wifi_sensor.get_samples()
        wifisamples_num = len(wifisamples)
	colormap = gtk.gdk.colormap_get_system()
        a = []
        for t, d in wifisamples.iteritems():
            a.extend(d.keys())
        sources = set(a)

	x, y, width, height = self.drawing.get_allocation()
	pixmap.draw_rectangle(self.drawing.get_style().white_gc,
			      True, 0, 0, width, height)
        
        if len(sources) > 0:
            self.size = self.drawing.window.get_size()
            margin = 25
            
            colwidth = 5
            colspace = 5
	
            current_x = margin
            current_y = margin
        
            w = (wifisamples_num+1)*colspace + (wifisamples_num*colwidth) + margin
            s = self.size[0]-margin
            num_cols = int(s/w)
            num_rows =  math.ceil(float(len(sources)) / float(num_cols))
            
            fig_width = w-margin
            fig_height = int((self.size[1]-(num_rows+1)*margin)/num_rows)
        
            i = 0
            for source in sources:
                if (i % num_cols == 0) and i != 0:
                    current_x = margin
                    current_y += (margin+fig_height)

                color1 = colormap.alloc_color(gtk.gdk.Color(0, 0, 0))
                color3 = colormap.alloc_color(gtk.gdk.Color(65535, 65535, 65535))

                # print surrounding rectangle
                self.gc.set_foreground(color1)
                pixmap.draw_rectangle(self.gc,False,
                                      int(current_x), int(current_y), 
                                      int(fig_width), int(fig_height))

                # print signal strength cols in rectangle
                current_int_x = current_x + colspace
                for time, sample in wifisamples.iteritems():
               
                    if sample.has_key(source):
                        v = sample.get(source)[0]
                        t = sample.get(source)[1]
                    
                        figval = int((75+v)*(float(fig_height)/float(75)))
                        r = int(65535-((75+v)*(float(65535)/float(75))))
                        g = int((75+v)*(float(65535)/float(75)))
                        b = 0
                        color2 = colormap.alloc_color(gtk.gdk.Color(r, g, b))

                        self.gc.set_foreground(color2)
                        pixmap.draw_rectangle(self.gc, True, int(current_int_x+1), 
                                              int(current_y+(fig_height-figval)), 
                                              int(colwidth), int(figval-1)) 
					
                        current_int_x += (colwidth + colspace)
                    else:
                        current_int_x += (colwidth + colspace)

                    target = self.drone.get_wifi_sensor().get_target_sample()
                    if self.show_targets and target and target.has_key(source):
                        self.gc.set_foreground(color1)
                        tv = target.get(source)
                        tval = int((75.0+tv[0])*(float(fig_height)/75.0))
                        pixmap.draw_line(self.gc, int(current_x), 
                                         int(current_y+(fig_height-tval)), 
                                         int(current_x+fig_width), 
                                         int(current_y+(fig_height-tval)))

                current_x += (margin+fig_width)
                i += 1

	self.drawing.queue_draw()
	return self.radiobutton2.get_active()


    def update_wifi(self, widget):
        if self.wifi_sensor is None:
            print "Wifi sensor not present"
            return False
       
        self.wifimap_current = self.wifi_sensor.get_data()       

	x, y, width, height = self.drawing.get_allocation()
	pixmap.draw_rectangle(self.white_gc, True, 0, 0, width, height)

	if self.wifimap_current and len(self.wifimap_current) > 0 and self.drawing.window:
		
            colormap = gtk.gdk.colormap_get_system()
            len_of_rows = 10
            num_of_sources = len(self.wifimap_current)
            num_of_rows = math.ceil(float(num_of_sources)/float(len_of_rows))
            x_margin = 25
            y_margin = 25
            internal_margin = 10
            self.size = self.drawing.window.get_size()
            x_available = self.size[0]- 2*x_margin
            y_available = self.size[1]- 2*y_margin
            current_x = x_margin
            current_y = y_margin
        
            row_height = int(y_available/num_of_rows)
            fig_height = int(row_height - 20)
            fig_width = int((x_available -((len_of_rows-1)*internal_margin))/len_of_rows)
            index = 0
            target = self.wifi_sensor.get_target_sample()
                
            for k, (val, last_updated, avg_update_time, update_num, last10, avg_val) in self.wifimap_current.iteritems():
              
                figval = int((75+avg_val)*(float(fig_height)/float(75)))
		
                r = int(65535.0-((75.0+float(val))*(65535.0/75.0)))
                g = int((75.0 + float(val))*(65535.0/75.0))
                b = 0
			
                color1 = colormap.alloc_color(gtk.gdk.Color(0, 0, 0))
                color2 = colormap.alloc_color(gtk.gdk.Color(r, g, b))
                color3 = colormap.alloc_color(gtk.gdk.Color(65535, 65535, 65535))
                color4 = colormap.alloc_color(gtk.gdk.Color(0, 65535, 0))

                self.gc.set_foreground(color1)
                # draw surrounding rectangle
                pixmap.draw_rectangle(self.gc, False, int(current_x), int(current_y), int(fig_width+1), int(fig_height+1))
                
                          
                if self.show_significance:
                    self.gc.set_foreground(color4)
                else:
                    self.gc.set_foreground(color2)
			
                pixmap.draw_rectangle(self.gc, True, int(current_x+1), int(current_y+(fig_height-figval)+1), int(fig_width), int(figval))
			
                # Calculate significance and set alpha value accordingly
                threshold = 5
                current_time = datetime.datetime.now()
                signal_time = last_updated
                delta_time = (current_time - signal_time).total_seconds()
           
                if 0 < delta_time < threshold :
                    significance = (threshold-delta_time) / threshold
                elif delta_time > threshold:
                    significance = 0
                else:
                    significance = 1
			
                if self.show_significance:
                    c = pixmap.cairo_create()
                    c.set_source_rgba(1,1,1, 1-significance)
                    c.rectangle(int(current_x+1), int(current_y+(fig_height-figval)+1), int(fig_width), int(figval))
                    c.fill()
	                        
                # print target bars if requested
                if self.show_targets and target and target.has_key(k):
                    self.gc.set_foreground(color1)
                    tv = target.get(k)
                    tval = int((75.0+tv[5])*(float(fig_height)/75.0))
                    pixmap.draw_line(self.gc, int(current_x), int(current_y+(fig_height-tval)), int(current_x+fig_width), int(current_y+(fig_height-tval)))
                    
                # text matter
                self.gc.set_foreground(color1)
                font_desc = pango.FontDescription('Serif 8')
                layout = self.drawing.create_pango_layout("sig:\r" + str(last10.get_avg()))
                layout.set_font_description(font_desc)
                # draw text below rectangle
                pixmap.draw_layout(self.gc, current_x+4, int(current_y+(fig_height/4)), layout)
                layout.set_text("dev:\r" + str(round(last10.get_std_dev(), 2)))
                pixmap.draw_layout(self.gc, current_x+4, int(current_y+(fig_height/4)+25), layout)
                layout.set_text("avg up:\r" + str(round(avg_update_time, 2)))
                pixmap.draw_layout(self.gc, current_x+4, int(current_y+(fig_height/4)+50), layout)


                index+=1
                current_x += (internal_margin + fig_width)
                if(index == len_of_rows):
                    current_x = x_margin
                    current_y += row_height
                    index = 0;

            if self.show_targets and target:
                match_val = self.wifi_sensor.match_target_sample()
                font_desc = pango.FontDescription('Serif 8')
                layout = self.drawing.create_pango_layout("Current Match value: " + str(match_val))
                pixmap.draw_layout(self.gc, x_margin, current_y+fig_height+10, layout)
           	
        self.drawing.queue_draw()
        return self.radiobutton1.get_active()

    def update_navdata(self, widget):
        if self.navdata_sensor is None:
            print "Navdata sensor not present"
            return False
       
        navdata = self.navdata_sensor.get_data()       

	x, y, width, height = self.drawing.get_allocation()
	pixmap.draw_rectangle(self.white_gc,
			      True, 0, 0, width, height)

	if navdata and self.drawing.window:
		
            vx      = navdata.get(0, dict()).get('vx', 0)
            vy      = navdata.get(0, dict()).get('vy', 0)
            vz      = navdata.get(0, dict()).get('vz', 0)
            theta   = navdata.get(0, dict()).get('theta', 0)
            phi     = navdata.get(0, dict()).get('phi', 0)
            psi     = navdata.get(0, dict()).get('psi', 0)
            bat     = navdata.get(0, dict()).get('battery', 0)
            alt     = navdata.get(0, dict()).get('altitude', 0)
            state   = navdata.get(0, dict()).get('ctrl_state', 0)
            frames  = navdata.get(0, dict()).get('num_frames', 0)

            # drone state
            us      = "FAIL" if navdata.get('drone_state', dict()).get('ultrasound_mask') else "OK"
            angles  = "FAIL" if navdata.get('drone_state', dict()).get('angles_out_of_range') else "OK"
            cutout  = "FAIL" if navdata.get('drone_state', dict()).get('cutout_mask') else "OK"
            motors  = "FAIL" if navdata.get('drone_state', dict()).get('motors_mask') else "OK"
            coms    = "FAIL" if navdata.get('drone_state', dict()).get('com_lost_mask') else "OK"
            # navdata.get('drone_state', dict()).get('')
            # navdata.get('drone_state', dict()).get('')

            gc = self.black_gc
            colormap = gtk.gdk.colormap_get_system()
            x_margin = 25
            y_margin = 25
            internal_margin = 10
            self.size = self.drawing.window.get_size()
            x_available = self.size[0]- 2*x_margin
            y_available = self.size[1]- 2*y_margin
            current_x = x_margin
            current_y = y_margin
        			
            color1 = colormap.alloc_color(gtk.gdk.Color(0, 0, 0))
            color3 = colormap.alloc_color(gtk.gdk.Color(65535, 65535, 65535))
            color4 = colormap.alloc_color(gtk.gdk.Color(0, 65535, 0))

            # create a font description
            font_desc = pango.FontDescription('Serif 12')

            # create a layout for your drawing area
            layout = self.drawing.create_pango_layout('vx:\t\t\t' + str(vx) + '\t\tvy:\t\t' + str(vy) + '\t\tvz:\t\t' + str(vz))
            # tell the layout which font description to use
            layout.set_font_description(font_desc)
            # draw the text with the draw_layout method
            pixmap.draw_layout(gc, 25, current_y, layout)
            current_y += 25

            layout.set_text('Theta:\t\t' + str(theta) + '\t\tPhi:\t\t' + str(phi) + ' \t\tPsi:\t\t' + str(psi))
            pixmap.draw_layout(gc, 25, current_y, layout)
            current_y += 25

            layout.set_text('Altitude:\t' + str(alt))
            pixmap.draw_layout(gc, 25, current_y, layout)
            current_y += 50

            layout.set_text('Battery:\t\t' + str(bat) + '\t\tFrames:\t' + str(frames) + '\tState:\t' + str(state))
            pixmap.draw_layout(gc, 25, current_y, layout)
            current_y += 50

            layout.set_text('Ultra sound:\t' + str(us))
            pixmap.draw_layout(gc, 25, current_y, layout)
            current_y += 25

            layout.set_text('Angles:\t\t' + str(angles))
            pixmap.draw_layout(gc, 25, current_y, layout)
            current_y += 25

            layout.set_text('Cut out:\t\t' + str(cutout))
            pixmap.draw_layout(gc, 25, current_y, layout)
            current_y += 25

            layout.set_text('Motors:\t\t' + str(motors))
            pixmap.draw_layout(gc, 25, current_y, layout)
            current_y += 25

            layout.set_text('Coms:\t\t' + str(coms))
            pixmap.draw_layout(gc, 25, current_y, layout)
            current_y += 25

            # layout.set_text('Ultra sound:\t' + str(us))
            # pixmap.draw_layout(gc, 25, 150, layout)


            # self.gc.set_foreground(color1)
            # pixmap.draw_rectangle(self.gc, False, int(current_x), int(current_y), 50, 50)
			
            # self.gc.set_foreground(color3)
            # pixmap.draw_rectangle(self.gc, True, int(current_x+1), int(current_y+1), 50, 50)
			
            # c = pixmap.cairo_create()
            # c.set_source_rgba(1,1,1, 0.5)
            # c.rectangle(int(current_x+1), int(current_y+10), 50, 50)
            # c.fill()
	        	

        self.drawing.queue_draw()
        return self.radiobutton3.get_active()


    def configure_event(self, widget, event):
        global pixmap
        x, y, width, height = widget.get_allocation()
        pixmap = gtk.gdk.Pixmap(widget.window, width, height)
        pixmap.draw_rectangle(widget.get_style().white_gc,
                              True, 0, 0, width, height)
        
        return True

    def expose_event(self, widget, event):
        x , y, width, height = event.area
        widget.window.draw_drawable(widget.get_style().fg_gc[gtk.STATE_NORMAL],
                                    pixmap, x, y, x, y, width, height)
	   
        return False
	


class VideoWindow(gtk.Window):

    """A specialized window class for displaying video from a videoreceiver, it takes a 
    video receiver reference in the constructor. The widget holds an image widget for 
    displaying video frames and a handfull of buttons for manipulation(graying, tracking and such)"""

    def __init__(self, video_sensor, autocontrol, drone=None):
        """
        Calls the Window super constructor, inits all the GTK gui elements and 
        hooks up all the signal callbacks"""

        gobject.threads_init()

        self.video_sensor = video_sensor
        self.autocontrol = autocontrol
        self.drone = drone

        gtk.Window.__init__(self)
        self.set_title("Video Source")
        self.set_position(gtk.WIN_POS_CENTER)
        self.set_size_request(360, 500)
       
        master_vbox = gtk.VBox(False, 5)
        master_vbox.set_border_width( 5 )
        self.add( master_vbox )
        
        self.video_image = gtk.Image()
        self.video_image.set_size_request(320, 240)
        self.video_image.set_alignment(0,0)
        self.video_eventbox = gtk.EventBox()
        self.video_eventbox.set_size_request(320, 240)
        self.video_eventbox.connect("motion_notify_event", self.motion_notify_event)
        self.video_eventbox.connect("button_press_event", self.button_press_event)
        self.video_eventbox.add(self.video_image)

        self.video_play_button = gtk.ToggleButton("Play Video")
        self.video_play_button.connect("clicked", self.toggle_video_play)
        self.video_play_button.set_active(True)
        self.video_capture_button = gtk.ToggleButton("Capture Video")
        self.video_capture_button.connect("clicked", self.toggle_video_capture)

        self.crosshairs_button = gtk.ToggleButton("Toggle Crosshairs")
        self.crosshairs_button.connect("clicked", self.toggle_crosshairs)

        self.get_features_button = gtk.ToggleButton("Find Features")
        self.get_features_button.connect("clicked", self.find_features)
        
        self.grayscale_button = gtk.ToggleButton("Toggle Grayscale")
        self.grayscale_button.connect("clicked", self.toggle_grayscale)

        self.move_button = gtk.ToggleButton("Start Move Task")
        self.move_button.connect("clicked", self.autocontrol.start_task)

        self.photo_button = gtk.Button("Save picture")
        self.photo_button.connect("clicked", self.save_picture)


        master_vbox.pack_start(self.video_eventbox, False, False)
        master_vbox.pack_start(self.video_play_button, False, False)
        master_vbox.pack_start(self.video_capture_button, False, False)
        master_vbox.pack_start(self.crosshairs_button, False, False)
        master_vbox.pack_start(self.get_features_button, False, False)
        master_vbox.pack_start(self.grayscale_button, False, False)
        master_vbox.pack_start(self.move_button, False, False)
        master_vbox.pack_start(self.photo_button, False, False)
        #self.video_play_button.show()

        master_vbox.show_all()

        # run flags for showing crosshairs and extracting new features
        self.show_crosshairs = True
        self.show_targets = False
        self.show_grayscale = False
        self.get_new_features = False
        
        self.connect("destroy", self.stop)#gtk.main_quit)
        self.connect('key_press_event', self.handle_key_pressed) 
        if not self.drone is None:
            gtk.quit_add(0, self.drone.stop, True)

    def show(self):
        self.init_video()
        gobject.timeout_add(750, self.run)
        #gobject.idle_add(self.run)
        gtk.Window.show(self)
        gtk.main()

    def stop(self, widget, event=None):
        print "Shutting down GUI\r"
        gtk.main_quit()
        return True

    def init_video(self):
        """
        This will setup the variales needed for feature tracking and get the first image
        from the video feed. The initial set of features is extracted to 'self.features'."""
        
        # Make sure we are getting a feed from the video sensor before beginning
        while self.video_sensor.get_data() is None:
            print "Frame acquisition failed.\r"
            time.sleep(0.1)

        # Get the first image from the video sensor
        input_image = self.video_sensor.get_data()
        width = input_image.width if type(input_image).__name__== 'iplimage' else input_image.shape[1]
        height = input_image.height if type(input_image).__name__== 'iplimage' else input_image.shape[0]
    
        # Create a pixbuf from the original iplimage, img must be 3-channeled
        self.input_pixbuf = gtk.gdk.pixbuf_new_from_data(
            input_image.tostring(), 
            gtk.gdk.COLORSPACE_RGB,
            False,
            8,
            width,
            height,
            width*3)
        
        # Set the image widget data from the pixbuf
        self.video_image.set_from_pixbuf(self.input_pixbuf)
        return True

    def print_points(self, tasks):
        points = []
        for t in tasks:
            if len(t.subtasks) == 0:
                if isinstance(t, tasks.HoverTrackTask):
                    p = t.get_point()
                    if p is not None:
                        points.append(p)
            else:
                points.extend(self.print_points(t.subtasks))
        
        return points

    def run(self):
        """
        The run method is primarily responsible for updating the image widget with
        new image data from the video receiver. As a part of development the method 
        also carries out optical flow tracking of features in 'self.features'."""

        # Get image from video sensor
        # input_image = self.autocontrol.last_match_image
        # if input_image is None:
        input_image = self.video_sensor.get_data()
        
        #points = self.print_points(self.autocontrol.active_tasks)

        width = input_image.width if type(input_image).__name__== 'iplimage' else input_image.shape[1]
        height = input_image.height if type(input_image).__name__== 'iplimage' else input_image.shape[0]
    
        middle_x = width / 2
        middle_y = height / 2
            
        # If we want to display the grayscale image in gtk we must change back to 3-channels
        if self.show_grayscale:
            input_image_gray = cv2.cvtColor(input_image, cv.CV_RGB2GRAY)
            input_image = cv2.cvtColor(input_image_gray, cv.CV_GRAY2RGB)

        # Add the target lines if requested
        if self.show_targets:
            target = self.video_sensor.get_target_sample()

            if target:
                lines = target[1]
                for line in lines:
                    cv2.line(input_image, line[0], line[1], (255,0,0))

        # Add crosshairs if requested
        if self.show_crosshairs:
            cv2.line(input_image, (middle_x, middle_y-10), (middle_x, middle_y+10), (255,0,0))
            cv2.line(input_image, (middle_x-10, middle_y), (middle_x+10, middle_y), (255,0,0))
        
        # for p in points:
        #     cv2.circle(input_image, (p[0], p[1]), 4, (0,255,0))

        incoming_pixbuf = gtk.gdk.pixbuf_new_from_data(
            input_image.tostring(), 
            gtk.gdk.COLORSPACE_RGB,
            False,
            8,
            width,
            height,
            width*3)
     
        # Copy the pixbuf image data to the image widget and request a draw
        self.video_image.set_from_pixbuf(incoming_pixbuf)
        self.video_image.queue_draw()

        return self.video_play_button.get_active()

    def save_picture(self, widget):
        im = self.video_sensor.get_data()
        im = input_image = cv2.cvtColor(im, cv.CV_RGB2BGR)
        cv.SaveImage( "images/pic.png", cv.fromarray(im))

    def handle_key_pressed(self, widget, event):
        keyname = gtk.gdk.keyval_name(event.keyval)
        
        if keyname == "Escape":
            self.stop(widget)
        elif keyname == "q":
            self.stop(widget)
        #     self.toggle_video_window(None)
        elif keyname == "k":
            self.autocontrol.kill_tasks()
    
    def get_features(self, frame):
        """
        Extracts features from 'frame' with the opencv SURF algorithm, the extracted
        features are returned as a list of (x,y) tuples."""
        print frame
        (keypoints, descriptors) = cv.ExtractSURF(frame, None, cv.CreateMemStorage(), (0, 20, 3, 1))
        new_features = []
        for ((x, y), laplacian, size, dir, hessian) in keypoints:
            new_features.append((x, y))
        return new_features

    def button_press_event(self, widget, event):
        """
        Mouse callback method. On a left click the method adds the mouse coordinates to the 
        tracked feature set"""
        if event.button == 1:
            x = int(event.x)
            y = int(event.y)
            #self.features.append((x,y))
            print "x: ", x, ", y: ", y, "\r"
            self.autocontrol.kill_tasks()
            self.autocontrol.start_auto_session((x,y))
        return True

    def motion_notify_event(self, widget, event):
        """
        Mouse callback method. Method does nothing important at this point, will print
        mouse coordinates if dragged"""
        if event.is_hint:
            x, y, state = event.window.get_pointer()
        else:
            x = event.x
            y = event.y
            state = event.state
   
        if state & gtk.gdk.BUTTON1_MASK:
            print "x: ", x, ", y: ", y, "\r"
           
        return True

    def toggle_video_play(self, widget):
        """
        Button callback method. Starts or stops updating of the image widget with data 
        from the video feed"""
        if widget.get_active():
            gobject.timeout_add(25000, self.run)
            #gobject.idle_add( self.run )

    def toggle_video_capture(self, widget):
        """
        Button callback method. Tells the video receiver to stop or start recording the requested frames
        (only requested frames are recorded)"""
        self.video_sensor.toggle_display_capture()

    def toggle_crosshairs(self, widget):
        """
        Button callback method. Toggles whether the run method should draw crosshairs on the current image"""
        self.show_crosshairs = not self.show_crosshairs

    def toggle_targets(self, widget):
        """
        Button callback method. Toggles whether the run method should draw target lines on the current image"""
        self.show_targets = not self.show_targets

    def toggle_grayscale(self, widget):
        """
        Button callback method. Toggles whether the run method should draw image as grayscale"""
        self.show_grayscale = not self.show_grayscale

    def find_features(self, widget):
        """
        Sets the get_new_features flag so that the run method will extract new 
        features from the current image and discard the old."""
        self.get_new_features = True


class ControllerWindow(gtk.Window):

    def __init__(self, controllers):
        gtk.Window.__init__(self)
        self.set_title("Controllers")
        self.set_position(gtk.WIN_POS_CENTER)
        self.set_size_request(360, 500)

        self.controllers = controllers
       
        master_vbox = gtk.VBox(False, 5)
        master_vbox.set_border_width( 5 )
        self.add( master_vbox )

        for controller in self.controllers:
            button = gtk.ToggleButton(controller.name)
            controller.set_control_button(button)

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
  a.shape = (im.height,im.width,im.nChannels) 
  return a 


if __name__ == '__main__':
    presenter = PresenterGui()
    presenter.show()
