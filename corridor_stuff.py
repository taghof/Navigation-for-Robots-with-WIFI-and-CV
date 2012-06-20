#!/usr/bin/python
# This is a standalone program. 
# Pass an image name as a first parameter of the program,
# and an angel for the horizontal line as the second parameter.

import cv2, math, numpy, random, cv2.cv as cv

def findCorridorVanishPoint(img_a, y_tilt, from_main=False):
    """

    params: img_a, the image array to search in for a vanishing point
    y_tilt, float in degrees between -90 to 0 to +90, where negative
    values mean the drones left side is tilted down

    returns vainshing point location in px pair and probability

    """

    horizon_rad = (( -y_tilt + 90.0 )*math.pi) / 180.0

    border = 4.0*math.pi / 180.0 # 4.0, 8.0, *7.0*
    w, h = size = (img_a.shape[1], img_a.shape[0])
    dst = cv.CreateImage(size, 8, 1)

    cell_width, cell_height = w/11, h/11

    #gray = numpy.asarray(cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY))
    #gray = cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY)
    #gray = numpy.asarray(img_a)
    gray = cv.fromarray(img_a)
    #gray = img_a

    #dst = cv2.Canny( gray, 50, 200, 3 )
    cv.Canny( gray, dst, 50, 200, 3 )
    #dst = cv2.Canny(img_a, 50, 200, 3)
    storage = cv.CreateMemStorage(0)
    lines = cv.HoughLines2(dst, storage, cv.CV_HOUGH_STANDARD, 1, math.pi/180, 100, 0, 0)

    # lodrette og vandrette theta vaerdier der skal skilles fra
    lille_lodret_rad = horizon_rad - (math.pi/2) + border # + (math.pi/2) + border
    lille_vandret_rad = horizon_rad - border
    stor_vandret_rad = (horizon_rad + border)
    stor_lodret_rad = horizon_rad + (math.pi/2) - border

    if from_main: ## # for debugg
        print "y_tilt", y_tilt, "horizon_rad", horizon_rad
        print "image size:", size
        color_dst = cv.CreateImage(size, 8, 3)
        cv.CvtColor(dst, color_dst, cv.CV_GRAY2BGR)
        print "shape", img_a.shape
        print "border", border
        print "cell w, h:", cell_width, cell_height
        print "type gray", type( gray )
        ## #
        cells = numpy.zeros((11,11), dtype=numpy.int)
        ## # drawing cell boundaries
        for xx in range(0, w, cell_width):
            cv.Line(color_dst, (xx,0), (xx,h), cv.RGB(0,255,0), 1, 8)
        for yy in range(0, h, cell_height):
            cv.Line(color_dst, (0,yy), (w,yy), cv.RGB(0,255,0), 1, 8)

        print "v 0:", lille_lodret_rad
        print "v 1:", lille_vandret_rad
        print "v 2:", stor_vandret_rad
        print "v 3:", stor_lodret_rad
        linier = 0
    ## #

    diagonal_lines = []
    # Filtrer linier fra
    for (rho, theta) in lines:
        if ((stor_vandret_rad < theta < stor_lodret_rad)) or ((lille_lodret_rad < theta < lille_vandret_rad)):
            #doTheBartMan()
            alpha = -math.tan((math.pi/2)-theta)
            beta = math.sin(theta)*rho + (-math.cos(theta)*rho) * alpha
            diagonal_lines.append((alpha, beta))

            ## #
            if from_main and ((linier % 5) == 1):# and (linier < 175):
                a = math.cos(theta)
                b = math.sin(theta)
                x0 = a * rho 
                y0 = b * rho
                pt1 = (cv.Round(x0 + 10000*(-b)), cv.Round(y0 + 10000*(a)))
                pt2 = (cv.Round(x0 - 10000*(-b)), cv.Round(y0 - 10000*(a)))
            #cv.Line(color_dst, pt1, pt2, cv.RGB(255, 0, 0), 1, 8)
                color = cv.RGB(125*random.random(),125*random.random(),125*random.random())
                cv.Line(color_dst, pt1, pt2, color, 1, 8)
            linier += 1
            ## #

            if 200 < len(diagonal_lines):
                break

    maxlines = 100

    lines2compare = diagonal_lines[:maxlines] #clone
    for (a1, b1) in diagonal_lines[:maxlines]:
        lines2compare.remove((a1, b1))
        for (a2, b2) in lines2compare:
            try: # hvis 1 og 2 har samme haeldning
                x = (b2-b1)/(a1-a2)
                y = a1 * x + b1

                if 0 < x < w and 0 < y < h: # tilfoejelse og hvis a1 og a2 er naesten vinkelrette !!!
                    try:
                        cix = int( (x-(cell_width/2)) / cell_width )
                        ciy = int( (y-(cell_height/2)) / cell_height )
                        cells[ciy][cix] = cells[ciy][cix] + 1
                    except IndexError, ie:
                        print "x: {0}, cell_width: {1}, cix: {2}".format(x, cell_width, cix)
                        print "y: {0}, cell_height: {1}, ciy: {2}".format(y, cell_height, ciy)
                        raise ie

                    #if from_main:
                    #    cv.Circle( color_dst, (int(x), int(y)), 10, cv.RGB(0,0,255), 2, 8, 0 )
                    ## #
            except ZeroDivisionError, zde:
                pass # if a1 == a2  <=> paralelle, ingen skaering


    # eventuelt lave en gauss filtrering...

    bc = [0.0, 0, 0]
    for row in range(len(cells)):
        for c in range(len(cells[row])):
            if cells[row][c] > bc[0]:
                bc = [cells[row][c], row, c]

    vp = (((bc[2]+1)*cell_width)-(cell_width/2), ((bc[1]+1)*cell_height)-(cell_height/2))

    ## # Debugg
    if from_main:
        print "number of diagonal_lines:", len(diagonal_lines)
        #print cells
        print "bc[]:", bc
        p1 = (bc[2]*cell_width, bc[1]*cell_height)
        p2 = (bc[2]*cell_width+cell_width, bc[1]*cell_height+cell_height)
        cv.Rectangle(color_dst, p1, p2, cv.RGB(0,255,255), 4,8,0)
        print "(vp):", vp
        print "index x, y;", vp[0]/cell_height , vp[1]/cell_width

        font = cv.InitFont( cv.CV_FONT_HERSHEY_SIMPLEX, 1.0, 1.0, 0.0, 3, 8) # thikness, linetype
    #cv.putText( color_dst, "hello", vp, cv.CV_FONT_HERSHEY_SIMPLEX, 1.0, cv.RGB(128,128,128))
        #cv.PutText( color_dst, "hello", vp, font, cv.RGB(128,128,128))

        for r in range(len(cells)):
            for c in range(len(cells[r])):

                str_ = ("%03d" % cells[c][r])
                if int(str_) == 0:
                    continue
                elif (cells[c][r] / 1000) > 0:
                    offset = 3
                    str_ = ("%03d" % cells[c][r])
                elif (cells[c][r] / 100) > 0:
                    offset = 2
                    str_ = str( cells[c][r] )
                elif (cells[c][r] / 10) > 0:
                    offset = 1
                    str_ = str( cells[c][r] )
                else:
                    offset = 0
                    str_ = str( cells[c][r] )
                p = ( ((r+1)*cell_width)-(cell_width/2)-(offset*12), ((c+1)*cell_height)-(cell_height/2) )
                cv.PutText( color_dst, str_ , p, font, cv.RGB(55,255,50))

    #cv2.putText(color_dst, "hello", vp, cv2.FONT_HERSHEY_PLAIN, 1.0, (0, 0, 0), thickness = 2, linetype=cv2.CV_AA)

    #cv.SaveImage( "out_"+filename, color_dst)

        #end_dst = numpy.asarray( cv.CreateImage(( 800, 600 ), 8, 3) )
    #end_dst = cv2.resize(color_dst, (800, 600)) #, interpolation=cv.CV_INTER_LINEAR)

        #horizon_rad
        h_w = int(w/2)
        h_h = int(3*h/4)
        d_h = h_w*math.tan((( -y_tilt )*math.pi) / 180.0) #horizon_rad)

        pt1 = ( cv.Round(0), cv.Round(h_h-d_h) )
        pt2 = ( cv.Round(w), cv.Round(h_h+d_h) )

        #a = math.cos( horizon_rad )
        #b = math.sin( horizon_rad )
        #x0 = a * rho 
        #y0 = b * rho
        #pt1 = (cv.Round(x0 + 10000*(-b)), cv.Round(y0 + 10000*(a)))
        #pt2 = (cv.Round(x0 - 10000*(-b)), cv.Round(y0 - 10000*(a)))
            #cv.Line(color_dst, pt1, pt2, cv.RGB(255, 0, 0), 1, 8)
        color = cv.RGB(0,0,255)
        cv.Line(color_dst, pt1, pt2, color, 3, 8)

        cv.PutText( color_dst, "Theta %2.2f" % y_tilt, (h_w-85, h_h), font, cv.RGB(255,0,255))
        

        #print type(color_dst)

        #cv.NamedWindow("Hough", 1)

        #thumbnail = cv.CreateMat( 600, 800, cv.CV_8UC3)
        #cv.Resize(color_dst, thumbnail)
        #cv.ShowImage("Hough", thumbnail) #color_dst)
        cv.ShowImage("Hough", color_dst)
        #cv.SaveImage( "out_put.png", thumbnail) #color_dst)
    ## #

    return vp, (float(bc[0])/float(maxlines)) # tell tell sign also if the color behind the cell is very bright, af feature of the IT-byen cooridors...



if __name__ == "__main__":
    import sys

    filename = "1.jpg"
    h_angel = 1.9 #2.25
    #filename = "2.jpg"
    #h_angel = -2.38 
    #h_angel = -32.0 
    # som fra drone.phi, ned venstre side => negativ ned til -90
    #                    vandret          => 0.0 
    #                    ned hoejre side  => positiv op til   90
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    if len(sys.argv) > 2:
        h_angel = float(sys.argv[2])

    im = cv2.imread( filename, 0 )
    print "type im", type(im)
    #im = cv.LoadImage(filename, cv.CV_LOAD_IMAGE_GRAYSCALE)
    #im = numpy.fromfile(filename, dtype=numpy.int64)
    #print "shape", im.shape

    p, ss = findCorridorVanishPoint(im, h_angel, from_main=True)
    print p, ss

    cv.WaitKey(0)

    #v1jpg = 2.3815
    #v5jpg = -2.33268179
