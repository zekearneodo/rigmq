# state machine that listens trhoruhgh a zmq port and excecutes commands (stimuli)
# state machine runs on a beaglebone black
# audio playback requires pyaudio

import pyaudio
import wave
import time
import sys
import os
import zmq
import serial
import struct
import numpy as np
import Adafruit_BBIO.GPIO as GPIO
import Adafruit_BBIO.UART as UART


# some globals

pin_audio = "P8_10"
pin_rec = "P8_46"  # But it is not implemented. rec goes through zmq.
pin_trial = "P8_45"

command_functions = {'trial' : run_trial,
                    'init' : init_board,
                    'play_wav': play_wav_file,
                    'trial_number': send_trial_number,
                    'trial_pin': switch_trial_pin,
                    'record' : switch_record_status}

module_dict = {'serial_out': SerialOutput(),
               'trial_pin': TrialPin(pin=pin_trial),
               'wav_play': WavPlayer(pin=pin_audio)}

# receives a line and turns it into a dictionary
# the line has one word for the command and n pairs that go to key, value (separator is space)
def parse_command(cmd_str):
    split_cmd = cmd_str.split(' ')
    assert (len(split_cmd) % 2)
    cmd_par = {split_cmd[i]: split_cmd[i + 1] for i in range(1, len(split_cmd), 2)}
    cmd = split_cmd[0]
    return cmd, cmd_par


def execute_command(cmd, pars):
    command = command_functions[cmd]
    response = command(pars)
    return response



class WavPlayer():
    def __init__(self, pin="P8_10"):
        self.pin = pin
        self.pa = pyaudio.PyAudio()
        self.wf = None
        self.n_chan = None
        self.played = False

        # init the pins
        GPIO.setup(self.pin, GPIO.OUT)
        GPIO.output(self.pin, GPIO.LOW)

    def play_callback(self, in_data, frame_count, time_info, status):
        # print(frame_count)
        frame_advance = frame_count * self.n_chan
        data = self.wf[:frame_advance].tostring()
        self.wf = np.delete(self.wf, np.s_[:frame_advance])
        return (data, pyaudio.paContinue)

    def play_file(self, wave_file_path):
        # open wav file and load into np array
        wave_file = wave.open(wave_file_path, 'rb')
        samp_width = wave_file.getsampwidth()
        self.n_chan = wave_file.getnchannels()
        rate = wave_file.getframerate()
        self.wf = wave_file.readframes(wave_file.getnframes())
        self.wf = np.fromstring(self.wf, dtype=np.int16)

        stream = self.pa.open(format=self.pa.get_format_from_width(samp_width),
                              channels=self.n_chan,
                              rate=rate,
                              output=True,
                              stream_callback=self.play_callback)

        GPIO.output(self.pin, GPIO.HIGH)
        time.sleep(1)
        stream.start_stream()

        while stream.is_active():
            time.sleep(0.1)
            pass
        stream.stop_stream()
        stream.close()
        self.flush_file()
        # time.sleep(1)
        GPIO.output(self.pin, GPIO.LOW)

    def flush_file(self):
        self.wf = None
        self.played = False
        self.n_chan = None


class TrialPin():
    def __init__(self, pin="P8_45"):
        self.pin = pin
        self.on = False

        GPIO.setup(self.pin, GPIO.OUT)
        GPIO.output(self.pin, GPIO.LOW)

    def toggle_rec_status(self, new_status):
        # new_status is boolean
        if new_status != self.on:
            self.on = new_status
            GPIO.output(self.pin, bool_to_gpio(new_status))


class RecControl():
    def __init__(self, pin="P8_45"):
        self.pin = pin
        self.on = False

        GPIO.setup(self.pin, GPIO.OUT)
        GPIO.output(self.pin, GPIO.LOW)

    def toggle_status(self, new_status):
        # new_status is boolean
        if new_status != self.on:
            self.on = new_status
            GPIO.output(self.pin, bool_to_gpio(new_status))


class SerialOutput():
    def __init__(self, uart="UART1", port="/dev/ttyO1", baudrate=300):
        self.uart = uart
        self.port = port
        self.baudrate = baudrate
        UART.setup(uart)
        self.serial = serial.Serial(port=port, baudrate=self.baudrate)

    def open_out(self):
        self.serial.close()
        self.serial.open()
        if self.serial.isOpen():
            print("Serial is open!")

    def close(self):
        self.serial.close()

    def write_number(self, number, dtype='L'):
        self.serial.write(struct.pack(dtype, number))



def str_to_bool(s):
    if s.lower() == 'true':
        return True
    elif s.lower() == 'false':
        return False
    else:
        raise ValueError


def bool_to_str(b):
    # b is boolean
    s = 'True' if b else 'False'
    return s


def bool_to_gpio(b):
    # b is boolean
    return GPIO.HIGH if b else GPIO.LOW


# command functions:
def run_trial(trial_pars):
    # for now the trial is just playing a sound file
    # read the parameters
    wavefile_path = trial_pars['stim_file']
    trial_number = int(float(trial_pars['number']))

    # do the deed
    module_dict['serial_out'].write_number(trial_number)
    time.sleep(0.1)
    module_dict['wav_play'].play_file(wavefile_path)
    return 'ok trial:{0}, file:{1}'.format(trial_number, wavefile_path)


def play_wav_file(file_pars):
    wavefile_path = file_pars['stim_file']
    module_dict['wav_play'].play_file(wavefile_path)
    return 'ok file:{0}'.format(wavefile_path)


def send_trial_number(trial_pars):
    # read the parameters
    trial_number = int(float(trial_pars['number']))

    # do the deed
    module_dict['serial_out'].write_number(trial_number)
    return 'ok trial_number:{0}'.format(trial_number)


def switch_trial_pin(trial_pars):
    new_status = str_to_bool(trial_pars['on'])
    module_dict['trial_pin'].toggle_rec_status(new_status)
    return 'ok trial_pin:' + bool_to_str(new_status)


def switch_record_status(rec_pars):
    new_rec_status = str_to_bool(rec_pars['on'])
    module_dict['rec_control'].toggle_rec_status(new_rec_status)
    return 'rec ' + bool_to_str(new_rec_status)


def get_args():
    parser = argparse.ArgumentParser(description='run state machine on beaglebone)')

    parser.add_argument('port', default = '5559', nargs='?',
                       help='port')
    return parser.parse_args()


def start_machine(port='5559'):
    test_file = os.path.abspath('/root/experiment/stim/audiocheck.net_sin_1000Hz_-3dBFS_3s.wav')

    # a very simple server that waits for commands
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind("tcp://*:%s" % port)

    while True:
        # Wait for next request from client
        print('Waiting for requests')
        command = socket.recv()
        # print("Received request: " + command)
        # socket.send("%s from %s" % (response, port))
        cmd, cmd_par = parse_command(command)
        response = execute_command(cmd, cmd_par, module_dict)
        socket.send(response)


def main():
    args = get_args()
    start_machine(port=args.port)

if __name__ == '__main__':
    main()
