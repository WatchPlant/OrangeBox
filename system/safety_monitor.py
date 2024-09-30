import enum
from collections import deque
from datetime import datetime, timedelta


class BatteryLevel(enum.Enum):
    OK = None
    CRIT = 3.5
    LOW1 = 3.7
    LOW2 = 3.6
    RECOVER = 3.8


class BatteryVoltageCheck(object):
    def __init__(self, history_len=10):
        self.buffer = deque(maxlen=history_len)
        self.status = BatteryLevel.OK

    def update(self, value):
        self.buffer.append(value)

    def check(self):
        if all(val < BatteryLevel.CRIT.value for val in self.buffer):
            self.status = BatteryLevel.CRIT
        elif self.status == BatteryLevel.OK and all(val < BatteryLevel.LOW1.value for val in self.buffer):
            self.status = BatteryLevel.LOW1
        elif self.status == BatteryLevel.LOW1 and all(val < BatteryLevel.LOW2.value for val in self.buffer):
            self.status = BatteryLevel.LOW2
        elif self.status in [BatteryLevel.LOW1, BatteryLevel.LOW2] \
                and all(val > BatteryLevel.RECOVER.value for val in self.buffer):
            self.status = BatteryLevel.OK

        return self.status


class ChargingState(enum.Enum):
        DEFAULT = "DEFAULT"
        CHARGING = "CHARGING"
        DANGER = "DANGER"


class BatteryCurrentCheck(object):
    def __init__(self, history_len=12, min_wait=timedelta(hours=1), max_current=70) -> None:
        self.short_buffer = deque(maxlen=history_len)  # Used as a running filter.
        self.long_buffer = deque(maxlen=history_len)   # Used to check for long-term charging problems.

        self.last_update = None
        self.min_wait = min_wait
        self.max_current = max_current

    def update(self, value):
        self.short_buffer.append(value)

        if self.last_update is None or (datetime.now() - self.last_update) >= self.min_wait:
            self.long_buffer.append(sum(self.short_buffer) / len(self.short_buffer))
            self.last_update = datetime.now()

    def check(self):
        charging_state = ChargingState.CHARGING if sum(self.short_buffer) > 0 else ChargingState.DEFAULT

        # If charging current is above 70 mA for a long time, it might be a problem.
        # The battery should get charged and the current should drop to a lower value.
        if len(self.long_buffer) == self.long_buffer.maxlen and all(val > self.max_current for val in self.long_buffer):
            charging_state = ChargingState.DANGER
            self.long_buffer[0] = 0

        return charging_state


class TemperatureCheck(object):
    def __init__(self, max_rate=timedelta(hours=3), max_temp=60) -> None:
        self.last_update = None
        self.max_rate = max_rate
        self.max_temp = max_temp

    def check(self, value):
        if self.last_update is None:
            self.last_update = datetime.now()

        if (datetime.now() - self.last_update) > self.max_rate and value > self.max_temp:
            self.last_update = datetime.now()
            return False

        return True

