#!/usr/bin/env python

import pygtk
pygtk.require('2.0')
import gtk
import gobject
import operator
import time
import string
import map
import math
import os
import pickle
import newtasks as tasks
import inspect
import string
import drone
import presenter
import settings
import random
import copy
import copy_reg
import types

class TaskGUI(object):
    def __init__(self, drone):
        gobject.threads_init()
        
        self.drone = drone
        self.wifi_sensor = self.drone.get_wifi_sensor()
        self.posmap = self.drone.get_map()

        self.selected_position = None
        self.start_pos = None
        self.end_pos = None
       
        self.selected_segment = None
        self.tasks = []
        self.selected_task = None
        self.parent_task = None
        
        self.mode = 0
        self.world_mode = 2
        self.tour_mode = 1
        self.task_mode = 0

        self.world_mode_sub = 0
        
        self.select_mode = 0
        self.add_mode = 1
        self.del_mode = 2
        self.add_wifi_mode = 3
        self.clear_wifi_mode = 4

        self.dragging = False
        self.connecting = True

        self.parseStr = lambda x: x.isalnum() and x or x.isdigit() and int(x) or len(set(string.punctuation).intersection(x)) == 1 and x.count('.') == 1 and float(x) or x

    def show(self):
        self.build_gui()
        gtk.main()
                
    def build_gui(self):
        self.colormap = gtk.gdk.colormap_get_system()
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_title("Tour Creator 1.0")
        window.connect("destroy", self.stop)
        window.set_size_request(800, 600)
        
        self.video_window = presenter.VideoWindow(self.drone)   	
	self.video_window.hide_on_delete()
        #self.video_window.connect("delete_event", self.toggle_video_window)
        import tabbed
        self.tabs = tabbed.Tabs()
        self.tabs.connect("switch-page", self.set_mode, 'set mode')
        
        # Layout boxes
        self.master_vbox = gtk.VBox(False, 2)
        self.master_vbox.set_border_width( 5 )

        self.world_action_hbox = gtk.HBox(False, 2)
        self.world_action_hbox.set_border_width( 5 )

        self.tour_action_hbox = gtk.HBox(True, 2)
        self.tour_action_hbox.set_border_width( 5 )

        self.task_vbox = gtk.VBox(False, 2)
        self.task_vbox.set_border_width( 5 )

        self.task_action_hbox = gtk.HBox(True, 2)
        self.task_action_hbox.set_border_width( 5 )
        
        self.task_param_hbox = gtk.HBox(False, 2)
        self.task_param_hbox.set_border_width( 5 )

        self.task_vbox.add(self.task_action_hbox)
        self.task_vbox.add(self.task_param_hbox)
        
        # Action buttons - world edit
        self.world_select_button = gtk.ToggleButton("Select/Move")
        self.world_select_button.connect("clicked", self.pushed_action, 'world select')

        self.add_button = gtk.ToggleButton("Add Position")
        self.add_button.connect("clicked", self.pushed_action, 'add')

        self.del_button = gtk.ToggleButton("Remove Position")
        self.del_button.connect("clicked", self.pushed_action, 'del')

        self.add_wifi_button = gtk.ToggleButton("Add/Update WIFI Sample")
        self.add_wifi_button.connect("clicked", self.pushed_action, 'add wifi')

        self.clear_wifi_button = gtk.ToggleButton("Clear WIFI Sample")
        self.clear_wifi_button.connect("clicked", self.pushed_action, 'clear wifi')

        self.world_action_hbox.pack_start(self.world_select_button, False, False, 2)
        self.world_action_hbox.pack_start(self.add_button, False, False, 2)
        self.world_action_hbox.pack_start(self.del_button, False, False, 2)
        self.world_action_hbox.pack_start(self.add_wifi_button, False, False, 2)
        self.world_action_hbox.pack_start(self.clear_wifi_button, False, False, 2)

        # Action buttons - tour edit
        self.tour_select_button = gtk.ToggleButton("Select/Move")
        self.tour_select_button.connect("clicked", self.pushed_action, 'tour select')

        self.tour_add_a_button = gtk.Button("Add/Remove A")
        self.tour_add_a_button.connect("clicked", self.pushed_action, 'add a')

        self.tour_add_b_button = gtk.Button("Add/Remove B")
        self.tour_add_b_button.connect("clicked", self.pushed_action, 'add b')

        self.tour_del_segment_button = gtk.Button("Delete segment")
        self.tour_del_segment_button.connect("clicked", self.pushed_action, 'del segment')

        self.tour_action_hbox.add(self.tour_select_button)
        self.tour_action_hbox.add(self.tour_add_a_button)
        self.tour_action_hbox.add(self.tour_add_b_button)
        self.tour_action_hbox.add(self.tour_del_segment_button)

        # Action buttons - task edit
        self.task_combobox = gtk.combo_box_new_text()
        for t in tasks.get_all_tasks():
            self.task_combobox.append_text(str(t.__name__))
        self.task_combobox.set_active(0)
        self.task_combobox.connect("changed", self.fill_param_box)
        
        self.task_add_button = gtk.Button("Add task")
        self.task_add_button.connect("clicked", self.pushed_action, 'add task')

        self.task_exe_button = gtk.Button("Execute task")
        self.task_exe_button.connect("clicked", self.pushed_action, 'exe task')
        
        self.task_del_task_button = gtk.Button("Delete task")
        self.task_del_task_button.connect("clicked", self.pushed_action, 'del task')

        self.task_kill_all_button = gtk.Button("Delete task")
        self.task_kill_all_button.connect("clicked", self.pushed_action, 'kill task')

        self.task_action_hbox.add(self.task_combobox)
        self.task_action_hbox.add(self.task_add_button)
        self.task_action_hbox.add(self.task_exe_button)
        self.task_action_hbox.add(self.task_del_task_button)
        self.task_action_hbox.add(self.task_kill_all_button)

        self.fill_param_box(None, None)
        
        self.area = gtk.DrawingArea()
        self.area.set_size_request(800, 600)
        self.pixmap = None
       
        self.pangolayout = self.area.create_pango_layout("")
        self.sw = gtk.ScrolledWindow()
        self.sw.add_with_viewport(self.area)
        self.table = gtk.Table(2,2)
        self.hruler = gtk.HRuler()
        self.vruler = gtk.VRuler()
        self.hruler.set_range(0, 400, 0, 400)
        self.vruler.set_range(0, 300, 0, 300)
        self.table.attach(self.hruler, 1, 2, 0, 1, yoptions=0)
        self.table.attach(self.vruler, 0, 1, 1, 2, xoptions=0)
        self.table.attach(self.sw, 1, 2, 1, 2)

        self.area.set_events(gtk.gdk.EXPOSURE_MASK | gtk.gdk.LEAVE_NOTIFY_MASK | gtk.gdk.BUTTON_PRESS_MASK
                             | gtk.gdk.BUTTON_RELEASE_MASK | gtk.gdk.POINTER_MOTION_MASK | gtk.gdk.POINTER_MOTION_HINT_MASK)
        
        # self.master_vbox.pack_start(self.mode_hbox, False, False)        
        # self.master_vbox.pack_start(self.world_action_hbox, False, False)        
        # self.master_vbox.pack_start(self.tour_action_hbox, False, False)        
        # self.master_vbox.pack_start(self.task_action_hbox, False, False)        
        # self.master_vbox.pack_start(self.task_param_hbox, False, False)        
       
       
        self.master_vbox.pack_start(self.tabs, False, False, 2)
        self.master_vbox.pack_start(self.table, True, True)        
        self.master_vbox.show_all()
        # self.tour_action_hbox.hide()
        # self.task_action_hbox.hide()
        # self.task_param_hbox.hide()

        self.tabs.create_tab('Edit Tasks', self.task_vbox)
        self.tabs.create_tab('Edit Tour', self.tour_action_hbox)
        self.tabs.create_tab('Edit World', self.world_action_hbox)        

        self.world_select_button.set_active(True)
        window.add(self.master_vbox)

        def motion_notify(ruler, event):
            return ruler.emit("motion_notify_event", event)
        
        self.area.connect_object("motion_notify_event", motion_notify,
                                 self.hruler)
        
        self.area.connect_object("motion_notify_event", motion_notify,
                                 self.vruler)

        self.area.connect("configure_event", self.configure_event)
        self.area.connect("expose-event", self.area_expose_cb)
        self.area.connect("button_press_event", self.pushed)
        self.area.connect("button_release_event", self.released)
        self.area.connect("motion_notify_event", self.motion)

        self.hadj = self.sw.get_hadjustment()
        self.vadj = self.sw.get_vadjustment()

        def val_cb(adj, ruler, horiz):
            if horiz:
                span = self.sw.get_allocation()[3]
            else:
                span = self.sw.get_allocation()[2]
            l,u,p,m = ruler.get_range()
            v = adj.value
            ruler.set_range(v, v+span, p, m)
            while gtk.events_pending():
                gtk.main_iteration()

        self.hadj.connect('value-changed', val_cb, self.hruler, True)
        self.vadj.connect('value-changed', val_cb, self.vruler, False)

        def size_allocate_cb(wid, allocation):
            x, y, w, h = allocation
            l,u,p,m = self.hruler.get_range()
            m = max(m, w)
            self.hruler.set_range(l, l+w, p, m)
            l,u,p,m = self.vruler.get_range()
            m = max(m, h)
            self.vruler.set_range(l, l+h, p, m)

        self.sw.connect('size-allocate', size_allocate_cb)
        self.area.show()
        self.hruler.show()
        self.vruler.show()
        self.sw.show()
        self.table.show()
        window.show()


    def configure_event(self, widget, event):
        x, y, width, height = widget.get_allocation()
        self.pixmap = gtk.gdk.Pixmap(widget.window, width, height)
        self.pixmap.draw_rectangle(widget.get_style().white_gc,
                              True, 0, 0, width, height)

        return True

    def toggle_video_window(self, widget, event=None):
        if self.video_window.get_visible():
            self.video_window.video_play_button.set_active(False)	
            self.video_window.hide()
            return True
        else:
            self.video_window.init_video()
            self.video_window.show_all()
            self.video_window.video_play_button.set_active(True)	
            return True
    
    def hide_children(self, con):
        for c in con.get_children():
            try:
                c.hide_all()
            except AttributeError:
                c.hide()
           
    def set_mode(self, widget, page, page_num, data):
        self.clear()
        self.mode = page_num
        if self.mode == self.world_mode:
            self.hide_children(self.tour_action_hbox)
            self.hide_children(self.task_vbox)
            self.world_action_hbox.show_all()

        elif self.mode == self.tour_mode:
            self.tour_action_hbox.show_all()
            self.hide_children(self.world_action_hbox)
            self.hide_children(self.task_vbox)

        elif self.mode == self.task_mode:
            self.task_vbox.show_all()
            self.hide_children(self.world_action_hbox)
            self.hide_children(self.tour_action_hbox)
        
        self.area.queue_draw()

    def fill_param_box(self, widget, data=None):
        self.task_param_hbox.hide_all()
        taskname = self.task_combobox.get_active_text()

        for c in self.task_param_hbox.get_children():
            self.task_param_hbox.remove(c)

        selected_task = None
        for t in tasks.get_all_tasks():
            if t.__name__ == taskname:
                selected_task = t
        
        args = inspect.getargspec(selected_task.__init__)[0]
        defaults = inspect.getargspec(selected_task.__init__)[3]

        reslist = []
        for i in range(len(args)):
            a = args[i]
            if a != 'self' and a != 'drone' and a != 'callback' and a != 'context':
                l = gtk.Label(a)
                e = gtk.Entry(10)
                e.set_width_chars(10)
                if defaults is not None and len(defaults) > 0 and i >= (len(args) - len(defaults)):
                    e.set_text(str(defaults[i - (len(args)-len(defaults))]))
                e.set_visibility(True)
                reslist.append((a, e))
                self.task_param_hbox.pack_start(l, False, False, 3)
                self.task_param_hbox.pack_start(e, False, False, 3)

        
        self.task_param_hbox.resize_children()
        self.task_param_hbox.show_all()
        self.task_param_hbox.show()
        
    def stop(self, widget, event=None):
        print "Shutting down GUI\r"
        self.posmap.save_map()
        
        # ofile = open("./testdata/task.data", "w")
        # pickle.dump(self.tasks, ofile)
        # ofile.close()
        if gtk.main_level() > 0:
            gtk.main_quit()
            self.drone.stop(True)

    def pushed_mode(self, widget, data):
        self.clear()
        if data == 'world mode':
            self.world_action_hbox.show()
            self.tour_action_hbox.hide()
            self.task_action_hbox.hide()
            self.task_param_hbox.hide()
            self.mode = self.world_mode
        elif data == 'tour mode':
            self.tour_action_hbox.show()
            self.world_action_hbox.hide()
            self.task_action_hbox.hide()
            self.task_param_hbox.hide()
            self.mode = self.tour_mode
        elif data == 'task mode':
            self.task_action_hbox.show()
            self.task_param_hbox.show()
            self.tour_action_hbox.hide()
            self.world_action_hbox.hide()
            self.mode = self.task_mode
       
    def pushed_action(self, widget, data):
        self.clear()

        if isinstance(widget, gtk.ToggleButton) and not widget.get_active():
            return

        if data == 'add':
            #print 'add'
            if self.add_button.get_active():
                self.world_select_button.set_active(False)
                self.del_button.set_active(False)
                self.add_wifi_button.set_active(False)
                self.clear_wifi_button.set_active(False)
            self.world_mode_sub = self.add_mode 

        if data == 'add wifi':
            if self.add_wifi_button.get_active():
                self.world_select_button.set_active(False)
                self.del_button.set_active(False)
                self.add_button.set_active(False)
                self.add_wifi_button.set_active(False)
            self.world_mode_sub = self.add_wifi_mode 

        if data == 'clear wifi':
            if self.clear_wifi_button.get_active():
                self.world_select_button.set_active(False)
                self.del_button.set_active(False)
                self.add_button.set_active(False)
            self.world_mode_sub = self.clear_wifi_mode 

        elif data == 'del':
            #print 'del'
            if self.del_button.get_active():
                self.clear_wifi_button.set_active(False)
                self.add_button.set_active(False)
                self.world_select_button.set_active(False)
                self.add_wifi_button.set_active(False)
            self.world_mode_sub = self.del_mode

        elif data == 'world select':
            #print 'select'
            if self.world_select_button.get_active():
                self.clear_wifi_button.set_active(False)
                self.add_button.set_active(False)
                self.del_button.set_active(False)
                self.add_wifi_button.set_active(False)
            self.world_mode_sub = self.select_mode

        elif data == 'tour select':
            pass
            #self.world_mode_sub = self.select_mode

        elif data == 'add a':
            if self.selected_segment is not None:
                if not 'a' in self.selected_segment[2]:
                    self.selected_segment[2].append('a')
                else:
                    self.selected_segment[2].remove('a')

        elif data == 'add b':
            if self.selected_segment is not None:
                if not 'b' in self.selected_segment[2]:
                    self.selected_segment[2].append('b')
                else:
                    self.selected_segment[2].remove('b')
                    
        elif data == 'del segment':
            if self.selected_segment is not None:
                self.posmap.remove_tour_segment(self.selected_segment)
                self.selected_segment = None

        elif data == 'add task':
            params = [self.drone, None, None]
            for c in self.task_param_hbox.get_children():
                if type(c) is gtk.Entry:
                    text = c.get_text()
                    if text == 'None':
                        val = None
                    else:
                        val = self.parseStr(text)
                    params.append(val)
            print params, '\r'
            taskname = self.task_combobox.get_active_text()
            selected_task = None
            for t in tasks.get_all_tasks():
                if t.__name__ == taskname:
                    selected_task = t
       
            inst = selected_task(*params)
            x = 200+random.randint(-50, 50)
            y = 100+random.randint(-50, 50)

            #tasks.append(t)
            self.selected_task = self.add_task(inst, x, y)

        elif data == 'exe task':
            if self.selected_task is not None:
                exe = self.selected_task
                task_manager = self.drone.get_task_manager()#.get_controller(settings.AUTOCONTROL)
                
                # def cb(caller):
                #     task_manager.task_done(caller)
                    #self.toggle_video_window(None, None)
                    
                exe[2].callback = task_manager.task_done
                # if not self.video_window.get_visible():
                #     self.toggle_video_window(None, None)
                handle = task_manager.start_task(exe[2])

        elif data == 'del task':
           if self.selected_task is not None:
               for t in self.tasks:
                   if issubclass(t[2].__class__, tasks.CompoundTask):
                       if self.selected_task[2] in t[2].subtasks:
                           t[2].remove_subtask(self.selected_task[2])

               self.tasks.remove(self.selected_task)
                           
        
        self.area.queue_draw()
        

    def add_task(self, t, x, y):
       
        if issubclass(t.__class__, tasks.CompoundTask):
            self.tasks.append([x,y,t])
            for st in t.subtasks:
                self.add_task(st,x+random.randint(-50, 50), y+50+random.randint(-50, 50)
)
        else:
            
            self.tasks.append([x,y,t])
            return [x,y,t]

    def released(self, widget, event):
        self.clear()
        x = event.x
        y = event.y

        if self.mode == self.world_mode:
            if self.selected_position is not None and self.dragging:
                    self.selected_position.x = int(x)*10
                    self.selected_position.y = int(y)*10
                    self.posmap.calc_distances()
                    self.dragging = False
        
        elif self.mode == self.tour_mode:
            if event.state & gtk.gdk.CONTROL_MASK:
                if self.start_pos is not None:
                    hit = False
                    for p in self.posmap.positions:
                        if self.hit_test(p, x, y):
                            hit = True
                            self.end_pos = p
                            if len(self.posmap.tour) == 0:
                                self.posmap.tour.append((self.start_pos, self.end_pos, []))
                            elif self.start_pos == self.posmap.tour[len(self.posmap.tour)-1][1]:
                                self.posmap.tour.append((self.start_pos, self.end_pos, []))
                            elif self.start_pos == self.posmap.tour[0][0]:
                                self.posmap.tour.insert(0, (self.end_pos, self.start_pos, []))
                            self.end_pos, self.start_pos = None, None 
                            self.posmap.save_map()
                    if not hit:
                        self.start_pos = None

        
        elif self.mode == self.task_mode:
            if event.state & gtk.gdk.CONTROL_MASK:
                if self.parent_task is not None:
                    hit = False
                    for t in self.tasks:
                        if self.hit_test_rect(t, x, y):
                            hit = True
                            if not t[2] in self.parent_task[2].subtasks:
                                print 'adding subtask'
                                self.parent_task[2].add_subtasks([t[2]])
                                print 'callback: ', t[2].callback, '\r'
                            else:
                                self.parent_task[2].remove_subtask(t[2])

                            self.parent_task = None
                           
                    if not hit:
                        self.start_pos = None
            else:
                if self.selected_task is not None and self.dragging:
                    self.selected_task[0] = int(x)
                    self.selected_task[1] = int(y)
                    self.dragging = False


        self.area.queue_draw()

    def motion(self, widget, event):
        self.clear()

        if event.is_hint:
            x, y, state = event.window.get_pointer()
        else:
            x = event.x
            y = event.y
            state = event.state
   
        if self.mode == self.world_mode:
            if not state & gtk.gdk.CONTROL_MASK and state & gtk.gdk.BUTTON1_MASK:
                if self.selected_position is not None:
                    self.dragging = True
                    self.draw_point(x,y)

        
        elif self.mode == self.tour_mode:
            if state & gtk.gdk.CONTROL_MASK and state & gtk.gdk.BUTTON1_MASK:
                if self.start_pos is not None:
                    self.pixmap.draw_line(self.gc, int(self.start_pos.x/10), int(self.start_pos.y/10), int(x), int(y))


        elif self.mode == self.task_mode:
            if not state & gtk.gdk.CONTROL_MASK and state & gtk.gdk.BUTTON1_MASK:
                self.parent_task = None
                if self.selected_task is not None:
                    self.dragging = True
                    self.selected_task[0] = int(x)
                    self.selected_task[1] = int(y)
            else:
                if self.parent_task is not None:
                    self.pixmap.draw_line(self.gc, int(self.parent_task[0]), int(self.parent_task[1]), int(x), int(y))
        
        self.area.queue_draw() 


    def pushed(self, widget, event):
        self.clear()
        x = event.x
        y = event.y
    
        if self.mode == self.world_mode:
            # if not control is pressed
            if not event.state & gtk.gdk.CONTROL_MASK:
                if self.world_mode_sub == self.select_mode: 
                    hit = False
                    for p in self.posmap.positions:
                        if self.hit_test(p, x, y):
                            hit = True
                            self.selected_position = p
            
                    if not hit:    
                        self.selected_position = None
        
                elif self.world_mode_sub == self.add_mode:
                    pos = map.Position(int(x*10), int(y*10))
                    self.posmap.add_pos(pos)

                elif self.world_mode_sub == self.add_wifi_mode:
                    for p in self.posmap.positions:
                        if self.hit_test(p, x, y):
                            wifi = self.wifi_sensor.record_sample()
                            p.wifi = wifi
                            print 'Updated ' , p.name, ' with a wifi sample\r'

                elif self.world_mode_sub == self.clear_wifi_mode:
                    for p in self.posmap.positions:
                        if self.hit_test(p, x, y):
                            p.wifi = None
                            print 'Cleared ' , p.name, ' for wifi sample\r'
                
                elif self.world_mode_sub == self.del_mode:
                    for p in self.posmap.positions:
                        if self.hit_test(p, x, y):
                            self.posmap.remove_pos(p)
                            break
            # if control
            else:
                pass
                    
        elif self.mode == self.tour_mode:
            # if control is pressed
            if event.state & gtk.gdk.CONTROL_MASK:
                hit = False
                for p in self.posmap.positions:
                    if self.hit_test(p, x, y) and (len(self.posmap.tour) == 0 or p == self.posmap.tour[0][0] or p == self.posmap.tour[len(self.posmap.tour)-1][1]):
                        hit = True
                        self.start_pos = p
            
                if not hit:    
                    self.start_pos = None

            else:
                hit = False
                for i in range(len(self.posmap.tour)):
                    if not i == len(self.posmap.tour):
                        l1 = self.posmap.tour[i][0]
                        l2 = self.posmap.tour[i][1]
                        p = (x*10,y*10)
                        d = float(abs(((l2.x-l1.x)*(l1.y-p[1])) - ((l1.x-p[0])*(l2.y-l1.y)))) / float(math.sqrt( (l2.x-l1.x)**2 + (l2.y - l1.y)**2))
                        if d <= 30:
                            self.selected_segment = self.posmap.tour[i]
                            hit = True
                if not hit:
                    self.selected_segment = None

        elif self.mode == self.task_mode:
            if event.state & gtk.gdk.CONTROL_MASK:
                hit = False
                for t in self.tasks:
                    
                    if self.hit_test_rect(t, x, y) and issubclass(t[2].__class__, tasks.CompoundTask):# or type(t[2]) is tasks.ParCompoundTask):
                        hit = True
                        self.parent_task = t
            
                if not hit:    
                    self.parent_task = None

            else:
                hit = False
                for t in self.tasks:
                    if self.hit_test_rect(t, x, y):
                        if t != self.selected_task:
                            hit = True
                            self.selected_task = t
                if not hit:
                    self.selected_task = None

        self.area.queue_draw()
        
    def hit_test(self, p, x, y):
        d = math.sqrt((x - (p.x/10))**2 + (y - (p.y/10))**2)
        if d <= 20:
            # print 'hit ', p, '\r'
            return True
        else:
            return False

    def hit_test_rect(self, t, x, y):
        t_max_x = t[0] + 60
        t_min_x = t[0] - 60

        t_max_y = t[1] + 20
        t_min_y = t[1] - 20
        return t_min_x < x < t_max_x and t_min_y < y < t_max_y
       
 
    def area_expose_cb(self, area, event):
        self.style = self.area.get_style()
        self.gc = self.style.fg_gc[gtk.STATE_NORMAL]
        black = self.colormap.alloc_color('black')
        white = self.colormap.alloc_color('white')
        green = self.colormap.alloc_color('green')
        yellow = self.colormap.alloc_color('yellow')
        blue = self.colormap.alloc_color('blue')
        red = self.colormap.alloc_color('red')

        self.gc_red = self.area.window.new_gc(foreground=red)
        self.gc_green = self.area.window.new_gc(foreground=green)
        self.gc_yellow = self.area.window.new_gc(foreground=yellow)
        self.gc_blue = self.area.window.new_gc(foreground=blue)

        if self.mode == self.tour_mode:
            for i in range(len(self.posmap.tour)):
                sp = self.posmap.tour[i][0]
                ep = self.posmap.tour[i][1]
                mods = self.posmap.tour[i][2]
                if self.selected_segment is not None and self.selected_segment == self.posmap.tour[i]: 
                    gc = self.gc_red
                else:
                    gc = self.gc_green
                self.pixmap.draw_line(gc, int(sp.x/10), int(sp.y/10), int(ep.x/10), int(ep.y/10))

                for mod in mods:
                    if mod == 'a':
                        self.pixmap.draw_line(self.gc_blue, int(sp.x/10), int(sp.y/10)-1, int(ep.x/10), int(ep.y/10)-1)
                    elif mod == 'b':
                        self.pixmap.draw_line(self.gc_yellow, int(sp.x/10), int(sp.y/10)+1, int(ep.x/10), int(ep.y/10)+1)

        if self.mode == self.world_mode or self.mode == self.tour_mode:
            gc = self.gc
            for p in self.posmap.positions:
                if not p == self.selected_position:
                    self.draw_pos(p, False)
                else:
                    if not self.dragging:
                        self.draw_pos(p, True)
                    
        if self.mode == self.task_mode:
            
            gc = self.gc
            for t in self.tasks:
                #if not self.dragging:
                if t == self.selected_task:
                    self.draw_task(gc, t, True)
                else:
                    self.draw_task(gc, t, False)
                if issubclass(t[2].__class__, tasks.CompoundTask):# or type(t[2]) is tasks.ParCompoundTask:
                    for st in self.tasks:
                        if st[2] in t[2].subtasks:
                            self.pixmap.draw_line(self.gc, int(t[0]), int(t[1]), int(st[0]), int(st[1]))

        x , y, width, height = event.area
        area.window.draw_drawable(area.get_style().fg_gc[gtk.STATE_NORMAL],
                                self.pixmap, x, y, x, y, width, height)
        return False

    def clear(self):
        x, y, width, height = self.area.get_allocation()
	if not self.pixmap is None:
            self.pixmap.draw_rectangle(self.area.get_style().white_gc,
                                       True, 0, 0, width, height)

    
    def draw_point(self, x, y):
        self.pixmap.draw_point(self.gc, x+30, y+30)
        self.pangolayout.set_text("Point")
        self.pixmap.draw_layout(self.gc, x+5, y+50, self.pangolayout)
        return

    def draw_points(self, x, y):
        points = [(x+10,y+10), (x+10,y), (x+40,y+30),
                  (x+30,y+10), (x+50,y+10)]
        self.pixmap.draw_points(self.gc, points)
        self.pangolayout.set_text("Points")
        self.pixmap.draw_layout(self.gc, x+5, y+50, self.pangolayout)
        return

    def draw_line(self, x, y):
        self.pixmap.draw_line(self.gc, x+10, y+10, x+20, y+30)
        self.pangolayout.set_text("Line")
        self.pixmap.draw_layout(self.gc, x+5, y+50, self.pangolayout)
        return

    def draw_lines(self, x, y):
        points = [(x+10,y+10), (x+10,y), (x+40,y+30),
                  (x+30,y+10), (x+50,y+10)]
        self.pixmap.draw_lines(self.gc, points)
        self.pangolayout.set_text("Lines")
        self.pixmap.draw_layout(self.gc, x+5, y+50, self.pangolayout)
        return

    def draw_segments(self, x, y):
        segments = ((x+20,y+10, x+20,y+70), (x+60,y+10, x+60,y+70),
            (x+10,y+30 , x+70,y+30), (x+10, y+50 , x+70, y+50))
        self.pixmap.draw_segments(self.gc, segments)
        self.pangolayout.set_text("Segments")
        self.pixmap.draw_layout(self.gc, x+5, y+80, self.pangolayout)
        return

    def draw_rectangles(self, x, y):
        self.pixmap.draw_rectangle(self.gc, False, x, y, 80, 70)
        self.pixmap.draw_rectangle(self.gc, True, x+10, y+10, 20, 20)
        self.pixmap.draw_rectangle(self.gc, True, x+50, y+10, 20, 20)
        self.pixmap.draw_rectangle(self.gc, True, x+20, y+50, 40, 10)
        self.pangolayout.set_text("Rectangles")
        self.pixmap.draw_layout(self.gc, x+5, y+80, self.pangolayout)
        return

    def draw_arcs(self, x, y):
        self.pixmap.draw_arc(self.gc, False, x-20, y-20, 40, 40,
                                  0, 360*64)
        # self.pixmap.draw_arc(self.gc, True, x+30, y+10, 30, 50,
        #                           210*64, 120*64)
        return
    def draw_task(self, gc, t, selected):
        x = t[0]
        y = t[1]
        task = t[2]
        name = str(task.__class__.__name__)
        level = 'level: ' + str(task.level)
        self.pixmap.draw_rectangle(gc, False, x-60, y-20, 120, 40)
        if selected:
            self.pixmap.draw_rectangle(gc, False, x-61, y-21, 122, 42)
        self.pangolayout.set_text(name)
        self.pixmap.draw_layout(self.gc, x-50, y-20, self.pangolayout)
        self.pangolayout.set_text(level)
        self.pixmap.draw_layout(self.gc, x-50, y-10, self.pangolayout)
    def draw_pos(self, pos, selected):
        x = int(pos.x/10)
        y = int(pos.y/10)
        name = pos.name
        filled = False#(pos == self.selected_position)
        self.pixmap.draw_arc(self.gc, filled, x-20, y-20, 40, 40,
                                   0, 360*64)
       
        if selected:
            self.pixmap.draw_arc(self.gc, filled, x-21, y-21, 42, 42,
                                      2, 360*64)
        t_len = len(self.posmap.tour) 

        if self.mode == self.tour_mode and t_len > 0 and pos == self.posmap.tour[0][0] and pos == self.posmap.tour[t_len-1][1]:
            self.pixmap.draw_arc(self.gc_green, True, x-20, y-20, 40, 40,
                                      0, 180*64)
            self.pixmap.draw_arc(self.gc_red, True, x-20, y-20, 40, 40,
                                       0, -180*64)
             
        elif self.mode == self.tour_mode and t_len > 0 and pos == self.posmap.tour[0][0]:
            self.pixmap.draw_arc(self.gc_green, True, x-20, y-20, 40, 40,
                                      0, 360*64)

        elif self.mode == self.tour_mode and t_len > 0 and pos == self.posmap.tour[t_len-1][1]:
            self.pixmap.draw_arc(self.gc_red, True, x-20, y-20, 40, 40,
                                      0, 360*64)


        self.pangolayout.set_text(name)
        self.pixmap.draw_layout(self.gc, x-10, y-10, self.pangolayout)
        return

    def draw_polygon(self, x, y):
        points = [(x+10,y+60), (x+10,y+20), (x+40,y+70),
                  (x+30,y+30), (x+50,y+40)]
        self.pixmap.draw_polygon(self.gc, True, points)
        self.pangolayout.set_text("Polygon")
        self.pixmap.draw_layout(self.gc, x+5, y+80, self.pangolayout)
        return

    def draw_rgb_image(self, x, y):
        b = 80*3*80*['\0']
        for i in range(80):
            for j in range(80):
                b[3*80*i+3*j] = chr(255-3*i)
                b[3*80*i+3*j+1] = chr(255-3*abs(i-j))
                b[3*80*i+3*j+2] = chr(255-3*j)
        buff = string.join(b, '')
        self.pixmap.draw_rgb_image(self.gc, x, y, 80, 80,
                                 gtk.gdk.RGB_DITHER_NONE, buff, 80*3)
        self.pangolayout.set_text("RGB Image")
        self.pixmap.draw_layout(self.gc, x+5, y+80, self.pangolayout)
        return
   
if __name__ == "__main__":
    import drone, sys
    test = False
    arg_len = len(sys.argv)
    for i in range(arg_len):
        if sys.argv[i] == '-t':
            test = True
            
    drone = drone.Drone(test)
    drone.start()
    gui = TaskGUI(drone)
    
    drone.gui = gui
    gui.show()

