# Classes to communicate with the open_ephys gui
import zmq
import time
import logging


class OpenEphysEvents:
    def __init__(self, port='5556', ip='127.0.0.1'):
        self.ip = ip
        self.port = port
        self.socket = None
        self.context = None
        self.timeout = 5.
        self.last_cmd = None
        self.last_rcv = None

    def connect(self):
        url = "tcp://%s:%d" % (self.ip, int(self.port))
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.RCVTIMEO = int(self.timeout * 1000)
        self.socket.connect(url)

    def start_acq(self, ):
        if self.query_status('Acquiring'):
            print('Already acquiring')
        else:
            self.send_command('StartAcquisition')
            if self.query_status('Acquiring'):
                print('Acquisition Started')
            else:
                print('Something went wrong starting acquisition')

    def stop_acq(self, ):
        if self.query_status('Recording'):
            print('Cant stop acquistion while recording')

        elif not self.query_status('Acquiring'):
            print('No acquisition running')

        else:
            self.send_command('StopAcquisition')
            if not self.query_status('Acquiring'):
                print('Acquistion stopped')
            else:
                print('Something went wrong stopping acquisition')

    def start_rec(self, rec_par={'CreateNewDir': '0',
                                 'RecDir': None,
                                 'PrependText': None,
                                 'AppendText': None}):
        ok_to_start = False
        ok_started = False

        if self.query_status('Recording'):
            print('Already Recording')

        elif not self.query_status('Acquiring'):
            print('Was not Acquiring')
            self.start_acq()
            if self.query_status('Acquiring'):
                ok_to_start = True
                print('OK to start')
        else:
            ok_to_start = True
            print('OK to start')

        if ok_to_start:
            rec_opt = ['{0}={1}'.format(key, value)
                       for key, value in rec_par.items()
                       if value is not None]
            self.send_command(' '.join(['StartRecord'] + rec_opt))
            if self.query_status('Recording'):
                print('Recording path: {}'.format(self.get_rec_path()))
                ok_started = True
            else:
                print('Something went wrong starting recording')
        else:
            print('Did not start recording')
        return ok_started

    def stop_rec(self, ):
        if self.query_status('Recording'):
            self.send_command('StopRecord')
            if not self.query_status('Recording'):
                print('Recording stopped')
            else:
                print('Something went wrong stopping recording')
        else:
            print('Was not recording')

    def break_rec(self):
        ok_to_start = False
        ok_started = False
        print('Breaking recording in progress')
        if self.query_status('Recording'):
            self.send_command('StopRecord')
            if not self.query_status('Recording'):
                #print('Recording stopped')
                ok_to_start = True
                #print('OK to start')
            else:
                print('Something went wrong stopping recording')

        else:
            print('Was not recording')

        if ok_to_start:
            #print('trying to record')
            self.send_command('StartRecord')
            if self.query_status('Recording'):
                #print('Recording path: {}'.format(self.get_rec_path()))
                ok_started = True
            else:
                print('Something went wrong starting recording')

    def get_rec_path(self):
        return self.send_command('GetRecordingPath')

    def query_status(self, status_query='Recording'):
        query_dict = {'Recording': 'isRecording',
                      'Acquiring': 'isAcquiring'}

        status_queried = self.send_command(query_dict[status_query])
        return True if status_queried == '1' else False if status_queried == '0' else None

    def send_command(self, cmd: str) -> str:
        self.socket.send(cmd.encode('utf8'))
        self.last_cmd = cmd
        self.last_rcv = self.socket.recv().decode('utf8')
        return self.last_rcv

    def close(self):
        self.stop_rec()
        self.stop_acq()
        self.context.destroy()