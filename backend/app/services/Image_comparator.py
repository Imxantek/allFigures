import cv2
import numpy as np
from os import listdir
import requests
import csv
from fake_useragent import UserAgent
ua=UserAgent()
headers = {'User-Agent': ua.random}
sift = cv2.SIFT_create()
bf = cv2.BFMatcher()
# brute force matching for keypoints
# knnMatch with k=2 returns a list of tuples
# where the first value is the best match
# and the snd is the snd best match
def prepare_image(file_path):

    if "https" in file_path:
        resp=requests.get(file_path, headers=headers, timeout=30)
        if resp.status_code != 200:
            return None, None
        image_array = np.frombuffer(resp.content, dtype=np.uint8)
        img = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    else:
        file_path="../static/"+file_path
        img = cv2.imread(file_path, cv2.IMREAD_COLOR)

    if img is None:
        print(f"File not found: {file_path}")
        return None, None
    # convert image to grayscale
    bgr=img
    gray=cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    # threshold for binary image conversion
    # a binary image is an image consisting of 0s and 1s
    # i've set a threshold of (245-255) for my grayscale image
    # THRESH BINARY INV inverts the logic so that if our mask fits into the
    # threshold, the figure is ones and the background is zeros
    retval, mask = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY_INV)
    # cv2.imwrite("mask.png", mask)
    # we are using find contours to locate a bounding box of an image
    contours, hierarchy=cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, None

    # get the largest contour, presumably the figure
    c=max(contours, key=cv2.contourArea)
    # draw it in red
    # cv2.drawContours(img, [c], 0, (0, 0, 255), 3)
    # now create a bounding rectangle of our contour
    x, y, w, h = cv2.boundingRect(c)
    # and draw it in green
    # cv2.rectangle(img, (x,y), (x+w, y+h), (0, 255, 0), 2)
    crop_img=img[y:y+h, x:x+w]
    crop_mask=mask[y:y+h, x:x+w]

    crop_img = cv2.resize(crop_img, (300, 600))
    crop_mask = cv2.resize(crop_mask, (300, 600), interpolation=cv2.INTER_NEAREST)

    return crop_img, crop_mask


def hist_score(img1, mask1, img2, mask2):
    # conversion to HSV color palette
    hsv1=cv2.cvtColor(img1, cv2.COLOR_BGR2HSV)
    hsv2=cv2.cvtColor(img2, cv2.COLOR_BGR2HSV)
    # create the histograms for HSV basing on H and S
    # set the bins to 50, 60 - larger values would lead for the
    # comparison to be too strict
    hist1=cv2.calcHist([hsv1], [0,1], mask1, [50,60], [0,180,0,256])
    hist2=cv2.calcHist([hsv2], [0,1], mask2, [50,60], [0,180,0,256])
    # normalization process - sometimes f.e. yellow pixels can take
    # 72000 pixels on img1 and 80000 pixels on img2
    # the normalization process scales those values in regard
    # to the histograms maximal value
    cv2.normalize(hist1, hist1, 0, 1, cv2.NORM_MINMAX)
    cv2.normalize(hist2, hist2, 0, 1, cv2.NORM_MINMAX)

    # compare those two histograms using the compareHist methods
    correl = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
    return max(0.0, correl)

def SIFT_score(img1, mask1, img2, mask2):


    # convert to grays
    gray1=cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2=cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

    # find the keypoints with sift
    kp1, des1 = sift.detectAndCompute(gray1, mask1)
    kp2, des2 = sift.detectAndCompute(gray2, mask2)
    if des1 is None or des2 is None or len(kp1) < 2 or len(kp2) < 2:
        return 0.0
    successes=[]


    matches = bf.knnMatch(des1, des2, k=2)

    for tup in matches:
        if len(tup)==2:
            fst, snd=tup
            # this is very important:
            # f.e. the first best match got a distance of 10
            # and the snd best got a distance of 75
            # then it's probably a good match - there is only one kp that matches
            # if not - then the match is not so good
            # f.e. first match got a score of 70
            # and the second got a score of 75.
            # not so sure for this kp so its most likely a fail
            if fst.distance < 0.75*snd.distance:
                successes.append(fst)

    # successes=[match for match in matches if match.distance]

    # calculate a score - a ratio of successes and all kp from 1 or 2 (smaller val)
    score=len(successes)/min(len(kp1), len(kp2))
    # for SIFT a score of 25-30% is a success hence we need to multiply the score *3
    return min(1.0, score*3)

def compare(src, targ):
    img1, mask1 = prepare_image(src)
    img2, mask2 = prepare_image(targ)
    if img1 is None or img2 is None:
        return 0.0
    sift=SIFT_score(img1, mask1, img2, mask2)
    hist=hist_score(img1, mask1, img2, mask2)
    return (sift+hist)/2


if __name__ == "__main__":
    # test
    path="../static/images/figures/"
    imgs=listdir(path)
    src=path+"4666_6.png"
    matches=[]
    with open("scores.csv","w") as csvfile:
        for img in imgs:
            if img.startswith("4666_"):
                continue
            targ=path+img
            score=compare(src, targ)
            print(f"Targ: {targ}, score: {score}")
            csvfile.write(str(score))
            if score > 0.9:
                matches.append(targ)
    print(matches)
    # print(compare(src, targ))