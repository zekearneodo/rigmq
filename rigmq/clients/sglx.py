import socket
import time
import logging
import numpy as np
import os

logger = logging.getLogger('rigmq.clients.sglx')

def print_msg(msg: str):
    logger.info(msg)

class NetClient():
    '''
    classdocs
    '''
    stream_matrix = []
    recv_str = ''

    def __init__(self, hostname: str='127.0.0.1', port: int=4142):
        self.HOSTNAME = hostname
        self.PORT = port
        try:
            self.connect()
            self.close()
        except socket.error as msg:
            print_msg(msg)
            self.close()
        return

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # IPv4, TCP (UDP is socket.SOCK_DGRAM)
        self.sock.connect((self.HOSTNAME, self.PORT))
        self.sock.settimeout(1)  # wait only 0.2 second before timing out.
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        # print 'connect'
        return

    def close(self):
        if self.sock:
            self.sock.shutdown(socket.SHUT_RDWR)
            self.sock.close()
        self.sock = None
        return

    def _reconnect(self):
        if self.sock:
            self.close()
        self.connect()
        return

    def send_string(self, send_string, line_end='\n'):
        if type(send_string) is not str:
            print_msg('The input to this function must be a string.')
            return None
        send_string = send_string + line_end  # add line ending to the string.
        if not self.sock:
            self.connect()
            time.sleep(0.001)
        try:
            send_bytes = bytes(send_string, 'utf-8')
            self.sock.sendall(send_bytes)
        except socket.error:
            print_msg("reconnecting")
            self._reconnect()
            self.send_string(send_string, line_end)
        return

    def receive_string(self, buffer_size=4096):
        received = ''
        try:
            received = self.sock.recv(buffer_size)
        except (socket.error, AttributeError):
            self._reconnect()
        received_str = received.decode()
        return received_str

    def receive_ok(self, buffer_size=2048, close=True, iterations=10, return_all=False):
        self.recv_buffer = []
        received = ''
        tries = 0
        while received.find('OK\n') == -1 and received.find('ERROR') == -1 and tries < iterations:
            received = self.receive_string(buffer_size)
            if received:
                print(received)
                self.recv_buffer.append(received)
            tries += 1

        # print tries
        if received.find('ERROR') != -1:
            print_msg('ERROR IN RECIEVING VALUE from receive_ok method!')
            print_msg(received)
            return None
        elif tries >= iterations:
            print_msg('Conducted ' + str(iterations) + ' without recieving OK')
        else:
            self.recv_str = ''.join(self.recv_buffer)
        # print 'joining'
        if close:
            self.close()  # close socket...

        if return_all is False:
            self.recv_str = self.recv_str[:self.recv_str.find('\nOK')]

        if self.recv_str == '':
            return True
        else:
            return self.recv_str

