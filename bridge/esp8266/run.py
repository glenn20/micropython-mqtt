# main.py: run the MQTTProxy

# Author: Glenn Moloney
# Copyright Glenn Moloney 2021 Released under the MIT license

import uasyncio as asyncio
from mqtt_as import config
from mqttproxy import MQTTProxy
from machine import reset as machine_reset
from network import WLAN, STA_IF, AP_IF
from channel_syncom import ChannelSynCom

config.update({
    'ssid':          'Red',
    'wifi_pw':       'violettrombones13',
    'timeserver':    '192.168.40.1',
    'server':        'hassio.lan',
    'port':          1883,
    'user':          'zigbee2mqtt',
    'password':      'purplemirror13',
    'keepalive':     60,
    'ping_interval': 0,
    'ssl':           False,
    'ssl_params':    {},
    'wifi_led_pin':  None,
})

heartbeat_led_pin = None

async def heartbeat():
    if heartbeat_led_pin is None:
        return
    led = Pin(heartbeat_led_pin, Pin.OUT)
    while True:
        await asyncio.sleep_ms(800)
        led(not led())
        await asyncio.sleep_ms(200)
        led(not led())

# Encrytion keys for ESPNow
pmk = b'abcdefghijklmnop'
lmk = b'abcdefghijklmnop'

asyncio.create_task(heartbeat())
app = MQTTProxy([ChannelESPNow(pmk, lmk)], config)
asyncio.run(app.run())
# machine_reset()
