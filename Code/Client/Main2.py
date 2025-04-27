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
@app.route('/stop', methods=['POST'])
@app.route('/move', methods=['POST'])
@app.route('/move/<string:gait>/<string:x>/<string:y>/<string:angle>', methods=['POST'])
def move(gait=None, x=None, y=None, angle=None):
    if gait is None:
        gait = '1'
        x = '0'
        y = '0'
        angle = '0'
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
    command = cmd.CMD_SERVOPOWER + f'#0\n'
    g.service.client.send_data(command)
    return jsonify({'status': 'Servo off'}), 200


# Endpoint to turn servo on
@app.route('/servopower/on', methods=['POST'])
def stand():
    command = cmd.CMD_SERVOPOWER + f'#1\n'
    g.service.client.send_data(command)
    return jsonify({'status': 'Servo on'}), 200


# Endpoint to turn head vertically
@app.route('/head/vertical', methods=['POST'])
@app.route('/head/vertical/<string:angle>', methods=['POST'])
def head_vertical(angle=None):
    if angle is None:
        angle = '90'
    command = cmd.CMD_HEAD + f'#0#{angle}\n'
    g.service.client.send_data(command)
    return jsonify({'status': 'Head vertical angle set', 'angle': int(angle)}), 200


# Endpoint to turn head horizontally
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


# Endpoint for power
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


# Endpoint to set position
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


# Endpoint to set attitude (-20 <= values <= 20; 0 by default)
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


# Endpoint to set LED color
@app.route('/led/color', methods=['POST'])
@app.route('/led/color/<string:red>/<string:green>/<string:blue>', methods=['POST'])
def set_led_color(red=None, green=None, blue=None):
    if red is None:
        red = '255'
        green = '255'
        blue = '255'
    command = cmd.CMD_LED + f'#255#{red}#{green}#{blue}\n'
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
