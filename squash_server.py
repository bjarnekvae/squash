#License MIT 2017 Ahmad Retha

import os
import pygame
import pygame.mixer
import threading
import queue
import json
import flask
import numpy as np
from PIL import Image
from io import BytesIO
import logging
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from glob import glob
import datetime
logging.getLogger('werkzeug').disabled = True
np.random.seed(datetime.datetime.now().microsecond)

rescale_trump = 160
d_trumps = glob("trump/*.png")
trump_heads = []
for d_trump in d_trumps:
    trump_head = pygame.image.load(d_trump)
    height = trump_head.get_height()
    width = trump_head.get_width()
    ratio = rescale_trump/height

    trump_head = pygame.transform.scale(trump_head, (rescale_trump, int(ratio*width)))
    trump_heads.append(trump_head)

n_trumps = len(trump_heads)

left_ctrl_q = queue.Queue(1)
right_ctrl_q = queue.Queue(1)
billboard_q = queue.Queue(5)

app = flask.Flask(__name__)
limiter = Limiter(app, key_func=get_remote_address)

frame = None
frame_mutex = threading.Lock()

server_url = '192.168.1.200'
remote_mode = True
left_player = dict()
left_player['ip'] = ''
left_player['name'] = ''
left_player['code'] = ''
left_player['score'] = 0
right_player = left_player.copy()
player_mutex = threading.Lock()

ctrl_limit = "20/second"

@app.route('/get_frame', methods=['GET'])
@limiter.limit(ctrl_limit)
def get_frame():
    # convert numpy array to PIL Image
    with frame_mutex:
        img = Image.fromarray(frame.astype('uint8'))

    # create file-object in memory
    file_object = BytesIO()

    # write PNG in file-object
    img.save(file_object, 'PNG')

    # move to beginning of file so `send_file()` it will read from start
    file_object.seek(0)

    return flask.send_file(file_object, mimetype='image/PNG')


@app.route('/ctrl', methods=['PUT'])
@limiter.limit(ctrl_limit)
def get_ctrl():
    client_data = json.loads(flask.request.data)
    #player_ip = flask.request.remote_addr
    resp = dict()
    resp['status'] = ""

    try:
        if left_player['code'] == client_data['code']:
            left_ctrl_q.put_nowait(client_data)
            resp['status'] = "OK"
        elif right_player['code'] == client_data['code']:
            right_ctrl_q.put_nowait(client_data)
            resp['status'] = "OK"
        else:
            resp['status'] = "Not logged inn"
    except queue.Full:
        resp['status'] = "Too fast!"

    return flask.jsonify(resp)


@app.route('/loginn', methods=['PUT'])
@limiter.limit("1/second")
def log_inn():
    client_data = json.loads(flask.request.data)
    #print(flask.request.remote_addr)
    resp = dict()
    resp['status'] = "full"

    with player_mutex:
        if left_player['code'] == '':
            left_player['code'] = client_data['code']
            left_player['name'] = client_data['name']
            resp['status'] = "left"
            print(client_data['name'], "({}) joined left side!".format(flask.request.remote_addr))
        elif right_player['code'] == '':
            right_player['code'] = client_data['code']
            right_player['name'] = client_data['name']
            resp['status'] = "right"
            print(client_data['name'], "({}) joined left side!".format(flask.request.remote_addr))

        if resp['status'] != "full":
            try:
                billboard_q.put_nowait("{} joined!".format(client_data['name']))
            except queue.Full:
                pass

    return flask.jsonify(resp)


