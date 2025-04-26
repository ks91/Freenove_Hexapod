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
                    self.label_sonic.setText('Obstacle:'+data[1]+'cm')
                    #print('Obstacle:',data[1])
                elif data[0]==cmd.CMD_POWER:
                    try:
                        if len(data)==3:
                            self.power_value[0] = data[1]
                            self.power_value[1] = data[2]
                            #self.power_value[0] = self.restriction(round((float(data[1]) - 5.00) / 3.40 * 100),0,100)
                            #self.power_value[1] = self.restriction(round((float(data[2]) - 7.00) / 1.40 * 100),0,100)
                            #print('Power：',power_value1,power_value2)
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


# Endpoint to move
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
    return jsonify({'status': f'Moving [{gait}][{x}][{y}][{angle}]', 'speed': int(speed)}), 200


# Endpoint for relax
@app.route('/relax', methods=['POST'])
def relax():
    command = cmd.CMD_SERVOPOWER + f'#0\n'
    g.service.client.send_data(command)
    return jsonify({'status': 'Relaxed'}), 200


# Endpoint to stand
@app.route('/stand', methods=['POST'])
def stand():
    command = cmd.CMD_SERVOPOWER + f'#1\n'
    g.service.client.send_data(command)
    return jsonify({'status': 'Stood'}), 200


# Endpoint to turn head vertically
@app.route('/head/vertical', methods=['POST'])
@app.route('/head/vertical/<string:angle>', methods=['POST'])
def head_vertical(angle=None):
    if angle is None:
        angle = '0'
    command = cmd.CMD_HEAD + f'#0#{angle}\n'
    g.service.client.send_data(command)
    return jsonify({'status': 'Head vertical angle set', 'angle': int(angle)}), 200


# Endpoint to turn head horizontally
@app.route('/head/horizontal', methods=['POST'])
@app.route('/head/horizontal/<string:angle>', methods=['POST'])
def head_horizontal(angle=None):
    if angle is None:
        angle = '0'
    command = cmd.CMD_HEAD + f'#1#{angle}\n'
    g.service.client.send_data(command)
    return jsonify({'status': 'Head horizontal angle set', 'angle': int(angle)}), 200


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
