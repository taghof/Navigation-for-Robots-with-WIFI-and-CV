def square():
    import controllers
    import time

    c = controllers.ControllerInterface()
    c.start()

    print 'taking off'
    c.take_off()
    time.sleep(5.0)
    print 'moving Forward'
    c.move(0.0, 0.2, 0.0, 0.0, True)
    time.sleep(2.0)
    print 'moving right'
    c.move(0.2, 0.0, 0.0, 0.0, True)
    time.sleep(2.0)
    print 'moving back'
    c.move(0.0, -0.2, 0.0, 0.0, True)
    time.sleep(2.0)
    print 'moving left'
    c.move(-0.2, 0.0, 0.0, 0.0, True)
    time.sleep(2.0)
    print 'landing'
    c.land()

    c.stop()

def receive_and_show_picture():
    import receivers, settings, time
    import cv2

    video_sensor = receivers.VideoReceiver(settings.VIDEO_PORT)
    video_sensor.start()
    time.sleep(1)
    pic = video_sensor.get_data()
    
    cv2.startWindowThread()
    win = cv2.namedWindow('win')
    cv2.imshow('win', cv2.cvtColor(pic, cv2.COLOR_BGR2RGB))
    cv2.waitKey()
    cv2.destroyWindow('win')
    video_sensor.stop()

def test_decode():
    import decoder
    import time

    reps = 100
    frame = open('./testdata/1.dat').read()

    t1 = time.time()
    for i in range(reps):
       res = decoder.read_picture(frame)

    t2 = time.time()
    print 'time: ', t2-t1

if __name__ == '__main__':
    receive_and_show_picture()
    # show_imgs()
    # test_decode()
