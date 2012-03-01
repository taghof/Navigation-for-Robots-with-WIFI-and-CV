#!/usr/bin/env python2.7
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


DEBUG = False
GTKVAL = True


class Presenter(threading.Thread):    

    def __init__(self, test, drone):
        threading.Thread.__init__(self)
        
        pygame.init()
        self.lock = threading.Lock()
        self.stopping = False
        self.test = test
        self.drone = drone
        self.width = 640
        self.height = 480
        self.wifiscreen = None

        self.video = False
        self.wifi = False
        self.samples = False
        self.targets = False
        
        self.videosensor = drone.getVideoSensor()
        self.videoupdates = 0

        self.wifisensor = drone.getWifiSensor()
        self.wifiupdates = 0
        
        self.samplesupdates = 0
       
    def run(self):
        Utils.dprint(True, 'Starting presenter\r')
        while not self.stopping:
            cv.WaitKey(1)
	    print "in the loop"
            self.lock.acquire()

            if self.video:
                img = self.videosensor.getImage()
                
                if self.targets and self.videosensor.targetVideoSample != None:
                    lines = self.videosensor.getTargetVideoSample()[1]
                    for line in lines:
                        cv.Line(img, line[0], line[1], (255,0,0))
                cv.ShowImage('Video', img)
                cv.WaitKey(1)
                self.videoupdates += 1
                
            if self.wifi:
                self.updateWifi(self.wifiscreen)
                self.wifiupdates += 1

            if self.samples:
                self.updateSamples(self.wifiscreen)
                self.samplesupdates += 1
            
            self.lock.release()
            
    	
    def stop(self):
        Utils.dprint(True, 'Shutting down presenter thread\r')
        if self.video:
            self.toggleVideo()
        if self.samples:
            self.toggleSamples()
        self.stopping = True
        pygame.quit()

    def toggleTargets(self):
        self.targets = not self.targets
   
    def toggleVideo(self):
        self.lock.acquire()
        if self.video:
            self.video = False
            cv.DestroyAllWindows()
        else:
            cv.NamedWindow('Video')
            self.video = True
	    self.updateVideo()
        self.lock.release()

    def toggleWifi(self):
        self.lock.acquire()
        
        
        # startup case
        if not (self.wifi or self.samples):
            self.wifiscreen = pygame.display.set_mode((self.width, self.height))
            self.wifi = True
            self.updateWifi(self.wifiscreen)
        
        # close case
        elif self.wifi:
            self.wifi = False
            pygame.display.quit()
        
        # switch case
        elif self.samples:
            self.samples = False
            self.wifi = True
            self.updateWifi(self.wifiscreen)
       
        self.lock.release()

    def toggleSamples(self):
	    self.lock.acquire()

        # startup case
	    if not (self.wifi or self.samples):
		    self.wifiscreen = pygame.display.set_mode((self.width, self.height))
		    self.samples = True
		    self.updateSamples(self.wifiscreen)
      
        # close case
	    elif self.samples:
		    self.samples = False
		    pygame.display.quit()
            
        # switch case
	    elif self.wifi:
		    self.wifi = False
		    self.samples = True
		    self.updateSamples(self.wifiscreen)
       
	    self.lock.release()


    def updateWifi(self, screen):
	    self.wifimap_current = self.wifisensor.getWifiSignals()       
	    if len(self.wifimap_current) > 0:
		    screen.fill((0,0,0))
		    len_of_rows = 10
		    num_of_sources = len(self.wifimap_current)
		    num_of_rows = math.ceil(float(num_of_sources)/float(len_of_rows))
		    x_margin = 25
		    y_margin = 25
		    internal_margin = 10
		    x_available = 590
		    y_available = 430
		    current_x = x_margin
		    current_y = y_margin
        
		    row_height = y_available/num_of_rows
		    fig_height = row_height - 20
		    fig_width = (x_available -((len_of_rows-1)*internal_margin))/len_of_rows
		    index = 0
		    target = self.wifisensor.getTargetWifiSample()
		    font = pygame.font.SysFont("Times New Roman",8)
		    for k, v in self.wifimap_current.iteritems():
                            
			    figval = int((75+v[0])*(float(fig_height)/float(75)))
			    r = int(255.0-((75.0+float(v[0]))*(255.0/75.0)))
			    g = int((75.0 + float(v[0]))*(255.0/75.0))
			    b = 0
			    colors = pygame.Color(r, g, b)
           
			    fig1 = pygame.draw.rect(screen, (255,255,255),(current_x, current_y, fig_width, fig_height), 1)
			    fig2 = pygame.draw.rect(screen, colors, (current_x+1, current_y+(fig_height-figval), fig_width-2, figval-1), 1) 
               
                            # screen.fill(colors, fig2)
                
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
				    
				    alpha_val = int(255*significance)
				    w, h = int(fig_width-2), int(figval-1)
				    if w >= 0 and h >= 0:
					    s = pygame.Surface((w, h))
					    s.set_alpha(alpha_val)
					    s.fill(colors)
					    screen.blit(s, (current_x+1, current_y+(fig_height-figval)))

		    label = font.render(k,True,(0,255,255))
		    screen.blit(label, (current_x, current_y+fig_height+3+((index%3)*7)))
		    
                # print target bars if requested
		    if self.targets and target.has_key(k):
			    tv = target.get(k)
			    tval = int((75.0+tv[0])*(float(fig_height)/75.0))
			    pygame.draw.line(screen, (0,0,255), (current_x+1, current_y+(fig_height-tval-1)), (current_x-2+fig_width, current_y+(fig_height-tval-1)), 1)

		    index+=1
		    current_x += (internal_margin + fig_width)
		    if(index == len_of_rows):
			    current_x = x_margin
			    current_y += row_height
			    index = 0;

		    pygame.display.update()


    def updateSamples(self, screen):
        print "updating samples\r"
        screen.fill((0,0,0))
        wifisamples = self.drone.getWifiSensor().getWifiSamples()
        wifisamples_num = len(wifisamples)

        a = []
        for t, d in wifisamples.iteritems():
            a.extend(d.keys())
        sources = set(a)
        
        if len(sources) == 0:
            pygame.display.update()
            return

        margin = 25
       
        colwidth = 5
        colspace = 5
       
        current_x = margin
        current_y = margin
        
        w = (wifisamples_num+1)*colspace + (wifisamples_num*colwidth) + margin
        s = self.width-margin
        num_cols = int(s/w)
        num_rows =  math.ceil(float(len(sources)) / float(num_cols))
        
        fig_width = w-margin
        fig_height = int((self.height-(num_rows+1)*margin)/num_rows)
        
        i = 0
        for source in sources:
            if (i % num_cols == 0) and i != 0:
                current_x = margin
                current_y += (margin+fig_height)

            # print surrounding rectangle
            fig1 = pygame.draw.rect(screen, (255,255,255),(current_x, current_y, fig_width, fig_height), 1)
            # print signal strength cols in rectangle
            current_int_x = current_x + colspace
            for time, sample in wifisamples.iteritems():
               
                if sample.has_key(source):
                    v = sample.get(source)[0]
                    t = sample.get(source)[1]
                    
                    figval = int((75+v)*(float(fig_height)/float(75)))
                    colors = (255-((75+v)*(float(255)/float(75))),(75+v)*(float(255)/float(75)), 0)
                    fig2 = pygame.draw.rect(screen, colors, (current_int_x+1, current_y+(fig_height-figval), colwidth, figval-1), 1) 
                    screen.fill(colors, fig2)
                    current_int_x += (colwidth + colspace)
                else:
                    current_int_x += (colwidth + colspace)
                              
            current_x += (margin+fig_width)
            i += 1
            
        pygame.display.update()

 # TODO: implement the recording functionality around here
        # if self.RECORD:
        #     Utils.ensure_dir('./testdata')
        #     fps = 12
        #     width, height = int(320), int(240)
        #     fourcc = cv.CV_FOURCC('I','4','2','0')
        #     self.writer = cv.CreateVideoWriter('out.avi', fourcc, fps, (width, height), 1)

