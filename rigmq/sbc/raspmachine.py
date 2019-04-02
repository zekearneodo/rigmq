# In the paris version, pyaudio is not necessary,
# only an audio presentation will happen.
# note that if WavPlayer wants to be used, pyaudio needs to be set up
#import pyaudio
import wave
import time
import sys
import os
import zmq
import serial
import logging
import struct
import RPi.GPIO as GPIO


logger = logging.getLogger('pipefinch.pipeline.filestructure')
# Classes and functions


class Event():
    pin = 1

    def __init__(self, pin=1):
        self.pin = pin
        # init the pin
        logger.info(
            'Initializing Event instance with pin {}'.format(self.pin))
        GPIO.setup(self.pin, GPIO.OUT)
        GPIO.output(self.pin, GPIO.LOW)
        logger.info('done')
        return 0


class TTLStim(Event):
    # A simple stimulus that just triggers itself (a pin) to be on for a period of time
    def __init__(self, pin):
        super(TTLStim, self).__init__(pin)
        logger.debug('Set ttl stim on pin {}'.format(self.pin))
    # in this one, the pin proper is the activator.
    def on(self):
        GPIO.output(self.pin, GPIO.HIGH)
        logger.debug('set pin {} hi'.format(self.pin))
        return 0

    def off(self):
        GPIO.output(self.pin, GPIO.LOW)
        return 0


class WavPlayer():
    def __init__(self, pin=5):
        raise NotImplementedError(
            'If you want to use WavPayer you need to setup pyaudio')
        self.pin = pin
        self.pa = pyaudio.PyAudio()
        self.wf = None
        self.played = False

        # init the pins
        GPIO.setup(self.pin, GPIO.OUT)
        GPIO.output(self.pin, GPIO.LOW)

    def play_callback(self, in_data, frame_count, time_info, status):
        data = self.wf.readframes(frame_count)
        return (data, pyaudio.paContinue)

    def play_file(self, wave_file_path):
        self.wf = wave.open(wave_file_path, 'rb')
        stream = self.pa.open(format=self.pa.get_format_from_width(self.wf.getsampwidth()),
                              channels=self.wf.getnchannels(),
                              rate=self.wf.getframerate(),
                              output=True,
                              stream_callback=self.play_callback)

        GPIO.output(self.pin, GPIO.HIGH)
        stream.start_stream()

        while stream.is_active():
            # time.sleep(0.1)
            pass
        GPIO.output(self.pin, GPIO.LOW)
        time.sleep(0.1)
        stream.stop_stream()
        stream.close()
        self.flush_file()

    def flush_file(self):
        self.wf = None
        self.played = False


class SerialOutput():
    def __init__(self, port="/dev/ttyS0", baudrate=300):
        self.port = port
        self.baudrate = baudrate
        self.serial = serial.Serial(port=port, baudrate=self.baudrate)
        logger.info('Initializing SerialOuptput in port {}, baud_rate {}'.format(port,
                                                                                 baudrate))

    def open_out(self):
        self.serial.close()
        self.serial.open()
        if self.serial.isOpen():
            logger.info("Serial is open!")

    def close(self):
        self.serial.close()

    def write_number(self, number, dtype='L'):
        self.serial.write(struct.pack(dtype, number))


# receives a line and turns it into a dictionary
# the line has one word for the command and n pairs that go to key, value (separator is space)
def parse_command(cmd_str):
    split_cmd = cmd_str.split(' ')
    assert(len(split_cmd) % 2)
    cmd_par = {split_cmd[i]: split_cmd[i+1]
               for i in range(1, len(split_cmd), 2)}
    cmd = split_cmd[0]
    return cmd, cmd_par


def execute_command(cmd, pars):
    command = command_functions[cmd]
    response = command(pars)
    return response


def send_trial_number(trial_pars):
    # read the parameters
    trial_number = int(float(trial_pars['number']))
    
    # do the deed
    so.write_number(trial_number)
    return 'ok trial_number:{0}'.format(trial_number)


def run_trial(trial_pars: dict):
    # here is where the trial is defined
    # for now the trial is just playing a sound file
    # read the parameters
    # for the female presetation, you only want to do smartglass
    wavefile_path = trial_pars['stim_file']
    trial_number = int(float(trial_pars['number']))

    # do the deed
    so.write_number(trial_number)
    time.sleep(0.5)
    wp.play_file(wavefile_path)
    return 0


def run_smartglass_trial(trial_pars: dict):
    # here is where the trial is defined
    # for now the trial is just playing a sound file
    # read the parameters
    # for the female presetation, you only want to do smartglass
    ttl_on_time = int(trial_pars['duration'])  # seconds on

    trial_number = int(float(trial_pars['number']))

    # do the deed
    so.write_number(trial_number)
    time.sleep(0.5)
    smartglass_ttl.on()
    time.sleep(ttl_on_time)
    smartglass_ttl.off()
    return 0

def smartglass_switch(trial_pars: dict):
    new_status = trial_pars['switch']

    if new_status == 'on':
        smartglass_ttl.on()
    else:
        smartglass_ttl.off()
    return 'smartglass_switched {}'.format(new_status)


def init_board():
    # init the board, the pins, and everything
    GPIO.cleanup()
    GPIO.setmode(GPIO.BOARD) # pins are mapped to board pin number
    return 0


def state_machine():
    port = "5558"
    #wave_file = os.path.abspath('/root/experiment/stim/audiocheck.net_sin_1000Hz_-3dBFS_3s.wav')

    # a very simple server that waits for commands
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind("tcp://*:%s" % port)
    logger.info('Setup ZMQ in port {}'.format(port))

    while True:
        # Wait for next request from client
        logger.info('Waiting for commands...')
        command = socket.recv().decode('utf8')
        logger.info("Received request: " + command)

        cmd, cmd_par = parse_command(command)
        response = execute_command(cmd, cmd_par).encode('utf8')
        time.sleep(1)
        socket.send(response)


command_functions = {'trial': run_smartglass_trial, 
                     'init': init_board, 
                     'trial_number': send_trial_number,
                     'glass': smartglass_switch}


if __name__ == '__main__':
    print('Gentnerlab OpenEphys Rig State Machine')
    print('Originally by Zeke Arneodo, Modified by Brad Theilman')
    logging.basicConfig(level=logging.DEBUG)
    logger.info('Setting up and startin state machien')
    # Configuration of Pins
    pin_smartglass = 37  # Physical pin 37; One Gnd is physical pin 39

    init_board()

    smartglass_ttl = TTLStim(pin=pin_smartglass)
    so = SerialOutput()

    state_machine()
