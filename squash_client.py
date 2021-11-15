import requests
import time
import json
from scipy import misc
import cv2
from io import BytesIO
from tqdm import tqdm

cv2.namedWindow("img", cv2.WINDOW_NORMAL)

test = dict()
ctr_url = "http://localhost:6010/ctrl"
frame_url = "http://localhost:6010/get_frame"


for i in tqdm(range(0, 999999)):
    response = requests.get(frame_url)
    img_arr = misc.imread(BytesIO(response.content))
    cv2.imshow("img", img_arr)
    cv2.waitKey(1)

    test["cmd"] = "down_left"
    response = requests.put(ctr_url, data=json.dumps(test))
    time.sleep(0.001)

