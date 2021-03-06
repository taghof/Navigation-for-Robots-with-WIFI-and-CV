
import numpy as np
import cv2.cv as cv
import cv2 
import sys
import datetime
import settings
import utils

RED = 0
GREEN = 1
BLUE = 2

def detect_color(img):

    pic = cv2.inRange(img, np.asarray((50, 10, 40)), np.asarray((80, 255, 255)))
    
    moments = cv2.moments(pic, 0)
    area = moments.get('m00')
    if(area > 10000):
        x = moments.get('m10')/area 
        y = moments.get('m01')/area
        print 'green'
        return (x, y, pic, 'green')

    pic = cv2.inRange(img, np.asarray((97, 10, 40)), np.asarray((116, 255, 255)))
    
    moments = cv2.moments(pic, 0)
    area = moments.get('m00')
    if(area > 10000):
        x = moments.get('m10')/area 
        y = moments.get('m01')/area 
        print 'blue'
        return (x, y, pic, 'blue')

    return None


def detect_position(img):
    org = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pic = cv2.cvtColor(org, cv2.COLOR_BGR2HSV)
    hsv = cv2.cvtColor(org, cv2.COLOR_BGR2HSV)
    thresh_l = cv2.inRange(hsv, np.asarray((0, 10, 30)), np.asarray((15, 255, 255)))
    thresh_h = cv2.inRange(hsv, np.asarray((172, 10, 30)), np.asarray((180, 255, 255)))
    thresh = cv2.add(thresh_l, thresh_h)
    
    contours,hierarchy = cv2.findContours(thresh ,cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
            #print cv2.contourArea(cnt), '\r'
        if cv2.contourArea(cnt)>20:
            [x,y,w,h] = cv2.boundingRect(cnt)
            if  h > 20 and w > 20:
                print 'red\r'
                mini_pic = hsv[(y):(y+h),(x):(x+w)]
                res = detect_color(mini_pic)
                if res is not None:
                    
                    x = x + res[0]
                    y = y + res[1]
                    if res[3] == 'green':
                        print 'green\r'
                        color = settings.GREEN
                    elif res[3] == 'blue':
                        print 'blue\r'
                        color = settings.BLUE
                    elif res[3] == 'yellow':
                        color = settings.YELLOW
                    elif res[3] == 'purple':
                        color = settings.PURPLE
                    elif res[3] == 'turqoise':
                        color = settings.TURQOISE
                                            
                    return x, y, color, org
                else:
                    print 'not red\r'
    return None


def _is_red( img_a, x, y, radius):
    """
    Takes an image array (numpy) as an argument, and calculates the average color in a square of with width = height = radius around the pixel coordiantes x, y.
    The calculated average color is used to determine if the pixel area around  
    """
    # h, w, c = img_a.shape
    # img = utils.array2cv(img_a) 
    #h, w, c = img_a.shape
    h = img_a.height
    w = img_a.width
    c = 3

    R,G,B = 0.0,0.0,0.0
    if radius < 2:
        R,G,B = img_a[y][x][RED], img_a[y][x][GREEN], img_a[y][x][BLUE]

    else:
        start_x = max(x - (radius-1/2), 0)
        end_x = min(x + (radius-1/2) + 1, w)
        start_y = max(y - (radius-1/2), 0)
        end_y = min(y + (radius-1/2) + 1, h)
        if radius % 2 == 0: # even
            end_x += 1
            end_y += 1

        for Y in range(start_y, end_y):
            for X in range(start_x, end_x):
                # R += img_a[Y][X][RED]
                # G += img_a[Y][X][GREEN]
                # B += img_a[Y][X][BLUE]
                R += img_a[Y,X][RED]
                G += img_a[Y,X][GREEN]
                B += img_a[Y,X][BLUE]
    
    denom = 0.0+R+G+B
    if denom > 0 and 0.40 < R/float(denom):
        return True
    return False

def _is_green( img_a, x, y, radius):
    """
    Takes an image array (numpy) as an argument, and calculates the average color in a square of with width = height = radius around the pixel coordiantes x, y.
    The calculated average color is used to determine if the pixel area around  
    """
    # h, w, c = img_a.shape
    # img = utils.array2cv(img_a) 
    #h, w, c = img_a.shape
    h = img_a.height
    w = img_a.width
    c = 3

    R,G,B = 0.0,0.0,0.0
    if radius < 2:
        R,G,B = img_a[y][x][RED], img_a[y][x][GREEN], img_a[y][x][BLUE]

    else:
        start_x = max(x - (radius-1/2), 0)
        end_x = min(x + (radius-1/2) + 1, w)
        start_y = max(y - (radius-1/2), 0)
        end_y = min(y + (radius-1/2) + 1, h)
        if radius % 2 == 0: # even
            end_x += 1
            end_y += 1

        for Y in range(start_y, end_y):
            for X in range(start_x, end_x):
                # R += img_a[Y][X][RED]
                # G += img_a[Y][X][GREEN]
                # B += img_a[Y][X][BLUE]
                R += img_a[Y,X][RED]
                G += img_a[Y,X][GREEN]
                B += img_a[Y,X][BLUE]
    
    denom = 0.0+R+G+B
    if denom > 0 and 0.60 < G/float(denom):
        return True
    return False



def detect_red_blob( img_a, step=5, avg_rad=3 ):
    img = utils.array2cv(img_a) 
    #h, w, c = img_a.shape
    h = img.height
    w = img.width
    c = 3

    TOP, BOTTOM, LEFT, RIGHT = h,-1,w,-1
    step, avg_rad = int(step), int(avg_rad)

    y = 0
    while y < h:
        x = 0
        while x < w:
            if _is_red(img, x, y, avg_rad):
                TOP = min(TOP, y)
                BOTTOM = max(BOTTOM, y)
                LEFT = min(LEFT, x)
                RIGHT = max(RIGHT, x)
                
            x += step
        y += step

    #print "---top,bottom,left,right", TOP, BOTTOM, LEFT, RIGHT
    width = RIGHT - LEFT
    if width == -1-w: # a test if red blob was found
        return None   # else:
    height = BOTTOM - TOP
    xpos = LEFT + width/2
    ypos = TOP + height/2
    return (xpos, ypos),(width, height)

def detect_green_blob( img_a, step=5, avg_rad=3 ):
    img = utils.array2cv(img_a) 
    #h, w, c = img_a.shape
    h = img.height
    w = img.width
    c = 3

    TOP, BOTTOM, LEFT, RIGHT = h,-1,w,-1
    step, avg_rad = int(step), int(avg_rad)

    y = 0
    while y < h:
        x = 0
        while x < w:
            if _is_green(img, x, y, avg_rad):
                TOP = min(TOP, y)
                BOTTOM = max(BOTTOM, y)
                LEFT = min(LEFT, x)
                RIGHT = max(RIGHT, x)
                
            x += step
        y += step

    #print "---top,bottom,left,right", TOP, BOTTOM, LEFT, RIGHT
    width = RIGHT - LEFT
    if width == -1-w: # a test if red blob was found
        return None   # else:
    height = BOTTOM - TOP
    xpos = LEFT + width/2
    ypos = TOP + height/2
    return (xpos, ypos),(width, height)



def main(filename = "images/mark3.png", search_step = 3):
    """
    call blobdetect from terminal w/ optional commandline arguments
    [ fileuri ], [search_pixel_step ], e.g.

    > python blobdetect.py images/mark3.png 3
    """
    if 1 < len(sys.argv):
        filename = sys.argv[1]
    print "Reads in", filename

    img_array = np.asarray( cv.LoadImageM( filename ) )

    if 2 < len(sys.argv):
        search_step = sys.argv[2]

    dt1 = datetime.datetime.now()
    print " Detecting red blobs, w/ search step",search_step,"px ..."
    blob = detect_red_blob( img_array, search_step)
    dt2 = datetime.datetime.now() - dt1

    dba = np.asarray( cv.LoadImageM( filename ) )
    if blob is not None:
        (xpos, ypos), (width, height) = position, size = blob
        print " Results:\n  Blob center position (x,y):",position,"\n  Blob size (width, height):", size

        #paint findings!
        for x in range(xpos-5, xpos+6):
            dba[ypos][x] = [255,0,0]
        for y in range(ypos-5, ypos+6):
            dba[y][xpos] = [255,0,0]
        t = ypos - height/2
        l = xpos - width/2
        b = ypos + height/2
        r = xpos + width/2
        for x in range( l, r ):
            dba[t][x] = [255,0,0]
        for x in range( l, r ):
            dba[b][x] = [255,0,0]
        for y in range( t, b ):
            dba[y][l] = [255,0,0]
        for y in range( t, b ):
            dba[y][r] = [255,0,0]
        print " look in: images/debug.png"
    else:
        print " Results:\n  No red blob found...!"

    print " Done in -", float(dt2.microseconds + dt2.seconds*10.0**6)/10.0**3 , "mSecs\n Exiting..."


    cv.SaveImage( "images/debug.png", cv.fromarray( dba ) )

if __name__ == "__main__":
    main()
