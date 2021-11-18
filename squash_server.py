#License MIT 2017 Ahmad Retha

import os
import pygame
import pygame.mixer
import threading
import queue
import json
import flask
from PIL import Image
from io import BytesIO
import logging
logging.getLogger('werkzeug').disabled = True

left_ctrl_q = queue.Queue(1)
right_ctrl_q = queue.Queue(1)

app = flask.Flask(__name__)
frame = None
frame_mutex = threading.Lock()

left_player = dict()
left_player['ip'] = ''
left_player['name'] = ''
left_player['code'] = ''
right_player = left_player.copy()
player_mutex = threading.Lock()


@app.route('/get_frame', methods=['GET'])
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

    return flask.jsonify(resp)

@app.route('/logout', methods=['PUT'])
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

    return flask.jsonify(resp)


threading.Thread(target=lambda: app.run(host='localhost', port=6010, threaded=True), daemon=True).start()


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
FRAME_RATE = 30

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
BALL_SPEED = 3
BALL_RADIUS = 4
PADDLE_SPEED = 3
PADDLE_SIZE = 70
PADDLE_THICKNESS = 4
LEFT_PLAYER = True
RIGHT_PLAYER = False
muted = False
speed_x = BALL_SPEED
speed_y = -BALL_SPEED
score_left = 0
score_right = 0
playerTurn = LEFT_PLAYER
current_mode = MODE_PLAY

