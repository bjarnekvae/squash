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
logging.getLogger('werkzeug').disabled = True

left_ctrl_q = queue.Queue(1)
right_ctrl_q = queue.Queue(1)
billboard_q = queue.Queue(1)

app = flask.Flask(__name__)
limiter = Limiter(app, key_func=get_remote_address)

frame = None
frame_mutex = threading.Lock()

left_player = dict()
left_player['ip'] = ''
left_player['name'] = ''
left_player['code'] = ''
right_player = left_player.copy()
player_mutex = threading.Lock()

server_url = '192.168.1.200'

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

        if resp['status'] is not "full":
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

        if resp['status'] is not "Not logged inn":
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
BLUE  = (0 ,0, 255)
GRAY  = (100, 100, 100)
MODE_PLAY = 1
MODE_QUIT = 0
FRAME_RATE = 120

##
# Game Sounds and delay for losing
#
LOSE_DELAY = 500
LOSE_SOUND = pygame.mixer.Sound('beep-2.wav')
FAIL_SOUND = pygame.mixer.Sound('beep-3.wav')
LEFT_SOUND = pygame.mixer.Sound('beep-7.wav')
RIGHT_SOUND = pygame.mixer.Sound('beep-8.wav')
#LEFT_SOUND = pygame.mixer.Sound('beep-21.wav') #--too quiet!
#RIGHT_SOUND = pygame.mixer.Sound('beep-22.wav')

##
# Game Vars
#
BUDGE = 5
BALL_INIT_SPEED = 3
BALL_INIT_ANGLE = 30
BALL_RANDOM_BOUNCE = 5
BALL_PADLE_MAX_BOUNCE = 40
BALL_RADIUS = 4
MAX_PADDLE_POWER = 6.01
PADDLE_SPEED = BALL_INIT_SPEED*0.7*6
PADDLE_SIZE = 70
PADDLE_THICKNESS = 8
LEFT_PLAYER = True
RIGHT_PLAYER = False
muted = False
score_left = 0
score_right = 0
playerTurn = LEFT_PLAYER
current_mode = MODE_PLAY
remote_mode = True
BILLBOARD_TEXT_VISIBLE = FRAME_RATE*1.5

def rotation_matrix(theta):
    theta *= np.pi/180
    matrix = np.array([
        [np.cos(theta), -np.sin(theta)],
        [np.sin(theta), np.cos(theta)]
    ])

    return matrix

ball_angle = BALL_INIT_ANGLE
ball_vector = rotation_matrix(ball_angle) @ np.array([0, -BALL_INIT_SPEED])

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
# Action on player score
#
def reset_game(playerTurn):
    global score_left, score_right, leftPaddle, rightPaddle, ball, ball_vector, ball_angle
    if playerTurn == RIGHT_PLAYER:
        leftPaddle.x = WIDTH/4 - PADDLE_SIZE/2
        leftPaddle.y = HEIGHT - PADDLE_THICKNESS
        rightPaddle.x = WIDTH/4 * 3 - PADDLE_SIZE/2
        rightPaddle.y = HEIGHT/4 * 3 - PADDLE_THICKNESS
        ball.x = WIDTH/4 * 3
    else:
        leftPaddle.x = WIDTH/4 - PADDLE_SIZE/2
        leftPaddle.y = HEIGHT/4 * 3 - PADDLE_THICKNESS
        rightPaddle.x = WIDTH/4 * 3 - PADDLE_SIZE/2
        rightPaddle.y = HEIGHT - PADDLE_THICKNESS
        ball.x = WIDTH/4
    ball.y = HEIGHT/4 * 3 - PADDLE_THICKNESS - 2 * BALL_RADIUS
    ball_angle = np.random.uniform(-20, 20)
    ball_vector = rotation_matrix(ball_angle) @ np.array([0, -BALL_INIT_SPEED])

##
# Game Objects
#

