
import cv2, time, receivers, controllers, cv2.cv as cv  #drone
import utils
#cam = cv2.VideoCapture(0)
#cam.read()
#cam.read()
#print type(cam)
#w = cam.get( 3 ) #cv2.CAP_PROP_FRAME_WIDTH)
#h = cam.get( 4 ) #cv2.CAP_PROP_FRAME_HEIGHT)
#fps = cam.get( cv2.cv.CV_CAP_PROP_FPS )
#cv2.cv.GetCaptureProperty(cam, cv2.cv.CV_CAP_PROP_FRAME_WIDTH )
ci = controllers.ControllerInterface()
ci.start()
jc = controllers.JoystickControl( ci )
jc.start()

w, h = size = (320, 240) #(800, 600)
print w, h

video_sensor = receivers.VideoReceiver()
video_sensor.start()
navdata_sensor = receivers.NavdataReceiver()
navdata_sensor.start()
#ci = controllers.ControllerInterface()
#ci.start()

time.sleep(2)
ci.zap(0)

img = video_sensor.get_data()

frames = 0
start = time.time()

while frames < 30:
    img = video_sensor.get_data()
    #ret, img = cam.read()
    cv2.imshow('cam', img)
    frames += 1
print "frames", frames
print "time", time.time() - start
fps = frames / ((time.time() - start))
#fps = 12

#fps = 12
width, height = int(320), int(240)
fourcc = cv.CV_FOURCC('M','P','4','2')
wr = cv.CreateVideoWriter('out.avi', fourcc, fps, (width, height), 1)


print "frames per second", fps
#print "fourcc type", type(cv2.cv.CV_FOURCC('P','I','M','1')), cv2.cv.CV_FOURCC('P','I','M','1')
#wr = cv2.VideoWriter("output.mpeg", cv.CV_FOURCC('P','I','M','1'), int(fps), (int(w),int(h)))
#wr = cv2.VideoWriter("output.bob", cv2.cv.CV_FOURCC('U', '2', '6', '3'), int(fps), (int(w),int(h)))

# comment out
ci.zap(0)

f = open("output.txt", "w")
f.write("#phi \t theta \t psi \t vx \t vy \t vz \t altitude\n")

str_out = "#{0}\t{1}\t{2}\t{3}\t{4}\t{5}\t{6}\n"

while True:
    dat = navdata_sensor.get_data().get(0, dict())
    phi = dat.get('phi', 0)
    theta = dat.get('theta', 0)
    psi = dat.get('psi', 0)
    vx = dat.get('vx', 0)
    vy = dat.get('vy', 0)
    vz = dat.get('vz', 0)
    altitude = dat.get('altitude', 0)

    f.write(str_out.format(phi, theta, psi, vx, vy, vz, altitude))

    #ret, img = cam.read()
    img = video_sensor.get_data()
    img = cv2.cvtColor( img, cv.CV_RGB2BGR )
    cv2.imshow('cam', img)

    cv.WriteFrame(wr, utils.array2cv(img))
    #wr.write(img)
    ch = cv2.WaitKey(10)
    if 0 < ch:
        break

#wr.release()
video_sensor.stop()
navdata_sensor.stop()
#ci.stop()
f.close()
jc.stop()
ci.stop()
f.close()