##
# Action on player score
#
def score():
    global playerTurn, score_left, score_right, leftPaddle, rightPaddle, ball, speed_y
    if playerTurn == LEFT_PLAYER:
        score_left += 1                
        leftPaddle.x = WIDTH/4 - PADDLE_SIZE/2
        leftPaddle.y = HEIGHT - PADDLE_THICKNESS
        rightPaddle.x = WIDTH/4 * 3 - PADDLE_SIZE/2
        rightPaddle.y = HEIGHT/4 * 3 - PADDLE_THICKNESS
        ball.x = WIDTH/4 * 3
    else:
        score_right += 1
        leftPaddle.x = WIDTH/4 - PADDLE_SIZE/2
        leftPaddle.y = HEIGHT/4 * 3 - PADDLE_THICKNESS
        rightPaddle.x = WIDTH/4 * 3 - PADDLE_SIZE/2
        rightPaddle.y = HEIGHT - PADDLE_THICKNESS
        ball.x = WIDTH/4
    ball.y = HEIGHT/4 * 3 - PADDLE_THICKNESS - 2 * BALL_RADIUS
    speed_y = -abs(speed_y)
    return not playerTurn

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
        self.rect.topleft = [self.x, self.y]

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
while current_mode == MODE_PLAY:
    ##
    # Handle keyboard
    #
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            current_mode = MODE_QUIT
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_q:
                current_mode = MODE_QUIT
            elif event.key == pygame.K_m:
                muted = not muted

    left_client_req = None
    try:
        left_client_req = left_ctrl_q.get_nowait()
    except queue.Empty:
        pass

    if left_client_req is not None:
        left_cmd = left_client_req['cmd']
    else:
        left_cmd = ''

    if left_cmd == 'up_left':
        leftPaddle.move(-PADDLE_SPEED, -PADDLE_SPEED)
    elif left_cmd == 'up_right':
        leftPaddle.move(PADDLE_SPEED, -PADDLE_SPEED)
    elif left_cmd == 'down_left':
        leftPaddle.move(-PADDLE_SPEED, PADDLE_SPEED)
    elif left_cmd == 'down_right':
        leftPaddle.move(PADDLE_SPEED, PADDLE_SPEED)
    elif left_cmd == 'up':
        leftPaddle.move(0, -PADDLE_SPEED)
    elif left_cmd == 'down':
        leftPaddle.move(0, PADDLE_SPEED)
    elif left_cmd == 'up_left':
        leftPaddle.move(-PADDLE_SPEED, 0)
    elif left_cmd == 'down_right':
        leftPaddle.move(PADDLE_SPEED, 0)

    right_client_req = None
    try:
        right_client_req = right_ctrl_q.get_nowait()
    except queue.Empty:
        pass

    if right_client_req is not None:
        right_cmd = right_client_req['cmd']
    else:
        right_cmd = ''

    if right_cmd == 'up_left':
        rightPaddle.move(-PADDLE_SPEED, -PADDLE_SPEED)
    elif right_cmd == 'up_right':
        rightPaddle.move(PADDLE_SPEED, -PADDLE_SPEED)
    elif right_cmd == 'down_left':
        rightPaddle.move(-PADDLE_SPEED, PADDLE_SPEED)
    elif right_cmd == 'down_right':
        rightPaddle.move(PADDLE_SPEED, PADDLE_SPEED)
    elif right_cmd == 'up':
        rightPaddle.move(0, -PADDLE_SPEED)
    elif right_cmd == 'down':
        rightPaddle.move(0, PADDLE_SPEED)
    elif right_cmd == 'up_left':
        rightPaddle.move(-PADDLE_SPEED, 0)
    elif right_cmd == 'down_right':
        rightPaddle.move(PADDLE_SPEED, 0)

    ##
    # Draw arena, score and player turn color
    #
    screen.fill(WHITE)
    pygame.draw.line(screen, RED, [0, HEIGHT/2], [WIDTH, HEIGHT/2], 2)
    pygame.draw.line(screen, RED, [WIDTH/2, HEIGHT/2], [WIDTH/2, HEIGHT], 2)
    pygame.draw.rect(screen, RED, (0, HEIGHT/2, WIDTH/4, HEIGHT/4), 2)
    pygame.draw.rect(screen, RED, (WIDTH/4 * 3 - 1, HEIGHT/2, WIDTH/4, HEIGHT/4), 2)
    if playerTurn == RIGHT_PLAYER:
        pygame.draw.circle(screen, leftPaddle.color, [int(WIDTH/4), 20], 15)
    else:
        pygame.draw.circle(screen, rightPaddle.color, [int(WIDTH/4) * 3, 20], 15)
    text = FONT.render("%s:%s" % (str(score_left), str(score_right)), 1, GRAY)
    textpos = text.get_rect(centerx=WIDTH/2)
    screen.blit(text, textpos)

    ##
    # Move ball and update scores
    #
    if ball.y > HEIGHT:
        if not muted:
            LOSE_SOUND.play()
        playerTurn = score()
        pygame.time.delay(LOSE_DELAY)
    elif ball.y < 0:
        speed_y = -speed_y
    if ball.x > WIDTH:
        speed_x = -speed_x
    elif ball.x < 0:
        speed_x = abs(speed_x)
    ball.y = ball.y + speed_y
    ball.x = ball.x + speed_x

    ##
    # Bounce ball off paddles and paddles off each other
    #
    if leftPaddle.rect.colliderect(ball.rect):
        if playerTurn == LEFT_PLAYER:
            if not muted:
                FAIL_SOUND.play()
            playerTurn = score()
            pygame.time.delay(LOSE_DELAY)
        else:
            ball.y = leftPaddle.y - 2 * BALL_RADIUS
            speed_y = -speed_y
            playerTurn = not playerTurn
            if not muted:
                LEFT_SOUND.play()
    elif rightPaddle.rect.colliderect(ball.rect):
        if playerTurn == RIGHT_PLAYER:
            if not muted:
                FAIL_SOUND.play()
                pygame.time.delay(LOSE_DELAY)
            playerTurn = score()
        else:
            ball.y = rightPaddle.y - 2 * BALL_RADIUS
            speed_y = -speed_y
            playerTurn = not playerTurn
            if not muted:
                RIGHT_SOUND.play()
    if leftPaddle.rect.colliderect(rightPaddle):
        if leftPaddle.rect.bottom >= rightPaddle.rect.top:
            leftPaddle.move(0, -BUDGE)
            rightPaddle.move(0, BUDGE)
        elif rightPaddle.rect.bottom >= leftPaddle.rect.top:
            rightPaddle.move(0, -BUDGE)
            leftPaddle.move(0, BUDGE)
        elif leftPaddle.rect.right >= rightPaddle.rect.left:
            leftPaddle.move(-BUDGE, 0)
            rightPaddle.move(BUDGE, 0)
        elif rightPaddle.rect.right >= leftPaddle.rect.left:
            rightPaddle.move(-BUDGE, 0)
            leftPaddle.move(BUDGE, 0)

    ##
    # Draw paddles and ball
    #
    spriteGroup.draw(screen)
    spriteGroup.update()

    ##
    # Tick-tock
    #
    with frame_mutex:
        frame = pygame.surfarray.array3d(screen).swapaxes(0, 1)

    pygame.display.update()
    clock.tick(FRAME_RATE)

pygame.quit()