@app.route('/logout', methods=['PUT'])
@limiter.limit("1/second")
def log_out():
    client_data = json.loads(flask.request.data)
    resp = dict()
    resp['status'] = "Not logged inn"

    with player_mutex:
        if left_player['code'] == client_data['code']:
            print(left_player['name'], "({}) left the game".format(flask.request.remote_addr))
            left_player['code'] = ''
            left_player['name'] = ''
            resp['status'] = "OK"
        elif right_player['code'] == client_data['code']:
            print(right_player['name'], "({}) left the game".format(flask.request.remote_addr))
            right_player['code'] = ''
            right_player['name'] = ''
            resp['status'] = "OK"

        print("Left: {}, Right {}".format(left_player['score'], right_player['score']))
        left_player['score'] = 0
        right_player['score'] = 0

        if resp['status'] != "Not logged inn":
            try:
                billboard_q.put_nowait("{} left!".format(client_data['name']))
            except queue.Full:
                pass

    return flask.jsonify(resp)


threading.Thread(target=lambda: app.run(host=server_url, port=6010, threaded=True), daemon=True).start()

##
# Game mode
#
WIDTH = 480
HEIGHT = 640
os.environ['SDL_VIDEO_WINDOW_POS'] = "%d,%d" % (WIDTH, 25)
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption('Squash')
clock = pygame.time.Clock()
pygame.key.set_repeat(50, 50)
pygame.mixer.pre_init(44100, -16, 2, 2048)
pygame.mixer.init()
pygame.init()

##
# Game consts
#
FONT = pygame.font.Font(None, 40)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED   = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE  = (0, 0, 255)
GRAY  = (100, 100, 100)
MODE_PLAY = 1
MODE_QUIT = 0
FRAME_RATE = 120

##
# Game Sounds and delay for losing
#
LOSE_DELAY = 2000
LOSE_SOUND = pygame.mixer.Sound('beep-2.wav')
FAIL_SOUND = pygame.mixer.Sound('beep-3.wav')
LEFT_SOUND = pygame.mixer.Sound('beep-7.wav')
RIGHT_SOUND = pygame.mixer.Sound('beep-8.wav')

##
# Game Vars
#
PADDLE_TAU = 0.15
BUDGE = 12
BALL_INIT_SPEED = 2
BALL_INIT_ANGLE = 30
BALL_BOUNCE_DECAY = 0.15
BALL_DECAY_RATE = 0.08/FRAME_RATE
BALL_RANDOM_BOUNCE = 5
BALL_PADLE_MAX_BOUNCE = 25
BALL_RADIUS = 4
MAX_PADDLE_POWER = 1.0001
PADDLE_SPEED = BALL_INIT_SPEED*0.8
PADDLE_SIZE = 70
PADDLE_THICKNESS = 12
PROB_TRUMP = 0.2 # A 20% chance for a Trump visit every 10 seconds
LEFT_PLAYER = True
RIGHT_PLAYER = False
muted = False
playerTurn = RIGHT_PLAYER
current_mode = MODE_PLAY
BILLBOARD_TEXT_VISIBLE = FRAME_RATE*1.5

def rotation_matrix(theta):
    theta *= np.pi/180
    matrix = np.array([
        [np.cos(theta), -np.sin(theta)],
        [np.sin(theta), np.cos(theta)]
    ])

    return matrix

ball_angle = BALL_INIT_ANGLE
ball_vector = rotation_matrix(ball_angle) @ np.array([0, -BALL_INIT_SPEED*1.5])

def is_toright(main_rect, sec_rect):
    x1 = main_rect[0]
    y1 = main_rect[1]
    x2 = main_rect[0] + PADDLE_SIZE/2
    y2 = main_rect[1] - PADDLE_THICKNESS/2
    y = (y2 - y1)/(x2 - x1)*(sec_rect[0] - x1) + y1

    if abs(y) < sec_rect[1]:
        return True
    else:
        return False

def is_toleft(main_rect, sec_rect):
    x1 = main_rect[0]
    y1 = main_rect[1]
    x2 = main_rect[0] - PADDLE_SIZE/2
    y2 = main_rect[1] - PADDLE_THICKNESS/2
    y = (y2 - y1)/(x2 - x1)*(sec_rect[0] - x1) + y1

    if abs(y) < sec_rect[1]:
        return True
    else:
        return False

