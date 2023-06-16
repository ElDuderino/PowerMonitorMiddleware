class SensorMessageItem:
    """
    A contract for the sensor message item type
    """
    def __init__(self, mac: int = -1,
                 sensor_type: int = -1,
                 payload_data: float = -1.0,
                 timestamp: int = -1,
                 sent: bool = False):

        self._type = sensor_type
        self._mac = mac
        self._timestamp = timestamp
        self._sent = sent
        self._data = payload_data
        pass

    def get_type(self) -> int:
        return self._type

    def set_type(self, sensor_type: int):
        self._type = sensor_type

    def get_data(self) -> float:
        return self._data

    def set_data(self, payload_data: float):
        self._data = payload_data

    def get_timestamp(self) -> int:
        return self._timestamp

    def set_timestamp(self, timestamp: int):
        self._timestamp = timestamp

    def get_mac(self) -> int:
        return self._mac

    def set_mac(self, mac: int):
        self._mac = mac

    def get_is_sent(self) -> bool:
        return self._sent

    def set_is_sent(self, is_sent: bool):
        self._sent = is_sent

