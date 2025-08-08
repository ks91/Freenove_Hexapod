# -*- coding: utf-8 -*-
"""
Licensed under CC BY-NC-SA 3.0

Derived from Freenove by Kenji Saito (ks91), 2025.

A version of Main.py that takes input from REST API instead of
GUI events. It is assumed that the robot has been calibrated using
the original Main.py client software.
"""

from flask import Flask, request, jsonify, g, send_file
from Client import *
import threading
import time


DEFAULT_MOVE_SPEED = '8'

FILENAME_IMAGE = 'image.jpg'

PORT_INSTRUCTIONS = 5002
PORT_VIDEO = 8002

class ClientService:
    def __init__(self):
        self.client = Client()
        self.client.move_speed = DEFAULT_MOVE_SPEED
        
        try:
            with open('IP.txt', 'r') as file:
                self.ip_address = file.readline().strip()
                
        except FileNotFoundError:
            self.ip_address = '127.0.0.1'
            
        self.video_thread = None
        self.video_timer_thread = None
        self.instruction_thread = None
        self.connected = False
        self.looking_for_ball = False
        self.tracking_ball = False
        self.distance = '0cm'
        self.power_value = [0, 0]

    def receive_instruction(self):
        try:
            self.client.client_socket1.connect((self.ip_address, PORT_INSTRUCTIONS))
            self.client.tcp_flag=True
            print ("Connecttion Successful !")

        except Exception as e:
            print ("Connect to server Faild!: Server IP is right? Server is opend?")
            self.client.tcp_flag=False
            return

        while self.client.tcp_flag:
            try:
                alldata=self.client.receive_data()
            except:
                self.client.tcp_flag=False
                break
            #print(alldata)
            if alldata=='':
                break
            else:
                cmdArray=alldata.split('\n')
                #print(cmdArray)
                if cmdArray[-1] !="":
                    cmdArray==cmdArray[:-1]
            for oneCmd in cmdArray:
                data=oneCmd.split("#")
                print(data)
                if data=="":
                    self.client.tcp_flag=False
                    break
                elif data[0]==cmd.CMD_SONIC:
                    self.distance = f'{data[1]}cm'
                    #print('Obstacle:',data[1])
                elif data[0]==cmd.CMD_POWER:
                    try:
                        if len(data)==3:
                            self.power_value[0] = data[1]
                            self.power_value[1] = data[2]
                    except Exception as e:
                        print(e)


    # Function to enable image input periodically
    def refresh_image(self):
        while self.connected:
            if self.client.video_flag == False:
                self.client.video_flag = True
            time.sleep(0.1)
            
            # ball tracking adopted and modified from
            # https://github.com/Freenove/Freenove_Robot_Dog_Kit_for_Raspberry_Pi
            if self.looking_for_ball:
                MIN_RADIUS=7
                #red
                THRESHOLD_LOW = (0, 180, 180)
                THRESHOLD_HIGH = (5,255,255)

                img_filter = cv2.GaussianBlur(self.client.image.copy(), (3, 3), 0)
                img_filter = cv2.cvtColor(img_filter, cv2.COLOR_BGR2HSV)
                img_binary = cv2.inRange(img_filter.copy(), THRESHOLD_LOW, THRESHOLD_HIGH)
                img_binary = cv2.dilate(img_binary, None, iterations = 1)
                contours = cv2.findContours(img_binary.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2]
                center = None
                radius = 0
                if len(contours) > 0:
                    c = max(contours, key=cv2.contourArea)
                    ((x, y), radius) = cv2.minEnclosingCircle(c)
                    M = cv2.moments(c)
                    if M["m00"] > 0:
                        center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))
                        if radius < MIN_RADIUS:
                            center = None
                
                speed = self.client.move_speed
                self.tracking_ball = True
                if center != None:
                    cv2.circle(self.client.image, center, int(radius), (0, 255, 0))
                    D=round(2700/(2*radius))  #CM
                    x=self.client.pid.PID_compute(center[0])
                    d=self.client.pid.PID_compute(D)
                    print(f'd={d}, x={x}, r={radius}')
                    if radius>7:
                        angle = 0
                        if x < 180:
                            angle = -4 if x < 180 else -2
                        elif x > 310:
                            angle = 4 if x > 340 else 2
                        if d < 45: # backward
                                step = -8 if d < 35 else -4
                                command=cmd.CMD_MOVE + f'#1#0#{step}#{speed}#{angle}\n'
                                self.client.send_data(command)
                        elif d > 70: # forward
                                step = 8 if d > 80 else 4
                                command=cmd.CMD_MOVE + f'#1#0#{step}#{speed}#{angle}\n'
                                self.client.send_data(command)
                        else:
                            if angle != 0:
                                command=cmd.CMD_MOVE + f'#1#0#-1#{speed}#{angle}\n'
                                self.client.send_data(command)
                            else:
                                command=cmd.CMD_MOVE + f'#1#0#0#{speed}#0\n'
                                self.client.send_data(command)
                                self.tracking_ball = False
                else:
                    command=cmd.CMD_MOVE + f'#1#0#0#{speed}#0\n'
                    self.client.send_data(command)
                    #print (command)

