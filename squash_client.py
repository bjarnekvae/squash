import requests
import time
import json
from scipy import misc
import cv2
from io import BytesIO

# README:
# - All requests must contain a code
# - Requests are limited to 20 Hz
# - Control input is paddle speed
#
# Possible directions:
# 'up', 'down', 'left', 'right', 'up_left', 'up_right', 'down_left', 'down_right' or ''
# speed = 0 - 1 (float)

team_name = "team_name"
code = "1234"

cv2.namedWindow("img", cv2.WINDOW_NORMAL)

server_url = '192.168.1.200'  # <- must be changed to server IP
ctrl_url = "http://{}:6010/ctrl".format(server_url)
frame_url = "http://{}:6010/get_frame".format(server_url)
loginn_url = "http://{}:6010/loginn".format(server_url)
logout_url = "http://{}:6010/logout".format(server_url)

log_inn = {"name": team_name, "code": code}
response = requests.put(loginn_url, data=json.dumps(log_inn))
print(response.text)

cmd = {"code": code, "direction": "", "speed": 0.5}
i = 0
try:
    while True:
        response = requests.get(frame_url)
        img_arr = misc.imread(BytesIO(response.content))
        img_arr = cv2.cvtColor(img_arr, cv2.COLOR_RGB2BGR)
        cv2.imshow("img", img_arr)
        cv2.waitKey(1)

        if i % 20 == 0:
            cmd["direction"] = "right"
            cmd["speed"] = 1.0
            response = requests.put(ctrl_url, data=json.dumps(cmd))
            print("right")

        if (i+10) % 20 == 0:
            cmd["direction"] = "left"
            cmd["speed"] = 0.9
            response = requests.put(ctrl_url, data=json.dumps(cmd))
            print("left")

        time.sleep(0.05)
finally:
    response = requests.put(logout_url, data=json.dumps(log_inn))
    print(response.text)
