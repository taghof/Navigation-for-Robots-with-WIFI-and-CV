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
import newesttasks as tasks
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

        self.tasks = []
        self.selected_task = None
        self.parent_task = None
        
        self.mode = 0
        self.task_mode = 0

        self.dragging = False
        self.connecting = True

        self.parseStr = lambda x: x.isalnum() and x or x.isdigit() and int(x) or len(set(string.punctuation).intersection(x)) == 1 and x.count('.') == 1 and float(x) or x

    def show(self):
        self.build_gui()
        gtk.main()
                
    def build_gui(self):
        self.colormap = gtk.gdk.colormap_get_system()
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_title("Task Creator 1.0")
        window.connect("destroy", self.stop)
        window.set_size_request(800, 600)
        
        import tabbed
        self.tabs = tabbed.Tabs()
        self.tabs.connect("switch-page", self.set_mode, 'set mode')
        
        # Layout boxes
        self.master_vbox = gtk.VBox(False, 2)
        self.master_vbox.set_border_width( 5 )

        self.task_vbox = gtk.VBox(False, 2)
        self.task_vbox.set_border_width( 5 )

        self.task_action_hbox = gtk.HBox(True, 2)
        self.task_action_hbox.set_border_width( 5 )
        
        self.task_param_hbox = gtk.HBox(False, 2)
        self.task_param_hbox.set_border_width( 5 )

        self.task_vbox.add(self.task_action_hbox)
        self.task_vbox.add(self.task_param_hbox)
        
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

        self.task_kill_button = gtk.Button("Stop task")
        self.task_kill_button.connect("clicked", self.pushed_action, 'kill task')

        self.task_kill_all_button = gtk.Button("Stop all tasks")
        self.task_kill_all_button.connect("clicked", self.pushed_action, 'kill all')

        #self.task_action_hbox.add(self.task_combobox)
        self.task_action_hbox.add(self.task_add_button)
        self.task_action_hbox.add(self.task_del_task_button)
        self.task_action_hbox.add(self.task_exe_button)
        self.task_action_hbox.add(self.task_kill_button)
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
        
       
        self.master_vbox.pack_start(self.tabs, False, False, 2)
        self.master_vbox.pack_start(self.table, True, True)        
        self.master_vbox.show_all()

        self.tabs.create_tab('Edit Tasks', self.task_vbox)
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
    
    def hide_children(self, con):
        for c in con.get_children():
            try:
                c.hide_all()
            except AttributeError:
                c.hide()
           
    def set_mode(self, widget, page, page_num, data):
        self.clear()
        self.mode = page_num

        if self.mode == self.task_mode:
            self.task_vbox.show_all()
                
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
        self.task_param_hbox.pack_start(self.task_combobox, False, False, 3)
        #reslist = []
        for i in range(len(args)):
            a = args[i]
            if a != 'self' and a != 'drone' and a != 'callback' and a != 'context':
                l = gtk.Label(a)
                e = gtk.Entry(10)
                e.set_width_chars(10)
                if defaults is not None and len(defaults) > 0 and i >= (len(args) - len(defaults)):
                    e.set_text(str(defaults[i - (len(args)-len(defaults))]))
                e.set_visibility(True)
                #reslist.append((a, e))
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

        if data == 'add task':
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
       
        elif data == 'kill task':
           t = self.selected_task 
           if t is not None:
               t[2].stop()
                           
        elif data == 'kill all':
            task_manager = self.drone.get_task_manager()#.get_controller(settings.AUTOCONTROL)
            task_manager.kill_tasks()
       
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

        if self.mode == self.task_mode:
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
           
        if self.mode == self.task_mode:
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
    
        if self.mode == self.task_mode:
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

    def draw_polygon(self, x, y):
        points = [(x+10,y+60), (x+10,y+20), (x+40,y+70),
                  (x+30,y+30), (x+50,y+40)]
        self.pixmap.draw_polygon(self.gc, True, points)
        self.pangolayout.set_text("Polygon")
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

