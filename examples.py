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


def qrscan():
    import testdevice, settings, receivers, zbar, Image
    
    settings.TEST = True
    testdevice = testdevice.TestDevice(False)
    testdevice.start()
    
    video_sensor = receivers.VideoReceiver(settings.VIDEO_PORT)
    video_sensor.start()
    
    scanner = zbar.ImageScanner()  
    scanner.parse_config('enable')

    reps = 100
    while reps > 0:
        
        # obtain image data
        org = video_sensor.get_data()
        if org is not None:
            pil = Image.fromarray(org)#open('test-decode.png').convert('L')
            width, height = pil.size
            raw = pil.tostring()

            # wrap image data
            image = zbar.Image(width, height, 'Y800', raw)

            # scan the image for barcodes
            scanner.scan(image)

            # extract results
            for symbol in image:
                # do something useful with results
                print 'decoded', symbol.type, 'symbol', '"%s"' % symbol.data

            # clean up
            del(image)
            reps -= 1

    testdevice.stop()
    video_sensor.stop()
   
def qrencode():
    import sys, qrcode

    e = qrcode.Encoder()
    image = e.encode('woah', version=1, mode=e.mode.ALNUM, eclevel=e.eclevel.Q)
    image.save('./testdata/out.png')


if __name__ == '__main__':
    receive_and_show_picture()
    # show_imgs()
    # test_decode()
