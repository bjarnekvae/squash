import requests
import time
import json
from scipy import misc
import imageio
import cv2
from io import BytesIO
from tqdm import tqdm
from queue import Queue
import threading
from simple_pid import PID
import json
import numpy as np



# README:
# - All requests must contain a code
# - Requests are limited to 20 Hz
# - Control input is paddle speed
#
# Possible directions:
# 'up', 'down', 'left', 'right', 'up_left', 'up_right', 'down_left', 'down_right' or ''
# speed = 0 - 1 (float)

paddle_coord_m = threading.Lock()

team_name = "bjarne2"
code = "12334"

cv2.namedWindow("img", cv2.WINDOW_NORMAL)

server_url = '127.0.0.1'#'192.168.1.200'  # <- must be changed to server IP
#server_url = '192.168.1.200'
ctrl_url = "http://{}:6010/ctrl".format(server_url)
frame_url = "http://{}:6010/get_frame".format(server_url)
loginn_url = "http://{}:6010/loginn".format(server_url)
logout_url = "http://{}:6010/logout".format(server_url)

log_inn = {"name": team_name, "code": code}
response = requests.put(loginn_url, data=json.dumps(log_inn))
side = json.loads(response.text)
print(side)

cmd = {"code": code, "direction": "", "speed": 0.5}

def rotation_matrix(theta):
    theta *= np.pi/180
    matrix = np.array([
        [np.cos(theta), -np.sin(theta)],
        [np.sin(theta), np.cos(theta)]
    ])

    return matrix


ctrl_loop_hz = 15
pid_x = PID(0.01, 0.0000, 0.0001)
pid_x.sample_time = 1/ctrl_loop_hz
pid_x.output_limits = (-0.999, 0.999)
pid_y = PID(0.026, 0.0000, 0.001)
pid_y.sample_time = 1/ctrl_loop_hz
pid_y.output_limits = (-0.999, 0.999)

current_coord = (0, 0)
other_guy_coords = (0, 0)
setpoint_coords = (0, 0)

def control_loop():
    t = time.time()
    u = [0, 0]
    while True:
        with paddle_coord_m:
            current_paddle_pos = current_coord
            setpoint = setpoint_coords

        pid_x.setpoint = float(setpoint[0])
        pid_y.setpoint = float(setpoint[1])

        u[0] = float(pid_x(float(current_paddle_pos[0])))
        u[1] = float(pid_y(float(current_paddle_pos[1])))

        cmd["direction"] = ''
        cmd["speed"] = 0.0

        if abs(setpoint[0] - current_paddle_pos[0]) > 10:
            if u[0] > 0:
                cmd["direction"] = "right"
                cmd["speed"] = u[0]
            elif u[0] <= 0:
                cmd["direction"] = "left"
                cmd["speed"] = -u[0]
        else:
            if u[1] > 0:
                cmd["direction"] = "down"
                cmd["speed"] = u[1]
            elif u[1] <= 0:
                cmd["direction"] = "up"
                cmd["speed"] = -u[1]

        print(cmd)

        resp = requests.put(ctrl_url, data=json.dumps(cmd))
        #print(resp)

        if 1/ctrl_loop_hz > time.time() - t:
            time.sleep(1/ctrl_loop_hz - (time.time() - t))
        t = time.time()


threading.Thread(target=control_loop, daemon=True).start()

right_colour = (0, 0, 255)
left_color = (0, 255, 0)
black = (0, 0, 0)
WIDTH = 480
HEIGHT = 640

left_paddle_cords = [0, 0]
right_paddle_cords = [0, 0]
ball_cords = np.array([0, 0])

prev_ball_coords = np.zeros([2, 5])

