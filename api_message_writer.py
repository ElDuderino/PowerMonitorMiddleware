import time
from threading import Thread, Event

import urllib3

from AretasPythonAPI.utils import Utils as AretasUtils
from AretasPythonAPI.api_config import *
from AretasPythonAPI.auth import *
from AretasPythonAPI.sensor_data_ingest import *
from sensor_message_item import SensorMessageItem


class APIMessageWriter(Thread):
    """
    This class writes the data to API
    inject data into this class by enqueue_msg
    Create an instance of this Thread and run it
    Data will be sent every report_interval milliseconds as specified in the config
    This means that any new data arriving before the interval elapsed will overwrite what's
    sitting in the local buffer
    """

    def __init__(self, sig_event: Event):

        super(APIMessageWriter, self).__init__()

        self.logger = logging.getLogger(__name__)
        self.sig_event = sig_event

        # read in the global app config
        config = configparser.ConfigParser()
        config.read('config.cfg')

        self.last_message_time = 0
        self.polling_interval = config.getint('API', 'report_interval')

        self.api_config = APIConfig()
        self.api_auth = APIAuth(self.api_config)
        self.api_writer = SensorDataIngest(self.api_auth)

        # a hashmap of sensor messages we want to send to the API
        self.to_send: dict([int, SensorMessageItem]) = dict()

        self.thread_sleep = config.getboolean('DEFAULT', 'thread_sleep')
        self.thread_sleep_time = config.getfloat('DEFAULT', 'thread_sleep_time')

        self.is_sending = False

    def enqueue_msg(self, message: SensorMessageItem):
        """
        Enqueue a message to be sent, the message may or may not be sent as it may be overwritten
        by a new value before being sent
        This thread manages its own send intervals and this function just
        adds the datum to a key/value store (indexed by sensor type)
        As such the key/value store index for a particular sensor type just gets overwritten by new data
        A flag is set in the dict entry to indicate if it has been sent or not
        New messages added to the dict always have the is_sent flag set to False
        """
        # don't accept new messages if we're in the process of sending
        # it's unlikely this will ever happen but...
        if self.is_sending is False:
            dict_key = message.get_type()
            # we're going to assert that it has not been sent
            message.set_is_sent(False)
            self.to_send[dict_key] = message
        return

    def run(self):
        """
        We send any of the messages in the self.to_send hashmap only if they have not
        been flagged as sent
        """
        while True:
            if self.sig_event.is_set():
                self.logger.info("Exiting {}".format(self.__class__.__name__))
                break

            # get the current time in milliseconds
            now_ = AretasUtils.now_ms()

            # determine if the polling interval has elapsed
            if (now_ - self.last_message_time) >= self.polling_interval:
                n_send = len(list(filter(lambda x: x.get_is_sent() is False, self.to_send.values())))
                self.logger.info("Sending {} messages to API".format(n_send))
                self.last_message_time = now_
                # use the apiwriter
                self.is_sending = True

                # gather the items for the batch send
                to_send_items = []

                for key, message in self.to_send.items():
                    # if it hasn't been previously sent, then send it
                    if not message.get_is_sent():
                        datum: dict = {
                            'mac': message.get_mac(),
                            'type': message.get_type(),
                            'timestamp': message.get_timestamp(),
                            'data': message.get_data()
                        }

                        to_send_items.append(datum)

                # send as a batch then if sent, mark all as sent
                if len(to_send_items) > 0:
                    send_status = self.send_batch_to_api(to_send_items)
                    if send_status is True:
                        for key, message in self.to_send.items():
                            message.set_is_sent(True)

                else:
                    if self.thread_sleep is True:
                        time.sleep(self.thread_sleep_time)

                self.is_sending = False

    def send_batch_to_api(self, batch: list[dict]) -> bool:
        """
        Send a batch of messages to the API
        If sending is successful, set_is_sent to True
        """
        try:
            # we're using the token self-management function
            err = self.api_writer.send_data(batch, True)
            if err is False:
                self.logger.error("Error sending messages, aborting rest")
                return False
            else:
                return True

        except urllib3.exceptions.ReadTimeoutError as rte:
            '''
            There are a lot of things we need to handle in stateless HTTP land without
            aborting the thread
            '''
            self.logger.error("Read timeout error from urllib3:{}".format(rte))
            # we break because there's no point in trying to send the rest of the messages,
            # we can wait until next interval
            return False

        except requests.exceptions.ReadTimeout as rt:
            self.logger.error("Read timeout error from requests:{}".format(rt))
            return False

        except requests.exceptions.ConnectTimeout as cte:
            self.logger.error("Connection timeout error sending messages to API:{}".format(cte))
            return False

        # we need to be fairly aggressive with exception handling as we are in a thread
        # doing network stuff and network things are buggy as heck
        except Exception as e:
            self.logger.error("Unknown exception trying to send messages to API:{}".format(e))
            return False
