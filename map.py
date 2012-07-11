import math
import pickle
import settings
import os

class PosMap(object):

    def __init__(self):

        self.verbose = False
        
        saved_map = self.load_map()
        if saved_map is None:
            pos1 = Position(1000, 1000, 'pos1', settings.BLUE)
            pos2 = Position(2000, 1000, 'pos2', settings.GREEN)
            pos3 = Position(2000, 2000, 'pos3', settings.YELLOW)
            pos4 = Position(1000, 2000, 'pos4', settings.PURPLE)
            pos5 = Position(1000, 3000, 'pos5', settings.TURQOISE)
            self.positions = [pos1, pos2, pos3, pos4, pos5]
            self.tour = []
        else:
            self.positions = saved_map.positions
            self.tour = saved_map.tour

        self.distances = self.calc_distances()

    def add_pos(self, p):
        i = 1
        stop = False
        while not stop:
            exist = False
            try_name = 'pos' + str(i)
            for pos in self.positions:
                if pos.name == try_name:
                    exist = True
            
            if not exist:
                p.name = try_name
                self.positions.append(p)
                stop = True
            i += 1
        self.distances = self.calc_distances()

        if self.verbose:
            print 'Positions:\r'
            print self.positions, '\r'

    def remove_pos(self, p):
        print 'remove called'
        self.positions.remove(p)
        first_seg = None
        for seg in self.tour:
            if p in seg:
                first_seg = seg
                break

        if first_seg is not None:
            i = self.tour.index(first_seg)
            self.tour = self.tour[:i]
        
        if self.verbose:
            print 'Positions:\r'
            print self.positions, '\r'

    def remove_tour_segment(self, ts):
        if ts in self.tour:
            i = self.tour.index(ts)
            self.tour = self.tour[:i]
           
    def calc_distances(self):
        mat = []
        for p1 in self.positions:
            row = []
            for p2 in self.positions:
                if p1 == p2:
                    row.append(0)
                else:
                    d = math.sqrt( (p1.x - p2.x)**2 + (p1.y - p2.y)**2 )
                    row.append(d)
            if self.verbose:
                print row, '\r'
            mat.append(row)
        return mat

    def get_distance(self, p1, p2):
        i1 = self.positions.index(p1)
        i2 = self.positions.index(p2)

        return self.distances[i1][i2]

    def load_map(self):
        if os.path.isfile('./testdata/map.data'):
            fileObj = open('./testdata/map.data')
            posmap = pickle.load(fileObj)
            return posmap
        else:
            return None

    def save_map(self):
        ofile = open("./testdata/map.data", "w")
        pickle.dump(self, ofile)
        ofile.close()

class Position(object):

    def __init__(self, x, y, name='Unnamed pos', color=settings.BLUE):
        self.x = x
        self.y = y
        self.name = name
        self.color = color
        self.wifi = None