try:
    for i in range(0, 999999):
        response = requests.get(frame_url)
        img_arr = imageio.imread(BytesIO(response.content))

        left_paddle_range = cv2.inRange(img_arr[int(HEIGHT/2):-1, :, :], (0, 254, 0), left_color)
        right_paddle_range = cv2.inRange(img_arr[int(HEIGHT/2):-1, :, :], (0, 0, 254), right_colour)
        ball_range = cv2.inRange(img_arr, black, (1, 1, 1))

        left_cnt, _ = cv2.findContours(left_paddle_range, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        right_cnt, _ = cv2.findContours(right_paddle_range, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        ball_cnt, _ = cv2.findContours(ball_range, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        for c in right_cnt:
            M = cv2.moments(c)
            if M["m00"] == 0:
                ball_cords[0] = ball_cords[1] = 0
            else:
                right_paddle_cords[0] = int(M["m10"] / M["m00"])
                right_paddle_cords[1] = int(M["m01"] / M["m00"]) + int(HEIGHT / 2)
            cv2.circle(img_arr, (right_paddle_cords[0], right_paddle_cords[1]), 7, (128, 128, 128), 3)

        for c in left_cnt:
            M = cv2.moments(c)
            if M["m00"] == 0:
                ball_cords[0] = ball_cords[1] = 0
            else:
                left_paddle_cords[0] = int(M["m10"] / M["m00"])
                left_paddle_cords[1] = int(M["m01"] / M["m00"]) + int(HEIGHT / 2)
            cv2.circle(img_arr, (left_paddle_cords[0], left_paddle_cords[1]), 7, (128, 128, 128), 3)

        for c in ball_cnt:
            M = cv2.moments(c)
            if M["m00"] == 0:
                ball_cords[0] = ball_cords[1] = 0
            else:
                ball_cords[0] = int(M["m10"] / M["m00"])
                ball_cords[1] = int(M["m01"] / M["m00"])
            cv2.circle(img_arr, (ball_cords[0], ball_cords[1]), 7, (128, 128, 128), 3)

        with paddle_coord_m:
            if side['status'] == 'left':
                current_coord = left_paddle_cords
                other_guy_coords = right_paddle_cords
            elif side['status'] == 'right':
                current_coord = right_paddle_cords
                other_guy_coords = left_paddle_cords
            elif side['status'] == 'full': # TEMP
                current_coord = left_paddle_cords
                other_guy_coords = right_paddle_cords

            my_turn = False
            if img_arr[28, int(WIDTH / 16 * 2), 1] == 255 and img_arr[28, int(WIDTH / 16 * 2), 0] == 0:
                if side['status'] == 'left' or side['status'] == 'full':
                    my_turn = True
            elif side['status'] == 'right':
                my_turn = True

            #my_turn = True

            for i in range(prev_ball_coords.shape[1] - 1):
                prev_ball_coords[:, i] = prev_ball_coords[:, i + 1]
            prev_ball_coords[:, -1] = ball_cords.copy()

            ball_vector = np.mean(np.diff(prev_ball_coords, axis=1), axis=1)

            if abs(ball_vector[1]) > 0:
                theta = np.arctan(ball_vector[1] / ball_vector[0])
                y = (current_coord[1] - ball_cords[1]) / np.tan(theta) + ball_cords[0]
                if y < 0:
                    y = -y
                elif y > WIDTH:
                    y = WIDTH - (y - WIDTH)
            else:
                y = ball_cords[0]

            x_setpoint = y

            if ball_cords[1] > HEIGHT/2 and ball_vector[1] > 0:
                y_setpoint = ball_cords[1]
            else:
                y_setpoint = HEIGHT - 60


            if my_turn:
                setpoint_coords = np.array([x_setpoint, y_setpoint]).copy()
            else:

                if np.linalg.norm(current_coord - ball_cords)*np.linalg.norm(ball_vector) > 6000:
                    setpoint_coords = other_guy_coords.copy()
                else:
                    setpoint_coords = np.array([0, HEIGHT]).copy()


        img_arr = cv2.line(img_arr, (ball_cords[0], ball_cords[1]), (int(y), int(current_coord[1])), (0, 0, 0), 1)

        cv2.imshow("img", img_arr)
        cv2.waitKey(1)
        time.sleep(0.05)
finally:
    response = requests.put(logout_url, data=json.dumps(log_inn))
    print(response.text)
