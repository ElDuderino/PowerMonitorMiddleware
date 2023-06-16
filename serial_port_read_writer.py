import configparser
import logging
from multiprocessing import Event
from queue import Queue
from threading import Thread
from time import time
import serial
from AretasPythonAPI.utils import Utils as AretasUtils
from dalybms import DalyBMS
from sensor_message_item import SensorMessageItem


class SerialPortReadWriter(Thread):
    """
    This thread monitors the serial port specified in the cfg
    and injects bytes and/or payloads into the semaphore queue
    """

    def __init__(self, payload_queue: Queue, sig_event: Event):
        super(SerialPortReadWriter, self).__init__()
        self.logger = logging.getLogger(__name__)

        self.pause_reading = False
        # read in the global app config
        config = configparser.ConfigParser()
        config.read('config.cfg')

        self.mac = config['DEFAULT']['self_mac']
        self.serial_port = config['SERIAL']['serial_port']
        self.sample_interval = int(config['SERIAL']['sample_interval'])
        self.last_sampled = 0

        self.payload_queue = payload_queue

        self.sig_event = sig_event

        self.daly_ = DalyBMS(3)
        self.daly_.connect(self.serial_port)

    def run(self):
        # enqueue bytes into the self.message_queue
        while True:
            if not self.pause_reading:
                # use the aretas utility function to ensure consistency
                now_ms = AretasUtils.now_ms()

                if (now_ms - self.last_sampled) > self.sample_interval:
                    self.read_port()
                    self.last_sampled = now_ms

                if self.sig_event.is_set():
                    self.logger.info("Exiting {}".format(
                        self.__class__.__name__))
                    break
            else:

                time.sleep(0.01)  # sleep for 10ms and allow UART to "settle"

    def write_cmd(self, cmd: bytes):
        """
        The idea is that if someone calls this function on the class, we "pause" the read loop in the class run()
        so we avoid port conflicts, emit the data over the serial port then return control to the read loop

        @param cmd:
        @return:
        """
        self.pause_reading = True
        # write data to the port
        # self.ser.write(cmd)
        self.pause_reading = False
        pass

    def read_port(self):
        """
        Read the daly BMS parameters, convert them into Aretas packets and inject into the message queue

        @return:
        """
        # payload = AretasPacket.parse_packet(packet)
        # if payload is not None:
        #    self.payload_queue.put(payload)

        params = self.daly_.get_all()
        payload_items = self.decode_daly_msg(params)
        for item in payload_items:
            self.payload_queue.put(item)
        self.logger.info("Enqueued {} items".format(len(payload_items)))

    def decode_daly_msg(self, params: dict) -> list:

        ret = list()

        now = AretasUtils.now_ms()

        if 'soc' in params.keys():

            voltage = params['soc']['total_voltage']
            current = params['soc']['current']
            soc = params['soc']['soc_percent']

            msg_voltage = SensorMessageItem(self.mac, 532, float(voltage), now)
            ret.append(msg_voltage)

            msg_current = SensorMessageItem(self.mac, 531, float(current), now)
            ret.append(msg_current)

            msg_soc = SensorMessageItem(self.mac, 514, float(soc), now)
            ret.append(msg_soc)

        if 'temperatures' in params.keys():
            temperature = params['temperatures']['1']

            msg_temperature = SensorMessageItem(self.mac, 520, float(temperature), now)
            ret.append(msg_temperature)

        if 'mosfet_status' in params.keys():
            capacity_ah = params['mosfet_status']['capacity_ah']

            msg_ahr = SensorMessageItem(self.mac, 530, float(capacity_ah), now)
            ret.append(msg_ahr)

        return ret
