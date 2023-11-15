import configparser
import json
import logging
from multiprocessing import Queue, Event
from threading import Thread
import redis
import time
import jsonpickle
from sensor_message_item import SensorMessageItem


class RedisQueueReader(Thread):
    """
    This class pumps SensorModel messages into redis
    We don't want any thread blocking while waiting for redis to inject messages, timeout, etc.
    """

    def __init__(self, sig_event: Event):
        super(RedisQueueReader, self).__init__()

        self.logger = logging.getLogger(__name__)
        self.logger.info("Init Redis Queue Reader")

        # read in the global app config
        config = configparser.ConfigParser()
        config.read('config.cfg')

        redis_host = config.get("REDIS", "redis_host", fallback="localhost")
        redis_port = config.getint("REDIS", "redis_port", fallback=6379)
        redis_pw = config.get("REDIS", "redis_authpw", fallback="FooBar")

        self.r = redis.StrictRedis(redis_host, redis_port, password=redis_pw, decode_responses=True)

        self.message_queue = Queue()
        self.sig_event = sig_event

        self.thread_sleep = config.getboolean('DEFAULT', 'thread_sleep')
        self.thread_sleep_time = config.getfloat('DEFAULT', 'thread_sleep_time')

        self.message_count = 0

    def inject_message(self, message: SensorMessageItem):
        self.message_queue.put_nowait(message)

    def process_message(self, message: SensorMessageItem):
        try:
            msg_mac = message.get_mac()
            msg_type = message.get_type()
            msg_json = jsonpickle.encode(message)
            self.r.hset(str(msg_mac), str(msg_type), msg_json)
            self.message_count += 1

            if ((self.message_count % 100) == 0) or (self.message_count == 1):
                self.logger.info("Processed {} messages".format(self.message_count))

        except Exception as e:
            self.logger.error("Error submitting message to Redis:{}".format(e))

    def run(self):
        while True:
            while not self.message_queue.empty():
                message: SensorMessageItem = self.message_queue.get()
                self.process_message(message)

            if self.sig_event.is_set():
                print("Exiting {}".format(self.__class__.__name__))
                break

            if self.thread_sleep is True:
                time.sleep(self.thread_sleep_time)