def is_above(main_rect, sec_rect):
    x1 = main_rect[1]
    y1 = main_rect[0]
    x2 = main_rect[1] + PADDLE_THICKNESS/2
    y2 = main_rect[0] - PADDLE_SIZE/2
    y = (y2 - y1)/(x2 - x1)*(sec_rect[1] - x1) + y1

    if abs(y) > sec_rect[0]:
        return True
    else:
        return False

def is_under(main_rect, sec_rect):
    x1 = main_rect[1]
    y1 = main_rect[0]
    x2 = main_rect[1] - PADDLE_THICKNESS/2
    y2 = main_rect[0] - PADDLE_SIZE/2
    y = (y2 - y1)/(x2 - x1)*(sec_rect[1] - x1) + y1

    if abs(y) > sec_rect[0]:
        return True
    else:
        return False

##
# Game Objects
#

class Paddle(pygame.sprite.Sprite):
    def __init__(self, color, width, height, maxX, maxY, x, y):
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.Surface([width, height])
        self.image.fill(color)
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.color = color
        self.width = width
        self.height = height
        self.maxX = maxX
        self.maxY = maxY
        self.x = x
        self.y = y
        self.prev_x = x
        self.prev_y = y
        self.inp_x = x
        self.inp_y = y
        self.y_velocity = 0

    def set_xy(self, x, y):
        self.x = self.prev_x = self.inp_x = x
        self.y = self.prev_y = self.inp_y = y

    def move(self, moveX, moveY):
        self.inp_x = self.inp_x + moveX
        self.inp_y = self.inp_y + moveY

    def change_width(self, paddle_width):
        self.width = paddle_width
        self.image = pygame.Surface([self.width, self.height])
        self.image.fill(self.color)
        self.rect = self.image.get_rect()
        self.rect.x = self.x
        self.rect.y = self.y
        self.maxX = WIDTH - paddle_width

    def update(self):
        if self.inp_y < self.maxY/2:
            self.inp_y = self.maxY/2
        elif self.inp_y > self.maxY:
            self.inp_y = self.maxY
        if self.inp_x < 0:
            self.inp_x = 0
        elif self.inp_x > self.maxX:
            self.inp_x = self.maxX

        f_x = self.prev_x + (1/FRAME_RATE)/PADDLE_TAU * (self.inp_x - self.prev_x)
        f_y = self.prev_y + (1/FRAME_RATE)/PADDLE_TAU * (self.inp_y - self.prev_y)

        self.y_velocity = self.prev_y - f_y
        self.prev_x = f_x
        self.prev_y = f_y
        self.x = f_x
        self.y = f_y

        self.rect.topleft = [int(f_x), int(f_y)]

class Ball(pygame.sprite.Sprite):
    def __init__(self, color, x, y, radius):
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.Surface([2*radius, 2*radius])
        self.image.set_alpha(0)
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.color = color
        self.radius = radius
        self.x = x
        self.y = y

    def update(self):
        self.rect.topleft = [self.x, self.y]
        self.draw(screen)

    def draw(self, surface):
        pygame.draw.circle(surface, self.color, [int(self.x), int(self.y)], int(self.radius))

leftPaddle = Paddle(GREEN, PADDLE_SIZE, PADDLE_THICKNESS, WIDTH - PADDLE_SIZE, HEIGHT - PADDLE_THICKNESS, WIDTH/4 - PADDLE_SIZE/2, HEIGHT/4 * 3 - PADDLE_THICKNESS)
rightPaddle = Paddle(BLUE, PADDLE_SIZE, PADDLE_THICKNESS, WIDTH - PADDLE_SIZE, HEIGHT - PADDLE_THICKNESS, WIDTH/4 * 3 - PADDLE_SIZE/2, HEIGHT - PADDLE_THICKNESS)
ball = Ball(BLACK, WIDTH/4 - BALL_RADIUS, HEIGHT/4 * 3 - PADDLE_THICKNESS - 2 * BALL_RADIUS, BALL_RADIUS)
spriteGroup = pygame.sprite.Group()
spriteGroup.add(leftPaddle)
spriteGroup.add(rightPaddle)
spriteGroup.add(ball)

