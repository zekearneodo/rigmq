# note that if WavPlayer wants to be used, pyaudio needs to be set up
# 12/6/2019, setup wavplayer on raspi.
# default channel should be the usb audio board
import pyaudio
import wave
import time
import sys
import os
import zmq
import serial
import logging
import struct
import RPi.GPIO as GPIO

## important todo:
## make whole trial happen here with timers.
## if harder real time is needed, use a teensy

logger = logging.getLogger('sbcrig.sbc.raspmachine_pyaudio')
# Classes and functions


class Event():
    pin = 1

    def __init__(self, pin: int=1):
        self.pin = pin
        # init the pin
        logger.info(
            'Initializing Event instance with pin {}'.format(self.pin))
        GPIO.setup(self.pin, GPIO.OUT)
        GPIO.output(self.pin, GPIO.LOW)
        logger.info('done')
        return 0


class TTLStim(Event): # True is high, False is lo.
    # A simple stimulus that just triggers itself (a pin) to be on for a period of time
    def __init__(self, pin:int, default_value: bool=False) -> int:
        super(TTLStim, self).__init__(pin)
        logger.debug('Set ttl stim on pin {}'.format(self.pin))
        if default_value:
            self.on()
        else:
            self.off()

    # in this one, the pin proper is the activator.
    def on(self):
        GPIO.output(self.pin, GPIO.HIGH)
        logger.debug('set pin {} hi'.format(self.pin))
        return 0

    def off(self):
        GPIO.output(self.pin, GPIO.LOW)
        logger.debug('set pin {} lo'.format(self.pin))
        return 0


class WavPlayer():
    def __init__(self, pin=40):
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


class SerialOutput(): # Not implemented yet on raspmachine
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
    return 'ok trial_number {0}'.format(trial_number)


def run_trial_audio(trial_pars: dict):
    # here is where the trial is defined
    # for now the trial is just playing a sound file
    # read the parameters
    # for the female presetation, you only want to do smartglass
    wavefile_path = os.path.join(wave_files_root, trial_pars['stim_file'])
    #trial_number = int(float(trial_pars['number']))

    # do the deed
    #so.write_number(trial_number)
    #time.sleep(0.5)
    wav_player.play_file(wavefile_path)
    return 0

def run_smartglass_trial(trial_pars: dict):
    # here is where the trial is defined
    # for now the trial is just playing a sound file
    # read the parameters
    # for the female presetation, you only want to do smartglass
    ttl_on_time = int(trial_pars['duration'])  # seconds on

    #trial_number = int(float(trial_pars['number']))

    # do the deed
    #so.write_number(trial_number)
    #time.sleep(0.5)
    # The relay we use activates on lo
    smartglass_ttl.off()
    time.sleep(ttl_on_time)
    smartglass_ttl.on()
    return 0

def run_trial_stim_pulse(trial_pars: dict):
    # here is where the trial is defined
    # for now the trial is just playing a sound file
    # read the parameters
    # for the female presetation, you only want to do smartglass
    #trial_number = int(float(trial_pars['number']))
    # do the deed
    stim_ttl.on()
    time.sleep(0.1)
    smartglass_ttl.off()
    return 0


def smartglass_switch(trial_pars: dict):
    new_status = trial_pars['switch']

    if new_status == 'on':
        smartglass_ttl.off()
    else:
        smartglass_ttl.on()
    return 'smartglass_switched {}'.format(new_status)


def init_board():
    # init the board, the pins, and everything
    GPIO.cleanup()
    GPIO.setmode(GPIO.BOARD) # pins are mapped to board pin number
    return 0


def state_machine():
    port = "5559"
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
        response = execute_command(cmd, cmd_par)
        return_response = 'cmd response: {}'.format(response).encode('utf8')
        time.sleep(1)
        socket.send(return_response)


command_functions = {'trial': run_smartglass_trial,
                     'trial_audio': run_trial_audio,
                     'init': init_board, 
                     'trial_number': send_trial_number,
                     'glass': smartglass_switch, 
                     'trial_stim_pulse': run_trial_stim_pulse}


if __name__ == '__main__':
    print('Gentnerlab OpenEphys Rig State Machine')
    print('Originally by Zeke Arneodo, Modified by Brad Theilman')
    logging.basicConfig(level=logging.DEBUG)
    logger.info('Setting up and startin state machien')
    
    # Configuration of Pins
    pin_smartglass = 37  # Physical pin 37; One Gnd is physical pin 39
    pin_wavplayer = 40 # pin to mark begin of waveplay
    pin_stimtrig = 35 # pin to control a stimulus with a ttl
    pin_stim = 38 # pin to control a stim pulse through a ttl
    
    init_board()
    
    # Other globals
    # location of stimulus files
    wave_files_root = os.path.abspath('/home/pi/stim_files')
    
    # TTls, players and other effector objects
    smartglass_ttl = TTLStim(pin=pin_smartglass, default_value=True) #the relay is off at hi.
    wav_player = WavPlayer(pin=pin_wavplayer)
    stim_ttl = TTLStim(pin=pin_stim)
    so = SerialOutput()

    # run the statemachine
    state_machine()
