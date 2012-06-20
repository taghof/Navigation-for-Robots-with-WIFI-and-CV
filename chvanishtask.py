
#import tasks
import corridor_stuff as cs

# class CorridorHoughlineVanishTask(Task):
#     """
#     Bla bla bla
#     """
#     #callback metode paa Task, som kaldes naar Tasken er faerdig, efter postloop
#     def __init__(self, drone, callback, context):
#         Task.__init__(self, drone, callback, context)

#     def pre_loop(self):
#         pass

#     def loop(self):

#         img_a = self.video_sensor.get_data()
#         #mat = cv.fromarray(img_a)
#         navdata = self.navdata_sensor.get_data()
#         #altitude = navdata.get(0, dict()).get('altitude', 0)
#         y_tilt = navdata.get(0, dict()).get('theta', 0)

#         point, ppty = cs.findCorridorVanishPoint(img_a, y_tilt, True)


if __name__ == "__main__":
    import receivers, controllers, time, settings, cv2, cv2.cv as cv
    video_sensor = receivers.VideoReceiver()
    video_sensor.start()
    navdata_sensor = receivers.NavdataReceiver(settings.NAVDATA_PORT)
    navdata_sensor.start()

    # in order to get all and full navdata send AT*CONFIG=605,"general:navdata_demo","TRUE"
    # this is send in the init-function of ControllerInterface
    ci = controllers.ControllerInterface()
    ci.start()

    time.sleep(3)

    cv.StartWindowThread()
    cv.NamedWindow("Hough", 1)

    while True:
        nd = navdata_sensor.get_data()
        ndd = nd.get(0, dict())
            #print nd, ndd
        #y_tilt = ndd.get('theta',0)
        y_tilt = ndd.get('phi',0)
        print "y_tilt", y_tilt
            #img_a = video_sensor.get_data()
        img_a = cv2.cvtColor( video_sensor.get_data() , cv2.COLOR_BGR2GRAY)
        point, ppty = cs.findCorridorVanishPoint(img_a, y_tilt, True)
            #print point
        if cv.WaitKey(3) == 27:
            break

    video_sensor.stop()
    navdata_sensor.stop()
    ci.stop()

# ci.take_off()
# ci.rotate( dir )