##
# Action on player score
#
paddle_size = PADDLE_SIZE
ball_velocity = BALL_INIT_SPEED
def reset_game(playerTurn):
    global ball_vector, ball_angle, leftPaddle, rightPaddle, ball_velocity
    if playerTurn == LEFT_PLAYER:
        left_x = WIDTH/4 - paddle_size/2
        left_y = HEIGHT - PADDLE_THICKNESS
        right_x = WIDTH/4 * 3 - paddle_size/2
        right_y = HEIGHT/4 * 3 - PADDLE_THICKNESS
        ball.x = WIDTH/4 * 3
    else:
        left_x = WIDTH/4 - paddle_size/2
        left_y = HEIGHT/4 * 3 - PADDLE_THICKNESS
        right_x = WIDTH/4 * 3 - paddle_size/2
        right_y = HEIGHT - PADDLE_THICKNESS
        ball.x = WIDTH/4

    leftPaddle.set_xy(left_x, left_y)
    rightPaddle.set_xy(right_x, right_y)
    ball.y = HEIGHT/4 * 3 - PADDLE_THICKNESS - 2 * BALL_RADIUS
    ball_angle = np.random.uniform(-25, 25)
    ball_velocity = BALL_INIT_SPEED
    ball_vector = rotation_matrix(ball_angle) @ np.array([0, -BALL_INIT_SPEED*1.5])


##
# Game loop
#
frame_cnt = 0
diff_cnt = 0
billboard_cnt = 0
text = ''
left_cmd = ''
left_pwr = 0
right_cmd = ''
right_pwr = 0

trmp_line = [-rescale_trump, 0, WIDTH, 0]
trmp_delta = 0
trmp_img = 0
trmp_visit = False

if not remote_mode:
    left_player['name'] = 'left'
    right_player['name'] = 'right'

