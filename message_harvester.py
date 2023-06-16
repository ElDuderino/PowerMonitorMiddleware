import logging
from multiprocessing import Event
from queue import Queue, Empty
from threading import Thread

from api_message_writer import APIMessageWriter
from sensor_message_item import SensorMessageItem


class MessageHarvester(Thread):
    """
    The thread to manage the consumption of the payload queue from the serial port reader
    """

    def __init__(self, payload_queue: Queue, sig_event: Event):
        super(MessageHarvester, self).__init__()

        self.logger = logging.getLogger(__name__)
        self.logger.info("Init MessageHarvester")
        self.sig_event = sig_event

        self.payload_queue = payload_queue

        self.api_sender = APIMessageWriter(sig_event)
        self.api_sender.start()

    def run(self):
        self.logger.info("Enter MessageHarvester run()")
        while True:

            if self.sig_event.is_set():
                print("Exiting {}".format(self.__class__.__name__))
                self.api_sender.join(1000)
                break

            payload = self.payload_queue.get()
            sensor_message_item = SensorMessageItem(mac=payload['mac'],
                                                    sensor_type=payload['type'],
                                                    timestamp=payload['timestamp'],
                                                    payload_data=payload['data'])

            self.api_sender.enqueue_msg(sensor_message_item)
