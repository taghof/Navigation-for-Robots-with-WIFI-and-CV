import sys

import numpy as np
import cv2
from common import anorm
from functools import partial

help_message = '''SURF image match 

USAGE: findobj.py [ <image1> <image2> ]
'''

FLANN_INDEX_KDTREE = 1  # bug: flann enums are missing

flann_params = dict(algorithm = FLANN_INDEX_KDTREE,
                    trees = 4)

def match_bruteforce(desc1, desc2, r_threshold = 0.75):
    res = []
    for i in xrange(len(desc1)):
        dist = anorm( desc2 - desc1[i] )
        n1, n2 = dist.argsort()[:2]
        r = dist[n1] / dist[n2]
        if r < r_threshold:
            res.append((i, n1))
    return np.array(res)

def match_flann(desc1, desc2, r_threshold = 0.6):
    flann = cv2.flann_Index(desc2, flann_params)
    idx2, dist = flann.knnSearch(desc1, 2, params = {}) # bug: need to provide empty dict
    mask = dist[:,0] / dist[:,1] < r_threshold
    idx1 = np.arange(len(desc1))
    pairs = np.int32( zip(idx1, idx2[:,0]) )
    return pairs[mask]

def draw_match(img1, img2, p1, p2, status = None, H = None):
    #img2.shape = (144,176)
    h1, w1 = img1.shape[:2]
    h2, w2 = img2.shape[:2]
    vis = np.zeros((max(h1, h2), w1+w2), np.uint8)
    vis[:h1, :w1] = img1
    vis[:h2, w1:w1+w2] = img2
    vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)

    if H is not None:
        corners = np.float32([[0, 0], [w1, 0], [w1, h1], [0, h1]])
        corners = np.int32( cv2.perspectiveTransform(corners.reshape(1, -1, 2), H).reshape(-1, 2) + (w1, 0) )
        cv2.polylines(vis, [corners], True, (255, 255, 255))
    
    if status is None:
        status = np.ones(len(p1), np.bool_)
    green = (0, 255, 0)
    red = (0, 0, 255)
    for (x1, y1), (x2, y2), inlier in zip(np.int32(p1), np.int32(p2), status):
        col = [red, green][inlier]
        if inlier:
            cv2.line(vis, (x1, y1), (x2+w1, y2), col)
            cv2.circle(vis, (x1, y1), 2, col, -1)
            cv2.circle(vis, (x2+w1, y2), 2, col, -1)
        else:
            r = 2
            thickness = 3
            cv2.line(vis, (x1-r, y1-r), (x1+r, y1+r), col, thickness)
            cv2.line(vis, (x1-r, y1+r), (x1+r, y1-r), col, thickness)
            cv2.line(vis, (x2+w1-r, y2-r), (x2+w1+r, y2+r), col, thickness)
            cv2.line(vis, (x2+w1-r, y2+r), (x2+w1+r, y2-r), col, thickness)
    return vis



def match(imga1, imga2):
   
    img1 = imga1#cv2.imread(fn1, 0)
    img2 = imga2#cv2.imread(fn2, 0)

    surf = cv2.SURF(10, 4, 2, False, True)
    
    kp1, desc1 = surf.detect(img1, None, False)
    kp2, desc2 = surf.detect(img2, None, False)
    
    if len(desc1) > 0 and len(desc2) > 0:
        desc1.shape = (-1, surf.descriptorSize())
        desc2.shape = (-1, surf.descriptorSize())
    else:
        return None
#    print 'img1 - %d features, img2 - %d features' % (len(kp1), len(kp2))

    def match_and_draw(match, r_threshold):
        m = match(desc1, desc2, r_threshold)
        
        #print 'Matched: ' + str(len(m))
        matched_p1 = np.array([kp1[i].pt for i, j in m])
        matched_p2 = np.array([kp2[j].pt for i, j in m])
       
        if len(matched_p1) > 3 and len(matched_p2) > 3: 
            H, status = cv2.findHomography(matched_p1, matched_p2, cv2.RANSAC, 10.0)
        else:
            H = None
            status = None

        if len(matched_p2 > 0):
            point = (matched_p2[0][0],matched_p2[0][1])
        else:
            point = None

        vis = draw_match(img1, img2, matched_p1, matched_p2, status, H)
        return (vis, len(m), point)

    # print 'bruteforce match:',
    vis_brute = match_and_draw( match_bruteforce, 0.65 )
    return vis_brute

    # print 'flann match:',
    #vis_flann = match_and_draw( match_flann, 0.8 ) # flann tends to find more distant second
    #return vis_flann                                               # neighbours, so r_threshold is decreased

