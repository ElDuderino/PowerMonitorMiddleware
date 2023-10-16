import logging
from multiprocessing import Event
from queue import Queue, Empty
from threading import Thread
import configparser
from api_message_writer import APIMessageWriter
import time


class MessageHarvester(Thread):
    """
    The thread to manage the consumption of the payload queue from the serial port reader
    """

    def __init__(self, payload_queue: Queue, sig_event: Event):
        super(MessageHarvester, self).__init__()

        # read in the global app config
        config = configparser.ConfigParser()
        config.read('config.cfg')

        self.logger = logging.getLogger(__name__)
        self.logger.info("Init MessageHarvester")
        self.sig_event = sig_event

        self.payload_queue = payload_queue

        self.thread_sleep = config.getboolean('DEFAULT', 'thread_sleep')
        self.thread_sleep_time = config.getfloat('DEFAULT', 'thread_sleep_time')

        self.api_sender = APIMessageWriter(sig_event)
        self.api_sender.start()

    def run(self):
        self.logger.info("Enter MessageHarvester run()")
        while True:

            if self.sig_event.is_set():
                print("Exiting {}".format(self.__class__.__name__))
                self.api_sender.join(1000)
                break

            sensor_message_item = self.payload_queue.get()

            self.api_sender.enqueue_msg(sensor_message_item)

            if self.thread_sleep is True:
                time.sleep(self.thread_sleep_time)