#f_brightness = thr_lightCtrl.prev + 0.1/led_tau * (brightness - thr_lightCtrl.prev)
#thr_lightCtrl.prev = f_brightness

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

    def move(self, moveX, moveY):
        self.y = self.y + moveY
        self.x = self.x + moveX

    def update(self):
        if self.y < self.maxY/2:
            self.y = self.maxY/2
        elif self.y > self.maxY:
            self.y = self.maxY
        if self.x < 0:
            self.x = 0
        elif self.x > self.maxX:
            self.x = self.maxX
        self.rect.topleft = [int(self.x), int(self.y)]

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
# Game loop
#
frame_cnt = 0
billboard_cnt = 0
text = ''
while current_mode == MODE_PLAY:
    ##
    # Draw arena, score and player turn color
    #
    screen.fill(WHITE)
    pygame.draw.line(screen, RED, [0, HEIGHT/2], [WIDTH, HEIGHT/2], 2)
    pygame.draw.line(screen, RED, [WIDTH/2, HEIGHT/2], [WIDTH/2, HEIGHT], 2)
    pygame.draw.rect(screen, RED, (0, HEIGHT/2, WIDTH/4, HEIGHT/4), 2)
    pygame.draw.rect(screen, RED, (WIDTH/4 * 3 - 1, HEIGHT/2, WIDTH/4, HEIGHT/4), 2)
    if playerTurn == RIGHT_PLAYER:
        pygame.draw.line(screen, leftPaddle.color, [int(WIDTH/16*2), 28], [int(WIDTH/16*6), 28], 3)
    else:
        pygame.draw.line(screen, rightPaddle.color, [int(WIDTH/16*10), 28], [int(WIDTH/16*14), 28], 3)
    score_text = FONT.render("{}:{}".format(str(score_left), str(score_right)), 1, GRAY)
    left_name_text = FONT.render(left_player['name'][:10], 1, leftPaddle.color)
    right_name_text = FONT.render(right_player['name'][:10], 1, rightPaddle.color)
    screen.blit(score_text, score_text.get_rect(centerx=WIDTH / 2))
    screen.blit(left_name_text, left_name_text.get_rect(centerx=WIDTH / 4))
    screen.blit(right_name_text, right_name_text.get_rect(centerx=WIDTH / 4*3))

    try:
        text = billboard_q.get_nowait()
        billboard_cnt = frame_cnt
        print(text)
    except queue.Empty:
        pass

    if frame_cnt < billboard_cnt+BILLBOARD_TEXT_VISIBLE:
        billboard_text = FONT.render(text, 1, RED)
        screen.blit(billboard_text, (billboard_text.get_rect(centerx=WIDTH / 2)[0], HEIGHT/4))
    else:
        text = ''

    frame_cnt += 1

    if (left_player['name'] == '' or right_player['name'] == ''): ## TODO add remote mode exception
        wait_text = "Wating for players..."
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
        # TODO remove this
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            current_mode = MODE_QUIT
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_q:
                current_mode = MODE_QUIT
            elif event.key == pygame.K_m:
                muted = not muted

    if remote_mode:
        left_client_req = None
        try:
            left_client_req = left_ctrl_q.get_nowait()
        except queue.Empty:
            pass

        if left_client_req is not None:
            left_cmd = left_client_req['cmd']
            left_pwr = 0
            if isinstance(left_client_req['pwr'], int):
                if 0 <= left_client_req['pwr'] <= MAX_PADDLE_POWER:
                    left_pwr = int(left_client_req['pwr'])
                else:
                    print("not in range")
            else:
                print("not float")
        else:
            left_cmd = ''
            left_pwr = 0

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
        elif left_cmd == 'up_left':
            leftPaddle.move(-PADDLE_SPEED * left_pwr, 0)
        elif left_cmd == 'down_right':
            leftPaddle.move(PADDLE_SPEED * left_pwr, 0)

        right_client_req = None
        try:
            right_client_req = right_ctrl_q.get_nowait()
        except queue.Empty:
            pass

        if right_client_req is not None:
            right_cmd = right_client_req['cmd']
            right_pwr = 0
            if isinstance(right_client_req['pwr'], float) or isinstance(right_client_req['pwr'], int):
                if 0 <= right_client_req['pwr'] <= MAX_PADDLE_POWER:
                    right_pwr = int(right_client_req['pwr'])
        else:
            right_cmd = ''
            right_pwr = 0

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
        elif right_cmd == 'up_left':
            rightPaddle.move(-PADDLE_SPEED * right_pwr, 0)
        elif right_cmd == 'down_right':
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
    # Move ball and update scores
    #
    if ball.y > HEIGHT:
        if not muted:
            LOSE_SOUND.play()
        if playerTurn == RIGHT_PLAYER:
            score_right += 1
            try:
                billboard_q.put_nowait("{} +1".format(right_player['name']))
                print("ball out")
            except queue.Full:
                pass
        elif playerTurn == LEFT_PLAYER:
            score_left += 1
            try:
                billboard_q.put_nowait("{} +1".format(left_player['name']))
                print("ball out")
            except queue.Full:
                pass
        playerTurn = not playerTurn
        reset_game(playerTurn)
        #pygame.time.delay(LOSE_DELAY)
    elif ball.y < 0:
        ball_angle = 180 - ball_angle + np.random.uniform(-BALL_RANDOM_BOUNCE, BALL_RANDOM_BOUNCE)
        ball_vector = rotation_matrix(ball_angle) @ np.array([0, -BALL_INIT_SPEED])
    if ball.x > WIDTH:
        ball_angle = 360 - ball_angle + np.random.uniform(-BALL_RANDOM_BOUNCE, BALL_RANDOM_BOUNCE)
        ball_vector = rotation_matrix(ball_angle) @ np.array([0, -BALL_INIT_SPEED])
    elif ball.x < 0:
        ball_angle = 360 - ball_angle + np.random.uniform(-BALL_RANDOM_BOUNCE, BALL_RANDOM_BOUNCE)
        ball_vector = rotation_matrix(ball_angle) @ np.array([0, -BALL_INIT_SPEED])

    ball.y = ball.y + ball_vector[1]
    ball.x = ball.x + ball_vector[0]
    ##
    # Bounce ball off paddles and paddles off each other
    #
    if leftPaddle.rect.colliderect(ball.rect):
        if ball.y > leftPaddle.rect.top:
            try:
                billboard_q.put_nowait("{} blocked!".format(left_player['name']))
                print("block!")
            except queue.Full:
                pass
            if not muted:
                FAIL_SOUND.play()
            #pygame.time.delay(LOSE_DELAY)
            score_right += 1
            playerTurn = RIGHT_PLAYER
            reset_game(playerTurn)
        elif playerTurn == LEFT_PLAYER:
            if not muted:
                FAIL_SOUND.play()
            #pygame.time.delay(LOSE_DELAY)
            score_right += 1
            try:
                billboard_q.put_nowait("{} +1".format(right_player['name']))
                print("not your turn!")
            except queue.Full:
                pass
            playerTurn = RIGHT_PLAYER
            reset_game(playerTurn)
        else:
            ball.y = leftPaddle.y - 2 * BALL_RADIUS
            ball_angle = 180 - ball_angle + (ball.x - leftPaddle.rect.center[0])/(PADDLE_SIZE/2)*BALL_PADLE_MAX_BOUNCE
            ball_vector = rotation_matrix(ball_angle) @ np.array([0, -BALL_INIT_SPEED])
            playerTurn = not playerTurn
            if not muted:
                LEFT_SOUND.play()
    elif rightPaddle.rect.colliderect(ball.rect):
        if ball.y > rightPaddle.rect.top:
            try:
                billboard_q.put_nowait("{} blocked!".format(right_player['name']))
                print("block!")
            except queue.Full:
                pass
            if not muted:
                FAIL_SOUND.play()
            #pygame.time.delay(LOSE_DELAY)
            score_left += 1
            playerTurn = LEFT_PLAYER
            reset_game(playerTurn)

        elif playerTurn == RIGHT_PLAYER:
            if not muted:
                FAIL_SOUND.play()
            #pygame.time.delay(LOSE_DELAY)
            score_left += 1
            try:
                billboard_q.put_nowait("{} +1".format(left_player['name']))
                print("not your turn!")
            except queue.Full:
                pass
            playerTurn = LEFT_SOUND
            reset_game(playerTurn)

        else:
            ball.y = rightPaddle.y - 2 * BALL_RADIUS
            ball_angle = 180 - ball_angle + (ball.x - rightPaddle.rect.center[0])/(PADDLE_SIZE/2)*BALL_PADLE_MAX_BOUNCE
            ball_vector = rotation_matrix(ball_angle) @ np.array([0, -BALL_INIT_SPEED])
            playerTurn = not playerTurn
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

pygame.quit()
