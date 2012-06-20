
import cv2, time, receivers #drone

#cam = cv2.VideoCapture(0)
#cam.read()
#cam.read()
#print type(cam)
#w = cam.get( 3 ) #cv2.CAP_PROP_FRAME_WIDTH)
#h = cam.get( 4 ) #cv2.CAP_PROP_FRAME_HEIGHT)
#fps = cam.get( cv2.cv.CV_CAP_PROP_FPS )
#cv2.cv.GetCaptureProperty(cam, cv2.cv.CV_CAP_PROP_FRAME_WIDTH )
w, h = size = (800, 600)
print w, h

video_sensor = receivers.VideoReceiver()
video_sensor.start()
time.sleep(2)

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
print "frames per second", fps
print "fourcc type", type(cv2.cv.CV_FOURCC('P','I','M','1'))
wr = cv2.VideoWriter("output.mpeg", cv2.cv.CV_FOURCC('P','I','M','1'), int(fps), (int(w),int(h)))

while True:
    ret, img = cam.read()
    cv2.imshow('cam', img)

    wr.write(img)

    ch = cv2.waitKey(2)
    if ch == 27:
        break

wr.release()
