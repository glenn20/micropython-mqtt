# syncom.py Synchronous communication channel between two MicroPython
# platforms. 4 June 2017
# Uses uasyncio.

# The MIT License (MIT)
#
# Copyright (c) 2017-2021 Peter Hinch
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# Timing: was 4.5mS per char between Pyboard and ESP8266 i.e. ~1.55Kbps. But
# this version didn't yield on every bit, invalidating t/o detection.
# New asyncio version yields on every bit.
# Instantaneous bit rate running ESP8266 at 160MHz: 1.6Kbps
# Mean throughput running test programs 8.8ms per char (800bps).

from esp import espnow
import uasyncio as asyncio
from micropython import const
import network
import ujson

class ChannelError(Exception):
    pass

class ChannelESPNow:
    def __init__(self, pmk = None, lmk = None, sync=True, string_mode=True):
        self._iface         = network.WLAN(network.STA_IF)
        self._espnow        = espnow.ESPNow()
        self._sync          = sync
        self._string_mode   = string_mode
        self._running       = False
        self._hosts         = []
        if pmk:
            self._espnow.set_pmk(pmk)

    @property
    def hosts(self):
        return self._hosts

    # Start channel interface
    async def start(self, user_task=None, awaitable=None):
        self._espnow.init()
        self._running = True
        await asyncio.sleep(0)

    # Can be used to force a failure
    def stop(self):
        self._espnow.deinit()
        self._running = False

    # Queue an object for tx. Convert to string NOW: snapshot of current
    # object state
    def send(self, host, obj):
        self._iface.active(True)            # Ensure wifi is active
        if host not in self.hosts:
            self.hosts.append(bytes(host))
            self.espnow.add_peer(host, self._lmk)

        try:
            return self._espnow.send(
                host,
                obj if self._string_mode else ujson.dumps(obj),
                self._sync)
        except OSError('ESP_ERR_ESPNOW_IF'):
            self._iface.active(True)

    # Wait for an object. Return None on timeout.
    # If in string mode returns a string (or None on t/o)
    async def await_obj(self, t_ms=10):
        while self._running:
            msg = self.espnow.irecv(0)  # Timeout set to 0 ms
            if msg is not None:
                host, msg = msg
                if host not in self.hosts:
                    self.hosts.append(bytes(host))
                    self.espnow.add_peer(host, self.lmk)

                return (
                    host,
                    (msg[1].decode('UTF8') if self.string_mode else
                    ujson.loads(msg[1].decode('UTF8'))))
            await asyncio.sleep_ms(t_ms)
        return None

    # running() is False if the target has timed out.
    def running(self):
        return self._running