while current_mode == MODE_PLAY:
    ##
    # Draw arena, score and player turn color
    #
    screen.fill(WHITE)
    pygame.draw.line(screen, RED, [0, HEIGHT/2], [WIDTH, HEIGHT/2], 2)
    pygame.draw.line(screen, RED, [WIDTH/2, HEIGHT/2], [WIDTH/2, HEIGHT], 2)
    pygame.draw.rect(screen, RED, (0, HEIGHT/2, WIDTH/4, HEIGHT/4), 2)
    pygame.draw.rect(screen, RED, (WIDTH/4 * 3 - 1, HEIGHT/2, WIDTH/4, HEIGHT/4), 2)
    if playerTurn == LEFT_PLAYER:
        pygame.draw.line(screen, leftPaddle.color, [int(WIDTH/16*2), 28], [int(WIDTH/16*6), 28], 3)
    else:
        pygame.draw.line(screen, rightPaddle.color, [int(WIDTH/16*10), 28], [int(WIDTH/16*14), 28], 3)
    score_text = FONT.render("{}:{}".format(str(left_player['score']), str(right_player['score'])), 1, GRAY)
    left_name_text = FONT.render(left_player['name'][:10], 1, leftPaddle.color)
    right_name_text = FONT.render(right_player['name'][:10], 1, rightPaddle.color)
    screen.blit(score_text, score_text.get_rect(centerx=WIDTH / 2))
    screen.blit(left_name_text, left_name_text.get_rect(centerx=WIDTH / 4))
    screen.blit(right_name_text, right_name_text.get_rect(centerx=WIDTH / 4*3))

    if trmp_visit:
        trmp_visit = False
        trmp_line[1] = np.random.uniform(0, HEIGHT)
        trmp_line[3] = np.random.uniform(0, HEIGHT)
        trmp_img = int(np.random.uniform(0, n_trumps))
        trmp_delta = frame_cnt

    x = frame_cnt - trmp_delta - rescale_trump
    if (x > -rescale_trump and x < WIDTH) and frame_cnt > HEIGHT:
        y = (trmp_line[3] - trmp_line[1]) / (trmp_line[2] - trmp_line[0]) * (x - trmp_line[0]) + trmp_line[1]
        screen.blit(trump_heads[trmp_img], [x, y])

    if text == '':

        try:
            text = billboard_q.get_nowait()
            billboard_cnt = frame_cnt
        except queue.Empty:
            pass

    if frame_cnt < billboard_cnt+BILLBOARD_TEXT_VISIBLE:
        billboard_text = FONT.render(text, 1, RED)
        screen.blit(billboard_text, (billboard_text.get_rect(centerx=WIDTH / 2)[0], HEIGHT/4))
    else:
        text = ''

    frame_cnt += 1

    if (left_player['name'] == '' or right_player['name'] == ''):
        wait_text = "Waiting for players..."
        billboard_text = FONT.render(wait_text, 1, RED)
        screen.blit(billboard_text, (billboard_text.get_rect(centerx=WIDTH / 2)[0], HEIGHT/5))
        pygame.display.update()
        clock.tick(FRAME_RATE)
        if frame_cnt % 5 == 0:
            with frame_mutex:
                frame = pygame.surfarray.array3d(screen).swapaxes(0, 1)
        continue

    ##
    # Handle keyboard
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            current_mode = MODE_QUIT
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_q:
                current_mode = MODE_QUIT
            elif event.key == pygame.K_m:
                muted = not muted
            elif event.key == pygame.K_k:
                left_player['ip'] = ''
                left_player['name'] = ''
                left_player['code'] = ''
                left_player['score'] = 0
                right_player = left_player.copy()


    if remote_mode:
        left_client_req = None
        try:
            left_client_req = left_ctrl_q.get_nowait()
        except queue.Empty:
            pass

        if left_client_req is not None:
            left_cmd = left_client_req['direction']
            left_pwr = 0
            if isinstance(left_client_req['speed'], float):
                if 0 <= left_client_req['speed'] <= MAX_PADDLE_POWER:
                    left_pwr = float(left_client_req['speed'])

        if left_cmd == 'up_left':
            leftPaddle.move(-PADDLE_SPEED * left_pwr, -PADDLE_SPEED * left_pwr)
        elif left_cmd == 'up_right':
            leftPaddle.move(PADDLE_SPEED * left_pwr, -PADDLE_SPEED * left_pwr)
        elif left_cmd == 'down_left':
            leftPaddle.move(-PADDLE_SPEED * left_pwr, PADDLE_SPEED * left_pwr)
        elif left_cmd == 'down_right':
            leftPaddle.move(PADDLE_SPEED * left_pwr, PADDLE_SPEED * left_pwr)
        elif left_cmd == 'up':
            leftPaddle.move(0, -PADDLE_SPEED * left_pwr)
        elif left_cmd == 'down':
            leftPaddle.move(0, PADDLE_SPEED * left_pwr)
        elif left_cmd == 'left':
            leftPaddle.move(-PADDLE_SPEED * left_pwr, 0)
        elif left_cmd == 'right':
            leftPaddle.move(PADDLE_SPEED * left_pwr, 0)

        right_client_req = None
        try:
            right_client_req = right_ctrl_q.get_nowait()
        except queue.Empty:
            pass

        if right_client_req is not None:
            right_cmd = right_client_req['direction']
            right_pwr = 0
            if isinstance(right_client_req['speed'], float):
                if 0 <= right_client_req['speed'] <= MAX_PADDLE_POWER:
                    right_pwr = float(right_client_req['speed'])


        if right_cmd == 'up_left':
            rightPaddle.move(-PADDLE_SPEED * right_pwr, -PADDLE_SPEED * right_pwr)
        elif right_cmd == 'up_right':
            rightPaddle.move(PADDLE_SPEED * right_pwr, -PADDLE_SPEED * right_pwr)
        elif right_cmd == 'down_left':
            rightPaddle.move(-PADDLE_SPEED * right_pwr, PADDLE_SPEED * right_pwr)
        elif right_cmd == 'down_right':
            rightPaddle.move(PADDLE_SPEED * right_pwr, PADDLE_SPEED * right_pwr)
        elif right_cmd == 'up':
            rightPaddle.move(0, -PADDLE_SPEED * right_pwr)
        elif right_cmd == 'down':
            rightPaddle.move(0, PADDLE_SPEED * right_pwr)
        elif right_cmd == 'left':
            rightPaddle.move(-PADDLE_SPEED * right_pwr, 0)
        elif right_cmd == 'right':
            rightPaddle.move(PADDLE_SPEED * right_pwr, 0)
    else:
        keysPressed = pygame.key.get_pressed()
        if keysPressed[pygame.K_UP] and keysPressed[pygame.K_LEFT]:
            rightPaddle.move(-PADDLE_SPEED, -PADDLE_SPEED)
        elif keysPressed[pygame.K_UP] and keysPressed[pygame.K_RIGHT]:
            rightPaddle.move(PADDLE_SPEED, -PADDLE_SPEED)
        elif keysPressed[pygame.K_DOWN] and keysPressed[pygame.K_LEFT]:
            rightPaddle.move(-PADDLE_SPEED, PADDLE_SPEED)
        elif keysPressed[pygame.K_DOWN] and keysPressed[pygame.K_RIGHT]:
            rightPaddle.move(PADDLE_SPEED, PADDLE_SPEED)
        elif keysPressed[pygame.K_UP]:
            rightPaddle.move(0, -PADDLE_SPEED)
        elif keysPressed[pygame.K_DOWN]:
            rightPaddle.move(0, PADDLE_SPEED)
        elif keysPressed[pygame.K_LEFT]:
            rightPaddle.move(-PADDLE_SPEED, 0)
        elif keysPressed[pygame.K_RIGHT]:
            rightPaddle.move(PADDLE_SPEED, 0)
        if keysPressed[pygame.K_w] and keysPressed[pygame.K_a]:
            leftPaddle.move(-PADDLE_SPEED, -PADDLE_SPEED)
        elif keysPressed[pygame.K_w] and keysPressed[pygame.K_d]:
            leftPaddle.move(PADDLE_SPEED, -PADDLE_SPEED)
        elif keysPressed[pygame.K_s] and keysPressed[pygame.K_a]:
            leftPaddle.move(-PADDLE_SPEED, PADDLE_SPEED)
        elif keysPressed[pygame.K_s] and keysPressed[pygame.K_d]:
            leftPaddle.move(PADDLE_SPEED, PADDLE_SPEED)
        elif keysPressed[pygame.K_w]:
            leftPaddle.move(0, -PADDLE_SPEED)
        elif keysPressed[pygame.K_s]:
            leftPaddle.move(0, PADDLE_SPEED)
        elif keysPressed[pygame.K_a]:
            leftPaddle.move(-PADDLE_SPEED, 0)
        elif keysPressed[pygame.K_d]:
            leftPaddle.move(PADDLE_SPEED, 0)

    ##
    # Increase difficulty
    #
    diff_cnt += 1

    if diff_cnt % (FRAME_RATE*60) == 0:
        paddle_size = paddle_size*0.8
        leftPaddle.change_width(paddle_size)
        rightPaddle.change_width(paddle_size)
        try:
            billboard_q.put_nowait("Paddle size: -20%")
        except queue.Full:
            pass

    if diff_cnt % (FRAME_RATE * 30) == 0:
        BALL_INIT_SPEED *= 1.1
        try:
            billboard_q.put_nowait("Ball velocity: +10%")
        except queue.Full:
            pass

    if diff_cnt % (FRAME_RATE * 42) == 0:
        PROB_TRUMP *= 1.2
        try:
            billboard_q.put_nowait("Trump visit: +20%")
        except queue.Full:
            pass

    if diff_cnt % (FRAME_RATE * 10) == 0:
        # A visit form Donald J. Trump? :)
        if np.random.random(1) < PROB_TRUMP:
            trmp_visit = True

    ##
    # Move ball and update scores
    #
    if ball.y > HEIGHT:
        if not muted:
            LOSE_SOUND.play()
        if playerTurn == RIGHT_PLAYER:
            left_player['score'] += 1
            try:
                billboard_q.put_nowait("{} +1".format(right_player['name']))
            except queue.Full:
                pass
            playerTurn = LEFT_PLAYER
        elif playerTurn == LEFT_PLAYER:
            right_player['score'] += 1
            try:
                billboard_q.put_nowait("{} +1".format(left_player['name']))
            except queue.Full:
                pass
            playerTurn = RIGHT_PLAYER
        reset_game(playerTurn)
        pygame.time.delay(LOSE_DELAY)
    elif ball.y < 0:
        ball_angle = 180 - ball_angle + np.random.uniform(-BALL_RANDOM_BOUNCE, BALL_RANDOM_BOUNCE)
        ball_velocity *= (1.0 - BALL_BOUNCE_DECAY)
        ball_vector = rotation_matrix(ball_angle) @ np.array([0, -ball_velocity])
        ball.y = 5
    if ball.x > WIDTH:
        ball_angle = 360 - ball_angle + np.random.uniform(-BALL_RANDOM_BOUNCE, BALL_RANDOM_BOUNCE)
        ball_velocity *= (1.0 - BALL_BOUNCE_DECAY)
        ball_vector = rotation_matrix(ball_angle) @ np.array([0, -ball_velocity])
        ball.x = WIDTH - 5
    elif ball.x < 0:
        ball_angle = 360 - ball_angle + np.random.uniform(-BALL_RANDOM_BOUNCE, BALL_RANDOM_BOUNCE)
        ball_velocity *= (1.0 - BALL_BOUNCE_DECAY)
        ball_vector = rotation_matrix(ball_angle) @ np.array([0, -ball_velocity])
        ball.x = 5


    ball_vector = ball_vector*(1.0 - BALL_DECAY_RATE)
    ball_velocity = np.linalg.norm(ball_vector)
    ball.y = ball.y + ball_vector[1]
    ball.x = ball.x + ball_vector[0]

    if ball_velocity < 0.5:
        pygame.time.delay(LOSE_DELAY)
        if ball.rect.center[1] < HEIGHT/2:
            if playerTurn is not LEFT_PLAYER:
                right_player['score'] += 1
            elif playerTurn is not RIGHT_PLAYER:
                left_player['score'] += 1
            reset_game(playerTurn)
        elif ball.rect.center[1] >= HEIGHT/2:
            if playerTurn is LEFT_PLAYER:
                right_player['score'] += 1
            elif playerTurn is RIGHT_PLAYER:
                left_player['score'] += 1
            reset_game(playerTurn)


    ##
    # Bounce ball off paddles and paddles off each other
    #
    if leftPaddle.rect.colliderect(ball.rect):
        if ball.rect.top > leftPaddle.rect.top and ball_vector[1] < 0:
            try:
                billboard_q.put_nowait("{} blocked!".format(left_player['name']))
            except queue.Full:
                pass
            if not muted:
                FAIL_SOUND.play()
            pygame.time.delay(LOSE_DELAY)
            right_player['score'] += 1
            playerTurn = LEFT_PLAYER
            reset_game(playerTurn)
        elif playerTurn == RIGHT_PLAYER:
            if not muted:
                FAIL_SOUND.play()
            pygame.time.delay(LOSE_DELAY)
            right_player['score'] += 1
            try:
                billboard_q.put_nowait("{} +1".format(right_player['name']))
            except queue.Full:
                pass
            playerTurn = LEFT_PLAYER
            reset_game(playerTurn)
        else:
            ball.y = leftPaddle.rect.top - BALL_RADIUS*4
            ball_angle = 180 - ball_angle + (ball.x - leftPaddle.rect.center[0])/(paddle_size/2)*BALL_PADLE_MAX_BOUNCE
            ball_velocity = BALL_INIT_SPEED + leftPaddle.y_velocity*np.random.uniform(0.8, 1.2)
            ball_vector = rotation_matrix(ball_angle) @ np.array([0, -ball_velocity])
            playerTurn = RIGHT_PLAYER
            if not muted:
                LEFT_SOUND.play()
    elif rightPaddle.rect.colliderect(ball.rect):
        if ball.rect.top > rightPaddle.rect.top and ball_vector[1] < 0:
            try:
                billboard_q.put_nowait("{} blocked!".format(right_player['name']))
            except queue.Full:
                pass
            if not muted:
                FAIL_SOUND.play()
            pygame.time.delay(LOSE_DELAY)
            left_player['score'] += 1
            playerTurn = RIGHT_PLAYER
            reset_game(playerTurn)
        elif playerTurn == LEFT_PLAYER:
            if not muted:
                FAIL_SOUND.play()
            pygame.time.delay(LOSE_DELAY)
            left_player['score'] += 1
            try:
                billboard_q.put_nowait("{} +1".format(left_player['name']))
            except queue.Full:
                pass
            playerTurn = RIGHT_PLAYER
            reset_game(playerTurn)
        else:
            ball.y = rightPaddle.rect.top - BALL_RADIUS*4
            ball_angle = 180 - ball_angle + (ball.x - rightPaddle.rect.center[0])/(paddle_size/2)*BALL_PADLE_MAX_BOUNCE
            ball_velocity = BALL_INIT_SPEED + rightPaddle.y_velocity*np.random.uniform(0.8, 1.2)
            ball_vector = rotation_matrix(ball_angle) @ np.array([0, -ball_velocity])
            playerTurn = LEFT_PLAYER
            if not muted:
                RIGHT_SOUND.play()
    if leftPaddle.rect.colliderect(rightPaddle):
        if is_toright(leftPaddle.rect.center, rightPaddle.rect.center):
            rightPaddle.move(BUDGE, 0)
            leftPaddle.move(-BUDGE, 0)
        if is_toleft(leftPaddle.rect.center, rightPaddle.rect.center):
            rightPaddle.move(-BUDGE, 0)
            leftPaddle.move(BUDGE, 0)
        if is_above(leftPaddle.rect.center, rightPaddle.rect.center):
            rightPaddle.move(0, -BUDGE)
            leftPaddle.move(0, BUDGE)
        if is_under(leftPaddle.rect.center, rightPaddle.rect.center):
            rightPaddle.move(0, BUDGE)
            leftPaddle.move(0, -BUDGE)

    ##
    # Draw paddles and ball
    #
    spriteGroup.draw(screen)
    spriteGroup.update()

    ##
    # Tick-tock
    #
    if frame_cnt % 5 == 0:
        with frame_mutex:
            frame = pygame.surfarray.array3d(screen).swapaxes(0, 1)

    pygame.display.update()
    clock.tick(FRAME_RATE)

    if (left_player['score'] >= 10 or right_player['score'] >= 10):
        if abs(left_player['score'] - right_player['score']) > 1:
            if left_player['score'] > right_player['score']:
                print("{} won! {} - {}".format(left_player['name'], left_player['score'], right_player['score']))
            else:
                print("{} won! {} - {}".format(right_player['name'], left_player['score'], right_player['score']))
            pygame.time.delay(LOSE_DELAY)
            pygame.quit()


