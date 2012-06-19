
import tasks
import corridor_stuff as cs

class CorridorHoughlineVanishTask(Task):
    """
    Bla bla bla
    """
    #callback metode paa Task, som kaldes naar Tasken er faerdig, efter postloop
    def __init__(self, drone, callback, context):
        Task.__init__(self, drone, callback, context)

    def pre_loop(self):
        pass

    def loop(self):

        img_a = self.video_sensor.get_data()
        #mat = cv.fromarray(img_a)
        navdata = self.navdata_sensor.get_data()
        #altitude = navdata.get(0, dict()).get('altitude', 0)
        y_tilt = navdata.get(0, dict()).get('theta', 0)

        point, ppty = cs.findCorridorVanishPoint(img_a, y_tilt, True)