def abort_by_bad_content_type(content_type):
    abort(400, description='Content-Type {0} is not expected'.format(
            content_type))


def abort_by_bad_json_format():
    abort(400, description='Bad JSON format')


def abort_by_missing_param(param):
    abort(400, description='{0} is missing'.format(param))


app = Flask(__name__)
service = ClientService()


@app.after_request
def after_request(response):
    return response


@app.before_request
def before_request():
    global service
    g.service = service


# Endpoint to connect
@app.route('/connect', methods=['POST'])
def connect_robot():
    if not g.service.connected:
        g.service.client.turn_on_client(g.service.ip_address)
        g.service.connected = True

        # Start video and instruction threads
        g.service.video_thread = threading.Thread(
                target=g.service.client.receiving_video,
                args=(g.service.ip_address,))
        g.service.video_timer_thread = threading.Thread(
                target=g.service.refresh_image)
        g.service.instruction_thread = threading.Thread(
                target=g.service.receive_instruction)
        g.service.video_thread.start()
        g.service.video_timer_thread.start()
        g.service.instruction_thread.start()

        return jsonify({'status': 'Connected'}), 200


# Endpoint to disconnect
@app.route('/disconnect', methods=['POST'])
def disconnect_robot():
    if g.service.connected:
        try:
            g.service.client.client_socket1.close()
            g.service.client.tcp_flag = False

        except Exception as e:
            print("Error disconnecting:", e)

        g.service.connected = False
        g.service.client.turn_off_client()

        return jsonify({'status': 'Disconnected'}), 200


# Endpoint to adjust speed (2 <= speed <= 10; 8 by default)
@app.route('/speed', methods=['POST'])
@app.route('/speed/<string:value>', methods=['POST'])
def adjust_speed(value=None):
    if value is None:
        value = DEFAULT_MOVE_SPEED
    g.service.client.move_speed = value
    return jsonify({'status': 'Speed set', 'speed': int(value)}), 200


# Endpoint to get the speed
@app.route('/speed', methods=['GET'])
def get_speed():
    return jsonify({'speed': int(g.service.client.move_speed)}), 200


# Endpoint to move or stop
# gait : 1 - three legs at a time, 2 - one leg at a time
# x and y : step length : should be around -30 to 30 (30 is quite fast moving)
# angle : should be around -20 to 20 (20 is quite fast moving)
# if both x and y are 0, it stops, so just to turn (counter)clockwise, x or y needs to be 1
@app.route('/stop', methods=['POST'])
@app.route('/move', methods=['POST'])
@app.route('/move/<string:gait>/<string:x>/<string:y>/<string:angle>', methods=['POST'])
def move(gait=None, x=None, y=None, angle=None):
    if gait is None:
        gait = '1'
        x = '0'
        y = '0'
        angle = '0'
    g.service.looking_for_ball = False
    speed = g.service.client.move_speed
    command = cmd.CMD_MOVE + f'#{gait}#{x}#{y}#{speed}#{angle}\n'
    g.service.client.send_data(command)
    return jsonify({
        'status': 'Moving',
        'gait': int(gait),
        'x': int(x),
        'y': int(y),
        'speed': int(speed),
        'angle': int(angle)
    }), 200


