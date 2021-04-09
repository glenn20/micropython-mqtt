# mqtt.py MQTT library for the micropython board using an ESP8266.
# asyncio version

# Author: Peter Hinch
# Copyright Peter Hinch 2017-2021 Released under the MIT license

# Accessed via pbmqtt.py on Pyboard

from machine import Pin, unique_id, freq
import uasyncio as asyncio
from syncom import SynCom

class ChannelSynCom(SynCom):
    def __init__(self):
        mtx = Pin(14, Pin.OUT)              # Define pins
        mckout = Pin(15, Pin.OUT, value=0)  # clocks must be initialised to 0
        mrx = Pin(13, Pin.IN)
        mckin = Pin(12, Pin.IN)
        super().__init__(True, mckin, mckout, mrx, mtx, string_mode = True)
        self.cstatus = False  # Connection status
        self._hosts = ["SynCom"]

    def send(self, _, obj):
        # Ignore the "host" argument
        super().send(obj)
