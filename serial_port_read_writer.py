import configparser
import logging
import sys
from multiprocessing import Event
from queue import Queue
from threading import Thread
from time import time
from AretasPythonAPI.utils import Utils as AretasUtils
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
        self.sample_interval = int(config['SERIAL']['sample_interval'])
        self.last_sampled = 0

        self.payload_queue = payload_queue

        self.sig_event = sig_event

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

        if (self._xdm_voltage_enabled is False) and (self._xdm_current_enabled is False):
            self.logger.error("Neither voltage or current are enabled, nothing to do... exiting.")
            sys.exit(0)

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
        Fetch the XDM parameters, populate the SensorMessageItem contract and enqueue the messages

        @return:
        """
        payload_items = self.do_fetch_params()

        if payload_items is not None:

            for item in payload_items:
                self.logger.debug(item)
                self.payload_queue.put(item)

            self.logger.info("Enqueued {} items".format(len(payload_items)))
        else:
            self.logger.error("Could not fetch XDM params")

    def do_fetch_params(self) -> list[SensorMessageItem]:
        """
        Fetch current and voltage from XDM (if enabled)
        if both are enabled, also return kW
        @return: a list of SensorMessageItems
        """
        xdm_current_meas = None
        xdm_voltage_meas = None

        # several of these checks below are obnoxious and a remnant from the previous repo
        # where we had the BMS params and wanted to support optional XDM1041s
        # I'm going to keep things similar though so we can still have the flexibility of
        # supporting one, both or none :D
        if self._xdm_current_enabled and (self._xdm_current_device is not None):
            xdm_voltage = self._xdm_current_device.read_val1_raw()
            # apply I = V / R
            xdm_current_meas = xdm_voltage / self._xdm_shunt_resistance
            if self._xdm_reverse_current_polarity:
                xdm_current_meas = xdm_current_meas * -1.0

        if self._xdm_voltage_enabled and (self._xdm_voltage_device is not None):
            xdm_voltage_meas = self._xdm_voltage_device.read_val1_raw()

        ret = list()

        now = AretasUtils.now_ms()

        try:

            if xdm_voltage_meas is not None:
                msg_voltage = SensorMessageItem(self.mac, 532, float(xdm_voltage_meas), now)
                ret.append(msg_voltage)

            if xdm_current_meas is not None:
                msg_current = SensorMessageItem(self.mac, 531, float(xdm_current_meas), now)
                ret.append(msg_current)

            if (xdm_current_meas is not None) and (xdm_voltage_meas is not None):
                # compute power for energy consumption calculations
                kw = (float(xdm_voltage_meas) * float(xdm_current_meas)) / 1000
                msg_kw = SensorMessageItem(self.mac, 533, kw, now)
                ret.append(msg_kw)

        except Exception as e:

            self.logger.error("Unknown exception trying to decode BMS params:{}".format(e))

            pass

        return ret
