# mqtt.py MQTT library for the micropython board using an ESP8266.
# asyncio version

# Author: Peter Hinch
# Copyright Peter Hinch 2017-2021 Released under the MIT license

# Accessed via pbmqtt.py on Pyboard

import gc
import ubinascii
from mqtt_as import MQTTClient, config
from machine import Pin, unique_id, freq, reset as machine_reset
import uasyncio as asyncio
gc.collect()
from network import WLAN, STA_IF, AP_IF
import usocket as socket
gc.collect()
from channel_syncom import ChannelSynCom
gc.collect()
import ustruct as struct
from status_values import *  # Numeric status values shared with user code.

_WIFI_DELAY = 15  # Time (s) to wait for default network
wifi_led_pin = (
    Pin(config['wifi_led_pin'], Pin.OUT, value = 1)
    if 'wifi_led_pin' in config else None)
heartbeat_led_pin = (
    Pin(config['heartbeat_led_pin'], Pin.OUT)
    if 'heartbeat_led_pin' in config else None)

# Format an arbitrary list of positional args as a status_values.SEP separated string
def argformat(*a):
    return SEP.join(['{}' for x in range(len(a))]).format(*a)

async def heartbeat():
    if heartbeat_led_pin is None:
        return
    while True:
        await asyncio.sleep_ms(500)
        heartbeat_led_pin(not heartbeat_led_pin())

class Client(MQTTClient):
    def __init__(self, channels, config):
        self.channels = channels
        # Config defaults:
        # 4 repubs, delay of 10 secs between (response_time).
        # Initially clean session.
        config['subs_cb'] = self.subs_cb
        config['wifi_coro'] = self.wifi_han
        config['connect_coro'] = self.conn_han
        config['client_id'] = ubinascii.hexlify(unique_id())
        self.timeserver = config['timeserver']
        self.subscriptions = {}
        super().__init__(config)

    # Get NTP time or 0 on any error.
    async def get_time(self):
        if not self.isconnected():
            return 0
        res = await self.wan_ok()
        if not res:
            return 0  # No internet connectivity.
        # connectivity check is not ideal. Could fail now... FIXME
        # (date(2000, 1, 1) - date(1900, 1, 1)).days * 24*60*60
        NTP_DELTA = 3155673600
        host = self.timeserver
        NTP_QUERY = bytearray(48)
        NTP_QUERY[0] = 0x1b
        t = 0
        async with self.lock:
            addr = socket.getaddrinfo(host, 123)[0][-1]  # Blocks 15s if no internet
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setblocking(False)
            try:
                s.connect(addr)
                await self._as_write(NTP_QUERY, 48, s)
                await asyncio.sleep(2)
                msg = await self._as_read(48, s)
                val = struct.unpack("!I", msg[40:44])[0]
                t = val - NTP_DELTA
            except OSError:
                pass
            s.close()

        if t < 16 * 365 * 24 * 3600:
            t = 0
        self.dprint('Time received: ', t, ' from:', host)
        return t

    async def wifi_han(self, state):
        for channel in self.channels:
            for host in channel.hosts:
                channel.send(
                    host,
                    argformat(STATUS, WIFI_UP if state else WIFI_DOWN))
        if wifi_led_pin is not None:
            wifi_led_pin(not state)
        await asyncio.sleep(1)

    async def conn_han(self, _):
        for topic, items in self.subscriptions.items():
            for channel, host, qos in items:
                await self.subscribe(topic, qos)

    def subs_cb(self, topic, msg, retained):
        for channel, host, qos in self.subscriptions[topic]:
            channel.send(host, argformat(SUBSCRIPTION, topic.decode('UTF8'), msg.decode('UTF8'), retained))

    # Task runs continuously. Process incoming messages from the channel.
    # Started by main_task() after client instantiated.
    async def from_channel(self, channel):
        while True:
            host, istr = await channel.await_obj(20)  # wait for string (poll interval 20ms)
            s = istr.split(SEP)
            command = s[0]
            if command == PUBLISH:
                await self.publish(s[1], s[2], bool(s[3]), int(s[4]))
                # If qos == 1 only returns once PUBACK received.
                channel.send(host, argformat(STATUS, PUBOK))
            elif command == SUBSCRIBE:
                topic, qos = s[1], int(s[2])
                await self.subscribe(topic, qos)
                if topic not in self.subscriptions:
                    self.subscriptions[topic] = []
                self.subscriptions[topic].append((channel, host, int(s[2])))  # re-subscribe after outage
            elif command == MEM:
                gc.collect()
                gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
                channel.send(host, argformat(MEM, gc.mem_free(), gc.mem_alloc()))
            elif command == TIME:
                t = await self.get_time()
                channel.send(host, argformat(TIME, t))
            elif command == STATUS:
                # A request for status of the broker
                status = (
                    BROKER_OK if self.isconnected() else
                    WIFI_UP if self._sta_if.isconnected() else
                    WIFI_DOWN)
                channel.send(host, argformat(STATUS, status))
            else:
                channel.send(host, argformat(STATUS, UNKNOWN, 'Unknown command:', istr))

    async def main_task(self):
        for channel in self.channels:
            asyncio.create_task(channel.start())

        for i in range(12, 0, -1):
            await asyncio.sleep(5)  # Let WiFi stabilise before connecting
            try:
                await self.connect()  # Clean session. Throws OSError if broker down.
                break
            except OSError:
                if i == 1:
                    for channel in self.channels:
                        for host in channel.hosts:
                            channel.send(host, argformat(STATUS, BROKER_FAIL))
                    # After repeated failures, reboot
                    machine_reset()

        for channel in self.channels:
            for host in channel.hosts:
                channel.send(host, argformat(STATUS, BROKER_OK))
                channel.send(host, argformat(STATUS, RUNNING))
        # Set channel running
        for channel in self.channels:
            asyncio.create_task(self.from_channel(channel))
        while True:
            await asyncio.sleep(1)


# Comms channel to Pyboard and ESPNow clients
client = Client([ChannelSynCom(), ChannelESPNow()], config)
asyncio.create_task(client.main_task())
asyncio.run(heartbeat())
