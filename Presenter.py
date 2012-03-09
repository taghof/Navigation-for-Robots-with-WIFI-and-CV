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

import math
import sys
import pygame
import datetime
import threading
import Utils
import Drone
import cv
import time
import random
import WifiReceiver
import pango
from collections import OrderedDict
from copy import deepcopy

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

class PresenterGui(object):
    def __init__(self, drone):

        gobject.threads_init()

        self.drone = drone
	self.wifisensor = drone.getWifiSensor()
	self.videosensor = drone.getVideoSensor()
	self.navdatasensor = drone.getNavdataSensor()
        self.controllerManager = drone.getControllerManager()

	self.stopping = False
	self.show_targets = False
	self.show_significance = False

        # Glade stuff ---------
	# Set the Glade file
        self.gladefile = "demogui.glade"  
        self.wTree = gtk.glade.XML(self.gladefile)
        self.window = self.wTree.get_widget("mainWindow")

        if self.window:
            self.window.connect("destroy", self.stop)#gtk.main_quit)

        self.drawing = self.wTree.get_widget("draw1")
	self.drawing.connect("configure-event", self.configure_event)
	self.drawing.connect("expose-event", self.expose_event)
	

	self.radiobutton1 = self.wTree.get_widget("radiobutton1")
	self.radiobutton2 = self.wTree.get_widget("radiobutton2")
	self.radiobutton3 = self.wTree.get_widget("radiobutton3")

	self.button1 = self.wTree.get_widget("button1")
	self.button2 = self.wTree.get_widget("button2")
	self.button3 = self.wTree.get_widget("button3")

	self.radiobutton1.connect("toggled", self.handleRadioButtons)
	self.radiobutton2.connect("toggled", self.handleRadioButtons)
	self.radiobutton3.connect("toggled", self.handleRadioButtons)

	# our frame
	self.video_frame = VideoWindow(self.videosensor)   	
	self.video_frame.hide_on_delete()

	self.video_window = gtk.Window(gtk.WINDOW_TOPLEVEL)
	self.video_window.set_title("Video feed")
	self.video_window.set_size_request(300, 360)
	self.video_window.set_border_width(10)   
	self.window.connect('key_press_event', self.handleKeyPressed) 

	self.video_window.connect('key_press_event', self.handleKeyPressed) 
	self.video_window.connect("delete-event", self.toggleVideoWindow)

	self.video_window.add(self.video_frame)

	# Create our dictionary and connect it
        dic = {"btn1OnClick" : self.toggleVideoWindow,
	       "btn2OnClick" : self.toggleTargets,
	       "btn3OnClick" : self.toggleSignificance,
	       "btn4OnClick" : self.takeSample,
	       "btn5OnClick" : self.setTarget,
	       "btn6OnClick" : self.toggleCapture}
	
        self.wTree.signal_autoconnect(dic)
	gtk.quit_add(0, self.drone.stop)

    def start(self):
	    print "Starting GUI\r"
	    self.window.show()
	    self.gc = gtk.gdk.GC(self.drawing.window)
	    self.loadControllers(self.controllerManager.getControllers())
	    self.video_frame.start_video()
	    gobject.timeout_add(100, self.updateWifi, None, None)
	    gtk.main()
	   
    def loadControllers(self, controllers):
	    for con in controllers:
		    if con.getControlMethod() != None:
			    meth = con.getControlMethod()
			    gobject.idle_add(meth)

    def stop(self, derp, herp=None):
	    print "Shutting down GUI"
	    gtk.main_quit()
	    return True

    def takeSample(self, widget):
	    self.drone.getWifiSensor().recordSample()
	    self.drone.getVideoSensor().recordSample()

    def setTarget(self, widget):
	    self.drone.getWifiSensor().setTargetSample()
	    self.drone.getVideoSensor().setTargetSample()

    def toggleVideoWindow(self, widget, derp=None):
	    if widget == None:
		    self.button1.set_active(not self.button1.get_active())
		    return True

	    if self.video_window.get_visible():
		 
		    self.video_frame.video_enabled_button.set_active(False)	
		    self.video_window.hide()
		    return True
	    else:
		    self.video_window.show_all()
		    return True

    def toggleTargets(self, widget, derp=None):
	    if widget == None:
		    self.button2.set_active(not self.button2.get_active())
		    return True
	    self.show_targets = not self.show_targets

    def toggleCapture(self, widget, derp=None):
	    if widget == None:
		    self.button6.set_active(not self.button2.get_active())
		    return True
	    self.drone.getVideoSensor().toggleCapture()
	    self.drone.getWifiSensor().toggleCapture()
	    self.drone.getNavdataSensor().toggleCapture()

    def toggleSignificance(self, widget, derp=None):
	    if widget == None:
		    self.button3.set_active(not self.button3.get_active())
		    return True
	    self.show_significance = not self.show_significance

    def handleRadioButtons(self, radio):
	    if radio.get_active():
		    if radio.get_name() == "radiobutton1":
			    gobject.timeout_add(100, self.updateWifi, radio, None)
		    elif radio.get_name() == "radiobutton2":
			    gobject.timeout_add(100, self.updateSamples, radio, None)
		    elif radio.get_name() == "radiobutton3":
			    gobject.timeout_add(100, self.updateNavdata, radio, None)
		 

    def handleKeyPressed(self, widget, event):
	    keyname = gtk.gdk.keyval_name(event.keyval)
	   
	    if keyname == "Escape":
		    self.stop(None)
	    elif keyname == "v":
		    self.toggleVideoWindow(None)
	    elif keyname == "w":
		    self.radiobutton1.set_active(True)
	    elif keyname == "s":
		    self.radiobutton2.set_active(True)
	    elif keyname == "p":
		    self.toggleTargets(None, None)
	    elif keyname == "t":
		    self.setTarget(None)
	    elif keyname == "r":
		    self.takeSample(None)
    
    def updateSamples(self, widget, derp):
	    
        wifisamples = self.drone.getWifiSensor().getSamples()
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
			pixmap.draw_rectangle(self.gc,False,int(current_x), int(current_y), int(fig_width), int(fig_height))
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
					pixmap.draw_rectangle(self.gc, True, int(current_int_x+1), int(current_y+(fig_height-figval)), int(colwidth), int(figval-1)) 
					
					current_int_x += (colwidth + colspace)
				else:
					current_int_x += (colwidth + colspace)
				
			current_x += (margin+fig_width)
			i += 1

	self.drawing.queue_draw()
	return self.radiobutton2.get_active()


    def updateWifi(self, herp, derp):
        self.wifimap_current = self.wifisensor.getData()       

	x, y, width, height = self.drawing.get_allocation()
	pixmap.draw_rectangle(self.drawing.get_style().white_gc,
			      True, 0, 0, width, height)

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
		target = self.wifisensor.getTargetSample()
			
		for k, v in self.wifimap_current.iteritems():
                		
			figval = int((75+v[0])*(float(fig_height)/float(75)))
			
			r = int(65535.0-((75.0+float(v[0]))*(65535.0/75.0)))
			g = int((75.0 + float(v[0]))*(65535.0/75.0))
			b = 0
			
			color1 = colormap.alloc_color(gtk.gdk.Color(0, 0, 0))
			color2 = colormap.alloc_color(gtk.gdk.Color(r, g, b))
			color3 = colormap.alloc_color(gtk.gdk.Color(65535, 65535, 65535))
			color4 = colormap.alloc_color(gtk.gdk.Color(0, 65535, 0))

			self.gc.set_foreground(color1)
			pixmap.draw_rectangle(self.gc, False, int(current_x), int(current_y), int(fig_width+1), int(fig_height+1))
			
			if self.show_significance:
				self.gc.set_foreground(color4)
			else:
				self.gc.set_foreground(color2)
			
			pixmap.draw_rectangle(self.gc, True, int(current_x+1), int(current_y+(fig_height-figval)+1), int(fig_width), int(figval))
			
			# Calculate significance and set alpha value accordingly
			threshold = 20
			current_time = datetime.datetime.now()
			signal_time = v[1]
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
				tval = int((75.0+tv[0])*(float(fig_height)/75.0))
				pixmap.draw_line(self.gc, int(current_x), int(current_y+(fig_height-tval)), int(current_x+fig_width), int(current_y+(fig_height-tval)))

			index+=1
			current_x += (internal_margin + fig_width)
			if(index == len_of_rows):
				current_x = x_margin
				current_y += row_height
				index = 0;
		
		self.drawing.queue_draw()
		return self.radiobutton1.get_active()

    def updateNavdata(self, herp, derp):
        navdata = self.navdatasensor.getData()       

	x, y, width, height = self.drawing.get_allocation()
	pixmap.draw_rectangle(self.drawing.get_style().white_gc,
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

		gc = self.drawing.get_style().black_gc
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
	
class VideoWindow(gtk.Frame):

        def __init__(self, videosensor):

                gtk.Frame.__init__(self, "Video Source")
		self.videosensor = videosensor

                master_vbox = gtk.VBox(False, 5)
                master_vbox.set_border_width( 5 )
                self.add( master_vbox )

                video_frame = gtk.Frame()
                self.video_image = gtk.Image()

                master_vbox.pack_start(video_frame, False, False)
                video_frame.add(self.video_image)

                # -----------------------------------

                self.video_enabled_button = gtk.ToggleButton("Play Video")
                self.video_enabled_button.connect("clicked", self.cb_toggle_video)
		self.video_capture_button = gtk.ToggleButton("Capture Video Packets")
                self.video_capture_button.connect("clicked", self.cb_capture_video)
            
		master_vbox.pack_start(self.video_enabled_button, False, False)
		master_vbox.pack_start(self.video_capture_button, False, False)
		self.video_enabled_button.show()
                # -----------------------------------

                #self.inverted_video = gtk.CheckButton("Invert video")
                #master_vbox.pack_start(self.inverted_video, False, False)

                # -----------------------------------


                self.capture = None


                master_vbox.show_all()

        # -----------------------------------

        def start_video(self, derp1=None, derp2=None):
		
		video_dimensions = [320, 240]
                device = 0
		self.initialize_video()

        def initialize_video(self):

                webcam_frame = self.videosensor.getData()

                if not webcam_frame:
                        print "Frame acquisition failed."
                        return False

                self.webcam_pixbuf = gtk.gdk.pixbuf_new_from_data(
                        webcam_frame.tostring(), 
                        gtk.gdk.COLORSPACE_RGB,
                        False,
                        8,
                        webcam_frame.width,
                        webcam_frame.height,
                        960)
                
		self.video_image.set_from_pixbuf(self.webcam_pixbuf)


                self.display_frame = cv.CreateImage( (webcam_frame.width, webcam_frame.height), cv.IPL_DEPTH_8U, 3)
	
		return True

        # -----------------------------------

        def cb_toggle_video(self, widget):
                if widget.get_active():
                        gobject.timeout_add(150, self.run )
			#gobject.idle_add(self.run )

	def cb_capture_video(self, widget):
		self.videosensor.toggleCapture()


        # -------------------------------------------

        def run(self):
		#print "showing\r"
		webcam_frame = self.videosensor.getData()

		incoming_pixbuf = gtk.gdk.pixbuf_new_from_data(
                        webcam_frame.tostring(),
                        gtk.gdk.COLORSPACE_RGB,
                        False,
                        8,
                        webcam_frame.width,
                        webcam_frame.height,
                        960)

		self.video_image.set_from_pixbuf(incoming_pixbuf)
                self.video_image.queue_draw()

                return self.video_enabled_button.get_active()
