import requests
import time
import json
from scipy import misc
import cv2
from io import BytesIO
from tqdm import tqdm

team_name = "Lgfw23"
code = "32f3"

cv2.namedWindow("img", cv2.WINDOW_NORMAL)

server_url = '192.168.1.200'
ctrl_url = "http://{}:6010/ctrl".format(server_url)
frame_url = "http://{}:6010/get_frame".format(server_url)
loginn_url = "http://{}:6010/loginn".format(server_url)
logout_url = "http://{}:6010/logout".format(server_url)

log_inn = {"name": team_name, "code": code}
response = requests.put(loginn_url, data=json.dumps(log_inn))
print(response.text)

cmd = {"code": code, "cmd": "", "pwr": 1}

try:
    for i in tqdm(range(0, 999999)):
        response = requests.get(frame_url)
        img_arr = misc.imread(BytesIO(response.content))
        cv2.imshow("img", img_arr)
        cv2.waitKey(1)

        cmd["cmd"] = "up_right"
        cmd["pwr"] = 3
        response = requests.put(ctrl_url, data=json.dumps(cmd))
        time.sleep(0.17)
finally:
    response = requests.put(logout_url, data=json.dumps(log_inn))
    print(response.text)
