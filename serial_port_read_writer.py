import configparser
import logging
from multiprocessing import Event
from queue import Queue
from threading import Thread
from time import time
from AretasPythonAPI.utils import Utils as AretasUtils
from dalybms import DalyBMS
from sensor_message_item import SensorMessageItem
from XDM1041Python.xdm1041main import *


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

        self.daly_ = DalyBMS(request_retries=3, address=8, device=self.serial_port)
        self.daly_.connect()

        # current measurement via XDM
        self._xdm_current_device = None
        self._xdm_current_enabled = config.getboolean("XDM", "xdm_current_enable")
        self._xdm_shunt_resistance = config.getfloat("XDM", "xdm_shunt_resistance")
        self._xdm_reverse_current_polarity = config.getboolean("XDM", "xdm_current_reverse_polarity")

        if self._xdm_current_enabled:
            xdm_serial_port = config.get("XDM", "xdm_current_port")
            # initialize the XDM device to use voltage mode since we're measuring the voltage across the shunt
            self._xdm_current_device = XDM1041(XDM1041Mode.MODE_VOLTAGE_DC, 1, xdm_serial_port)
            self.logger.info("Initializing XDM Meter for Current Measurement")
            self.logger.info(self._xdm_current_device.test_conn())

        # voltage measurement via XDM
        self._xdm_voltage_device = None
        self._xdm_voltage_enabled = config.getboolean("XDM", "xdm_voltage_enable")

        if self._xdm_voltage_enabled:
            xdm_serial_port_v = config.get("XDM", "xdm_voltage_port")
            # initialize the XDM device to use voltage mode since we're measuring the voltage across the shunt
            self._xdm_voltage_device = XDM1041(XDM1041Mode.MODE_VOLTAGE_DC, 5, xdm_serial_port_v)
            self.logger.info("Initializing XDM Meter for Voltage Measurement")
            self.logger.info(self._xdm_voltage_device.test_conn())

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

        If enabled, read the XDM instrument to get current and replace the Daly BMS value

        If enabled, read the XDM instrument to get voltage and replace the Daly BMS value

        @return:
        """

        params = self.daly_.get_all()

        xdm_current_meas = None
        xdm_voltage_meas = None

        if self._xdm_current_enabled and (self._xdm_current_device is not None):
            xdm_voltage = self._xdm_current_device.read_val1_raw()
            # apply I = V / R
            xdm_current_meas = xdm_voltage / self._xdm_shunt_resistance
            if self._xdm_reverse_current_polarity:
                xdm_current_meas = xdm_current_meas * -1.0

        if self._xdm_voltage_enabled and (self._xdm_voltage_device is not None):
            xdm_voltage_meas = self._xdm_voltage_device.read_val1_raw()

        if params is not None:

            payload_items = self.decode_daly_msg(params)
            for item in payload_items:

                # if xdm *current* is enabled, replace the value with the XDM calculated current measurement
                if item.get_type() == 531 and xdm_current_meas is not None:
                    self.logger.info(
                        "Replacing Daly current value:{} with XDM value:{}".format(item.get_data(), xdm_current_meas)
                    )
                    item.set_data(xdm_current_meas)

                # if xdm *voltage* is enabled, replace the value with the XDM calculated voltage measurement
                if item.get_type() == 532 and xdm_voltage_meas is not None:
                    self.logger.info(
                        "Replacing Daly voltage value:{} with XDM value:{}".format(item.get_data(), xdm_voltage_meas)
                    )
                    item.set_data(xdm_voltage_meas)

                self.payload_queue.put(item)

            self.logger.info("Enqueued {} items".format(len(payload_items)))
        else:
            self.logger.error("Could not fetch BMS params")

    def decode_daly_msg(self, params: dict) -> list:

        ret = list()

        now = AretasUtils.now_ms()

        self.logger.info("Decoding params:{}".format(params))

        try:

            if 'soc' in params.keys():

                voltage = params['soc']['total_voltage']
                current = params['soc']['current']
                soc = params['soc']['soc_percent']
                # compute power for energy consumption calculations
                kw = (float(voltage) * float(current))/1000

                msg_voltage = SensorMessageItem(self.mac, 532, float(voltage), now)
                ret.append(msg_voltage)

                msg_current = SensorMessageItem(self.mac, 531, float(current), now)
                ret.append(msg_current)

                msg_kw = SensorMessageItem(self.mac, 533, kw, now)
                ret.append(msg_kw)

                msg_soc = SensorMessageItem(self.mac, 514, float(soc), now)
                ret.append(msg_soc)

            if 'temperatures' in params.keys() and params['temperatures'] is not None:
                temperature = params['temperatures'][1]

                msg_temperature = SensorMessageItem(self.mac, 520, float(temperature), now)
                ret.append(msg_temperature)

            if 'mosfet_status' in params.keys():
                capacity_ah = params['mosfet_status']['capacity_ah']

                msg_ahr = SensorMessageItem(self.mac, 530, float(capacity_ah), now)
                ret.append(msg_ahr)

        except Exception as e:

            self.logger.error("Unknown exception trying to decode BMS params:{}".format(e))

            pass

        return ret