# Endpoint to turn servo off
@app.route('/servopower/off', methods=['POST'])
def relax():
    g.service.looking_for_ball = False
    command = cmd.CMD_SERVOPOWER + f'#0\n'
    g.service.client.send_data(command)
    return jsonify({'status': 'Servo off'}), 200


# Endpoint to turn servo on
@app.route('/servopower/on', methods=['POST'])
def stand():
    command = cmd.CMD_SERVOPOWER + f'#1\n'
    g.service.client.send_data(command)
    return jsonify({'status': 'Servo on'}), 200


# Endpoint to turn head vertically (60 <= angle <= 180; 90 (straight) by default)
@app.route('/head/vertical', methods=['POST'])
@app.route('/head/vertical/<string:angle>', methods=['POST'])
def head_vertical(angle=None):
    if angle is None:
        angle = '90'
    command = cmd.CMD_HEAD + f'#0#{angle}\n'
    g.service.client.send_data(command)
    return jsonify({'status': 'Head vertical angle set', 'angle': int(angle)}), 200


# Endpoint to turn head horizontally (0 <= angle <= 180; 90 (straight) by default)
@app.route('/head/horizontal', methods=['POST'])
@app.route('/head/horizontal/<string:angle>', methods=['POST'])
def head_horizontal(angle=None):
    if angle is None:
        angle = '90'
    command = cmd.CMD_HEAD + f'#1#{angle}\n'
    g.service.client.send_data(command)
    return jsonify({'status': 'Head horizontal angle set', 'angle': int(angle)}), 200


# Endpoint for buzzer (state : '1' to turn on, '0' to turn off)
@app.route('/buzzer', methods=['POST'])
@app.route('/buzzer/<string:state>', methods=['POST'])
def buzzer(state=None):
    if state is None:
        state = '0'
    command = cmd.CMD_BUZZER + f'#{state}\n'
    g.service.client.send_data(command)
    return jsonify({'status': 'Buzzer state changed', 'state': state}), 200


# Endpoint for balance (state : '1' to enable, '0' to disable)
@app.route('/balance', methods=['POST'])
@app.route('/balance/<string:state>', methods=['POST'])
def balance(state=None):
    if state is None:
        state = '0'
    command = cmd.CMD_BALANCE + f'#{state}\n'
    g.service.client.send_data(command)
    return jsonify({'status': 'Balance state changed', 'state': state}), 200


# Endpoint for sonic
@app.route('/sonic', methods=['GET'])
def sonic():
    command = cmd.CMD_SONIC + '\n'
    g.service.client.send_data(command)
    time.sleep(0.1)
    distance = g.service.distance
    return jsonify({'status': 'Sonic data requested', 'distance': distance}), 200


# Endpoint for power (if they are full, more than 8V)
@app.route('/power', methods=['GET'])
def power():
    command = cmd.CMD_POWER + '\n'
    g.service.client.send_data(command)
    time.sleep(0.1)
    power_servo = g.service.power_value[0] + 'V'
    power_rasp = g.service.power_value[1] + 'V'
    return jsonify({
        'status': 'Power data requested',
        'power_servo': power_servo,
        'power_rasp': power_rasp
    }), 200