class PresenterGui(threading.Thread):    
    def __init__(self, drone):
        threading.Thread.__init__(self)
        gtk.gdk.threads_init()
        gobject.threads_init()
        self.drone = drone
	self.wifisensor = drone.getWifiSensor()
        self.stopping = False

	self.targets = False

        # Glade stuff ---------
	# Set the Glade file
        self.gladefile = "demogui.glade"  
        self.wTree = gtk.glade.XML(self.gladefile)
        self.window = self.wTree.get_widget("mainWindow")

        if self.window:
            #self.window.connect("destroy", gtk.main_quit)
            self.window.connect("delete-event", self.mainStop)#gtk.main_quit)

        self.drawing = self.wTree.get_widget("draw1")
        self.drawing.connect("expose-event", self.updateWifi)
	

	gobject.idle_add(self.updateWifi, None, None)

	# Create our dictionay and connect it
        dic = {"btn1OnClick" : self.onToggleVideo}
        self.wTree.signal_autoconnect(dic)


    def run(self):
        self.window.show()
	gtk.main()
        print "GUI shutdown\r\n\r"

    def mainStop(self, derp, herp):
	    #self.window.hide()
	    #gtk.main_quit()
	    gobject.idle_add(self.window.hide)
	    self.drone.stop()

    def stop(self):
        print "Shutting down GUI\r"
        gobject.idle_add(self.window.destroy)
        gobject.idle_add(gtk.main_quit)        
        time.sleep(1)
        
    def OnClick(self, widget):
	    print "Clicked\r"

    def onToggleVideo(self, widget):
	    self.drone.presenter.toggleVideo()

    def updateWifi(self, herp, derp):
	self.drawing.queue_draw()    
	self.wifimap_current = self.wifisensor.getWifiSignals()       
	if len(self.wifimap_current) > 0:
		    #screen.fill((0,0,0))
		#self.drawing.window.freeze_updates()
		#self.drawing.window.clear()
		self.gc = gtk.gdk.GC(self.drawing.window)
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
        
		row_height = y_available/num_of_rows
		fig_height = row_height - 20
		fig_width = (x_available -((len_of_rows-1)*internal_margin))/len_of_rows
		index = 0
		target = self.wifisensor.getTargetWifiSample()
		  
		for k, v in self.wifimap_current.iteritems():
                            
			figval = int((75+v[0])*(float(fig_height)/float(75)))
			r = int(65535.0-((75.0+float(v[0]))*(65535.0/75.0)))
			g = int((75.0 + float(v[0]))*(65535.0/75.0))
			b = 0
		
			color1 = colormap.alloc_color(gtk.gdk.Color(0, 0, 0))
			color2 = colormap.alloc_color(gtk.gdk.Color(r, g, b))
			color3 = colormap.alloc_color(gtk.gdk.Color(65535, 65535, 65535))

			self.gc.set_foreground(color1)
			self.drawing.window.draw_rectangle(self.gc, False, int(current_x), int(current_y), int(fig_width), int(fig_height))
			self.gc.set_foreground(color3)
			self.drawing.window.draw_rectangle(self.gc, True, int(current_x+1), int(current_y+1), int(fig_width-2), int(fig_height-2))
			self.gc.set_foreground(color2)
			self.drawing.window.draw_rectangle(self.gc, True, int(current_x+1), int(current_y+(fig_height-figval)), int(fig_width-2), int(figval-1))
		                
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
                
			alpha_val = int(255*significance)
                # w, h = int(fig_width-2), int(figval-1)
                # if w >= 0 and h >= 0:
                #     s = pygame.Surface((w, h))
                #     s.set_alpha(alpha_val)
                #     s.fill(colors)
                #     screen.blit(s, (current_x+1, current_y+(fig_height-figval)))

                # label = font.render(k,True,(0,255,255))
                # screen.blit(label, (current_x, current_y+fig_height+3+((index%3)*7)))
                
                # print target bars if requested
			if self.targets and target.has_key(k):
				tv = target.get(k)
				tval = int((75.0+tv[0])*(float(fig_height)/75.0))
                    # pygame.draw.line(screen, (0,0,255), (current_x+1, current_y+(fig_height-tval-1)), (current_x-2+fig_width, current_y+(fig_height-tval-1)), 1)

			index+=1
			current_x += (internal_margin + fig_width)
			if(index == len_of_rows):
				current_x = x_margin
				current_y += row_height
				index = 0;

            
		#self.drawing.window.thaw_updates()
		return True

    def draw(self, derp1, derp2):
        self.style = self.drawing.get_style()
        self.gc = self.style.fg_gc[gtk.STATE_NORMAL]
        self.drawing.window.draw_rectangle(self.gc, True, 3, 3, 30, 30)

def main():

    wifisensor = WifiReceiver.WifiReceiver(True)
    wifisensor.start()
    r = Presenter(None, None, wifisensor)
    r.start()
    r.showWifi()
    input = Utils.getChar()
    wifisensor.stop()
    wifisensor.join()
    r.stop() # kill process
    r.join()

if __name__ == '__main__':
    main()