class SGLInterface():
    '''
    classdocs
    '''
    last_sample_read = 0
    acquiring = False
    params = None
    adc_scale = None

    def __init__(self, **kwargs):
        '''
        Constructor
        '''

        self.net_client = NetClient()
        self.query_acquire()
        self.fs = 25000
        return


    def close_connect(self):
        self.net_client.close()
        return

    def get_ver(self):
        # returns version number.
        self.net_client.send_string('GETVERSION')
        self.version = self.net_client.receive_ok()
        self.net_client.close()
        print_msg(self.version)
        return

    def get_params(self):
        # returns a string of parameters from net_client.
        self.net_client.send_string('GETPARAMS')
        param_string = self.net_client.receive_ok()
        # print param_string
        param_list = param_string.splitlines()
        self.params = dict()
        for param in param_list:
            param_split = param.split('=')  # split the keys and the values
            try:  # convert string into numeric when possible.
                param_split[1] = int(param_split[1])
            except:
                try:
                    param_split[1] = float(param_split[1])
                except:
                    pass
            self.params[param_split[0]] = param_split[1]
        return self.params

    def set_params(self, params):
        if self.query_acquire():
            print_msg('Cannot set params during acquisition.')
            return False
        self.net_client.send_string('SETPARAMS')
        rcd = self.net_client.receive_string()
        if rcd.find('READY') == -1:
            print_msg('SPIKEGLx did not return READY for params.')
            return False
        for key, val in params.iteritems():
            if val:
                line = str(key) + ' = ' + str(val)
                self.net_client.send_string(line)
        self.net_client.send_string('')  # send blank line at the end as per protocol...
        ok = self.net_client.receive_ok()
        if ok:
            self.params = params
        return True

    def set_save_file(self, filename):  # FILENAME should be in 'C:/folder/whatever.bin' format.
        if type(filename) is not str:
            print_msg(type(filename))
            print_msg(filename)
            print_msg('SPIKEGL FILENAME MUST BE A VALID STRING.')

        d, n = os.path.split(filename)
        print_msg(d)
        if d:
            d2 = d.replace("\\", "/")
            sendstring = "SETRUNDIR {0}".format(d2)
            self.net_client.send_string(sendstring)
            ok = self.net_client.receive_ok()
            if ok == 'OK':
                print_msg('SpikeGL save directory set: {0}.'.format(d2))
            else:
                print_msg('SpikeGL save directory NOT SET')
                return False

        sendstring = "SETRUNNAME {0}".format(n)
        self.net_client.send_string(sendstring)
        ok = self.net_client.receive_ok()
        if ok == 'OK':
            print_msg('SpikeGL save filename set: {0}'.format(n))
            return True
        else:
            print_msg('SpikeGL save filename NOT SET')
            return False

    def query_acquire(self):
        self.net_client.send_string('ISRUNNING')
        re = self.net_client.receive_ok()
        if int(re) == 1:
            self.acquiring = True
        elif int(re) == 0:
            self.acquiring = False
        return self.acquiring

    def start_acquire(self, params=None):
        if not params:
            params = self.get_params()
        if type(params) != dict:
            print_msg('PARAMETERS MUST BE IN FORM OF DICTIONARY')
            return False
        if self.query_acquire():
            return True
        done = self.set_params(params)
        if not done:
            return False
        self.net_client.send_string('STARTRUN\n')
        time.sleep(.1)
        done = self.net_client.receive_ok()
        if done == 'OK':
            self.acquiring = True
            print_msg('SpikeGL acquisition started.')
            return True
        else:
            return False

    def stop_acquire(self):
        self.net_client.send_string('STOPRUN\n')
        done = self.net_client.receive_ok()
        if done == 'OK':
            self.saving = False
            self.acquiring = False
            return True
        else:
            return False

    def query_save(self):
        self.net_client.send_string('ISSAVING')
        re = self.net_client.receive_ok()
        if int(re) == 1:
            self.saving = True
        elif int(re) == 0:
            self.saving = False
        return self.saving

    def start_save(self, filename):
        if self.query_save():
            return True
        if not self.query_acquire():
            return False

        name_set = self.set_save_file(filename)
        if not name_set:
            return False
        self.net_client.send_string('SETRECORDENAB 1')
        done = self.net_client.receive_ok()
        if done == 'OK':
            self.saving = True
            print_msg('SpikeGL save started.')
            return True
        else:
            print_msg('ERROR: SpikeGL')
            return False

    def stop_save(self):
        pass  # BECAUSE OF SGLX BUG!
        self.net_client.send_string('SETRECORDENAB 0')
        done = self.net_client.receive_ok()
        if done:
            self.saving = False
        return done

    def hide_console(self):
        self.net_client.send_string('CONSOLEHIDE')
        self.net_client.receive_ok()
        return

    def unhide_console(self):
        self.net_client.send_string('CONSOLEUNHIDE')
        self.net_client.receive_ok()
        return

    def get_time(self):
        self.net_client.send_string('GETTIME')
        time = self.net_client.receive_ok()
        return float(time)

    def get_scancount(self, close=True):
        if not self.acquiring and not self.query_acquire():
            return False
        self.net_client.send_string('GETSCANCOUNTNI')
        return int(self.net_client.receive_ok(close=close))

    def query_channels(self):
        self.net_client.send_string('GETSAVECHANSNI')
        self.channels = self.net_client.receive_ok()
        return self.channels

    def set_adc_scale(self):
        if not self.params:
            self.get_params()

        Vdd = self.params['niAiRangeMax']
        Vss = self.params['niAiRangeMin']
        ADC_bits = 16
        gain = self.params['niMNGain']
        #
        # Vdd = 2
        # Vss = -2
        #         ADC_bits = 16.
        #         gain = 200.
        scale = ((Vdd - Vss) / (pow(2., 16.))) / gain
        self.adc_scale = np.float64(scale)

    def get_daq_data(self, end_sample, num_samples, channels, close=True, ):
        # returns a m by n matrix of m channels with n samples.
        if not self.adc_scale:
            self.set_adc_scale()

        if not self.acquiring and not self.query_acquire():
            return False
        start_sample = end_sample - num_samples
        if channels.__class__ is int:  # make iterable.
            channels = [channels]
        chan_str = ''
        for ch in channels:
            chan_str = chan_str + str(ch) + '#'
        # line = 'FETCHNI {0} {1} {2}'
        line = 'FETCHNI ' + str(start_sample) + ' ' + str(num_samples) + ' ' + chan_str + ' 1'
        # print line
        self.net_client.send_string(line)
        self.bufstr = self.net_client.receive_ok(1048576, close, 1000, True)
        # print 'length buffer' +str(len(self.bufstr))
        handshake, _, self.buf = self.bufstr.partition('\n')
        dims = handshake.split(' ')
        # print dims
        if len(self.buf) < int(dims[1]) * int(dims[2]) + 2:
            self.buf = self.buf + self.net_client.receive_ok(20971520, close, 20)
            print_msg('short')
        try:
            self.data = np.fromstring(self.buf, dtype=np.int16, count=int(dims[1]) * int(dims[2]))
            self.data = self.data.astype(np.float64, copy=False)
        except:
            #             print bufstr
            print_msg('length buff: ' + str(len(self.buf)))
            print_msg('handshake: ' + handshake)
            return None

        self.data.shape = (int(dims[2]), int(dims[1]))
        #         arr.shape = (int(dims[3]),int(dims[2])) THIS WOULD RESHAPE TO BE FORTRANIC.
        self.data = self.data.T * self.adc_scale
        return

    def get_next_data(self, channels, max_read=5000):
        # times = time.time()
        if self.acquiring or self.query_acquire():
            self.acquiring = True
        else:
            return False
        current_sample = self.get_scancount(close=False)

        num_samples = current_sample - self.last_sample_read  # gives the number of samples since the last acquistion.

        if num_samples > max_read:
            num_samples = max_read
            print_msg('reducing')
        if num_samples == 0:
            self.data = np.array([[]], dtype=np.float64)
            print_msg('no data')
            return None
        self.last_sample_read = current_sample
        self.get_daq_data(current_sample, num_samples, channels, False)
        # print time.time()-times
        #self.acquisition_complete.emit()
        return