"""
This is a PyGTK program that displays tabbed-pages (GtkNotebook) that are
detachable and movable.
 
see http://www.pygtk.org/pygtk2tutorial/sec-Notebooks.html#notebookfig
"""
 
import gtk
 
__author__ = "Caleb P Burns"
__copyright__ = "Copyright (C) 2010 Caleb P Burns <cpburns2009@gmail.com>"
__license__ = "WTFPL License"
__version__ = "0.3"
 
class Tabs(gtk.Notebook):
        """
        This class displays tabbed-pages via a GtkNotebook in a window.
        """
       
        def __init__(self):
            gtk.Notebook.__init__(self)
            self.set_scrollable(True)
            self.set_properties(group_id=0, tab_vborder=0, tab_hborder=1, tab_pos=gtk.POS_TOP)
            self.popup_enable()
            
        def create_tab(self, name, box):

                tab = gtk.HBox()
                tab_label = gtk.Label(name)
                tab_label.show()
                tab.pack_start(tab_label)
                tab.show()
                box.show()
                self.append_page(box, tab)
                self.set_tab_reorderable(box, True)
                self.set_tab_detachable(box, True)

