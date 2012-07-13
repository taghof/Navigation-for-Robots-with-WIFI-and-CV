import cv2
import numpy as np

#######   training part    ############### 
samples = np.loadtxt('generalsamples.data',dtype=np.float32)
responses = np.loadtxt('generalresponses.data',dtype=np.float32)
responses = responses.reshape((responses.size,1))
print samples.shape
print responses.shape

model = cv2.KNearest()
model.train(samples,responses)

############################# testing part  #########################

im = cv2.imread('./testdata/newtest2.png')
out = np.zeros(im.shape,np.uint8)
gray = cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)

# thresh = cv2.inRange(im, np.asarray((0, 0, 0)), np.asarray((60, 60, 60)))
# threshb = thresh
# threshb = cv2.medianBlur(thresh, 1)
thresh = cv2.adaptiveThreshold(gray,255,1,1,11,2)
cv2.imshow('thres', thresh)
cv2.waitKey(0)
contours,hierarchy = cv2.findContours(thresh,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)

found_filtered = []

def inside(r, q):
    rx, ry, rw, rh = r
    qx, qy, qw, qh = q
    return rx > qx and ry > qy and rx + rw < qx + qw and ry + rh < qy + qh

def rotateImage(image, angle):
  image_center = tuple(np.array(image.shape)/2)
  rot_mat = cv2.getRotationMatrix2D(image_center,angle,1.0)
  result = cv2.warpAffine(image, rot_mat, image.shape,flags=cv2.INTER_LINEAR)
  return result

for co, o in enumerate(contours):
    insider = False
    c1 = [x,y,w,h] = cv2.boundingRect(o)
   
    for ci, i in enumerate(contours):
        c2 = [x,y,w,h] = cv2.boundingRect(i)
        if co != ci and inside(c1, c2):
            insider = True
            break
   
    if not insider:
        found_filtered.append(o)

print len(found_filtered)
t = True
for cnt in found_filtered:
    if cv2.contourArea(cnt)>50:
        
        [x,y,w,h] = cv2.boundingRect(cnt)
        if  h>20:
            x = x-10
            y = y-10
            w = w+20
            h = h+20
            cv2.rectangle(im,(x,y),(x+w,y+h),(0,255,0),2)
            roi = thresh[(y):(y+h),(x):(x+w)]
            roismall = cv2.resize(roi,(20,20))
            roicopy = np.copy(roismall)
            roismall = roismall.reshape((1,400))
            roismall = np.float32(roismall)
            
            for i in range(72):
                angle = i*5
                res = rotateImage(roicopy, angle)
                
                # if t:
                #     import time
                #     cv2.imshow('roicopy',res)
                #     cv2.waitKey(1)
                #     time.sleep(0.1)
                    
                roismallrot = res.reshape((1,400))
                roismallrot = np.float32(roismallrot)

                roismall = np.vstack((roismall, roismallrot))

            t = False
            # print roismall.shape
            retval, results, neigh_resp, dists = model.find_nearest(roismall, k = 1)
            string = str(int((results[0][0])))
            cv2.putText(out,string,(x,y+h),0,1,(0,255,0))

cv2.imshow('im',im)
cv2.imshow('out',out)
cv2.waitKey(0)


