# Functions to talk to a state machine in the beaglebone
import os
import sys
import zmq
import time
import logging

import numpy as np


def parse_command(cmd_str):
    """
    # the line has one word for the command and n pairs that go to key, value (separator is space)
    :param cmd_str: string with name of command and pairs of params and values
    :return: cmd : str (name of the command)
            cmd_par: dictionary {par_name: str(par_value)} with the parameters for the command
    """
    split_cmd = cmd_str.split(' ')
    assert (len(split_cmd) % 2)
    cmd_par = {split_cmd[i]: split_cmd[i + 1] for i in range(1, len(split_cmd), 2)}
    cmd = split_cmd[0]
    return cmd, cmd_par


class SBC:
    # connects to a single board computer running a zmq server on port port,
    # in ip ip.
    def __init__(self, port='5558', ip='192.168.7.2', timeout_s=60.):
        self.ip = ip
        self.port = port
        self.socket = None
        self.context = None
        self.timeout = int(timeout_s * 1000) # timeout in ms
        self.last_cmd = None
        self.last_rcv = None

    def connect(self):
        url = "tcp://%s:%d" % (self.ip, int(self.port))
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.RCVTIMEO = self.timeout
        self.socket.connect(url)

    def send_command(self, cmd):
        self.socket.send(cmd)
        self.last_cmd = cmd
        # stays locked until commands executes and response comes back
        # this should go on a thread of the program that uses it
        self.last_rcv = self.socket.recv().decode('utf8')
        return self.last_rcv

    def close(self):
        self.context.destroy()