# Endpoint to set position (should be around -10 <= values <= 10; 0 by default)
@app.route('/position', methods=['POST'])
@app.route('/position/<string:x>/<string:y>/<string:z>', methods=['POST'])
def set_height(x=None, y=None, z=None):
    if x is None:
        x = '0'
        y = '0'
        z = '0'
    command = cmd.CMD_POSITION + f'#{x}#{y}#{z}\n'
    g.service.client.send_data(command)
    return jsonify({
        'status': 'Position set',
        'x': x,
        'y': y,
        'z': z
    }), 200


# Endpoint to set attitude (should be around -10 <= values <= 10; 0 by default)
@app.route('/attitude', methods=['POST'])
@app.route('/attitude/<string:roll>/<string:pitch>/<string:yaw>', methods=['POST'])
def set_attitude(roll=None, pitch=None, yaw=None):
    if roll is None:
        roll = '0'
        pitch = '0'
        yaw = '0'
    command = cmd.CMD_ATTITUDE + f'#{roll}#{pitch}#{yaw}\n'
    g.service.client.send_data(command)
    return jsonify({
        'status': 'Attitude set',
        'roll': int(roll),
        'pitch': int(pitch),
        'yaw': int(yaw)
    }), 200


# Endpoint to set LED mode (0 : off, 1 to 5)
@app.route('/led/mode', methods=['POST'])
@app.route('/led/mode/<string:value>', methods=['POST'])
def set_led_mode(value=None):
    if value is None:
        value = '0'
    command = cmd.CMD_LED_MOD + f'#{value}\n'
    g.service.client.send_data(command)
    return jsonify({'status': 'LED mode set', 'mode': int(value)}), 200


# Endpoint to set LED color (200 is too bright)
@app.route('/led/color', methods=['POST'])
@app.route('/led/color/<string:red>/<string:green>/<string:blue>', methods=['POST'])
def set_led_color(red=None, green=None, blue=None):
    if red is None:
        red = '255'
        green = '255'
        blue = '255'
    command = cmd.CMD_LED + f'#{red}#{green}#{blue}\n'
    g.service.client.send_data(command)
    return jsonify({
        'status': 'LED color set',
        'r': int(red),
        'g': int(green),
        'b': int(blue)
    }), 200


# Endpoint to get image from camera
@app.route('/camera/image', methods=['GET'])
def get_image():
    cv2.imwrite(FILENAME_IMAGE, g.service.client.image)
    return send_file(FILENAME_IMAGE, mimetype='image/jpeg')


# Endpoint to enter ball tracking
@app.route('/ball/start', methods=['POST'])
def start_ball_tracking():
    command = cmd.CMD_HEAD + '#0#90\n'
    g.service.client.send_data(command)
    command = cmd.CMD_HEAD + '#1#90\n'
    g.service.client.send_data(command)
    g.service.looking_for_ball = True
    return jsonify({'status': 'Ball-tracking started'}), 200


# Endpoint to exit ball tracking
@app.route('/ball/stop', methods=['POST'])
def stop_ball_tracking():
    g.service.looking_for_ball = False
    time.sleep(0.2)
    command=cmd.CMD_MOVE + f'#1#0#0#{g.service.client.move_speed}#0\n'
    g.service.client.send_data(command)
    return jsonify({'status': 'Ball-tracking stopped'}), 200


# Endpoint to check the state of ball tracking
@app.route('/ball/state', methods=['GET'])
def get_ball_tracking_state():
    state = ''
    if g.service.looking_for_ball:
        if g.service.tracking_ball:
            state = 'ongoing'
        else:
            state = 'completed'
    else:
        state = 'not tracking'
    return jsonify({'status': state}), 200


@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(409)
def error_handler(e):
    return jsonify({'error': {
        'code': e.code,
        'name': e.name,
        'description': e.description,
    }}), e.code

@app.errorhandler(ValueError)
@app.errorhandler(KeyError)
def error_handler(e):
    return jsonify({'error': {
        'code': 400,
        'name': 'Bad Request',
        'description': str(e),
    }}), 400


# Run the Flask app
if __name__ == '__main__':
    app.run(host='0.0.0.0', threaded=True)


# end of Main2.py
