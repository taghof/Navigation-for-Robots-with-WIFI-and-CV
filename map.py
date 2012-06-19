import math
import pickle

class PosMap(object):

    def __init__(self):

        self.verbose = True
        
        pos1 = ['pos1',1000,1000]
        pos2 = ['pos2', 2000,1000]
        pos3 = ['pos3', 2000, 2000]
        pos4 = ['pos4', 1000, 2000]
        pos5 = ['pos5', 1000, 3000]

        self.positions = [pos1, pos2, pos3, pos4, pos5]
        self.distances = self.calc_distances()
        self.tour = []

    def add_pos(self, p):
        i = 1
        stop = False
    
        while not stop:
            exist = False
            try_name = 'pos' + str(i)
            print try_name
            for pos in self.positions:
                if pos[0] == try_name:
                    exist = True
            
            if not exist:
                p[0] = try_name
                self.positions.append(p)
                stop = True
            i += 1

        print self.positions

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
           
        print self.positions

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
                    d = math.sqrt( (p1[1] - p2[1])**2 + (p1[2] - p2[2])**2 )
                    row.append(d)
            if self.verbose:
                print row, '\r'
            mat.append(row)
        return mat

    def get_distance(self, p1, p2):
        i1 = self.positions.index(p1)
        i2 = self.positions.index(p2)

        return self.distances[i1][i2]

    def save_map(self):
        ofile = open("./testdata/map.data", "w")
        pickle.dump(self, ofile)
        ofile.close()

