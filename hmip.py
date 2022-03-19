import json
import io
import ssl
import wifi
import socketpool
import adafruit_requests

import adafruit_minimqtt.adafruit_minimqtt as MQTT
import adafruit_logging as logging

from secrets import secrets


LOGGER = logging.getLogger('HMIP')

REST_SERVER = ''
REST_ENDPOINT = '{}/device/{}/{}/~pv'
MQTT_TOPIC = 'device/status/{}/{}'


class HMIPInfo:
    def __init__(self, name, did):
        self._did = did
        self._name = name
        self._topic = MQTT_TOPIC.format(did,self._topic_part)
        self._value = None
        self._dirty = True

    def text(self):
        return self._name

    def query_state(self, session):
        global REST_SERVER
        url = REST_ENDPOINT.format(REST_SERVER, self._did, self._topic_part)
        if session:
            response = session.get(url)
            self.process_message(response.text)

    def topic(self):
        return self._topic

    def value(self):
        self._dirty = False
        return self._value

    def _translate_value(self, value):
        return True if value else False

    def process_message(self, msg):
        value = self._translate_value(json.loads(msg)['v'])
        changed = False
        if self._value != value or self._value   == None:
            self._value = value
            self._dirty = True
            changed = True
        return changed

class HeatingCircuit(HMIPInfo):
    def __init__(self, name, did):
        self._topic_part = 'STATE'
        super().__init__(name, did)


class SWDM(HMIPInfo):
    def __init__(self, name, did):
        self._topic_part = 'STATE'
        super().__init__(name, did)


class WTH(HMIPInfo):
    def __init__(self, name, did):
        self._topic_part = 'ACTUAL_TEMPERATURE'
        super().__init__(name, did)

    def _translate_value(self, value):
        return round(value, 1)

    def text(self):
        return '{} {}'.format(self._name, self._value)


class HMIP:
    def __init__(self):
        import config
        global REST_SERVER

        REST_SERVER = 'http://{}:{}'.format(secrets['server'], secrets['rest_port'])
        self._heating_circuits = [ HeatingCircuit(item[0], item[1]) for item in config.HC.items() ]
        LOGGER.info('found %i heating circuits' % len(self._heating_circuits))
        self._swdms = [ SWDM(item[0], item[1]) for item in config.SWDM.items() ]
        LOGGER.info('found %i SWDMs' % len(self._swdms))
        self._wths = [ WTH(item[0], item[1]) for item in config.WTH.items() ]
        LOGGER.info('found %i WTH' % len(self._wths))
        self._hk_dirty = True
        self._swdm_dirty = True

        self._subscriptions = dict()
        for hc in self._heating_circuits:
            self._subscriptions[hc.topic()] = hc

        for swdm in self._swdms:
            self._subscriptions[swdm.topic()] = swdm

        for wth in self._wths:
            self._subscriptions[wth.topic()] = wth

        self._pool = socketpool.SocketPool(wifi.radio)
        self._ssl_context = ssl.create_default_context()
        self._mqtt_client = MQTT.MQTT(
            broker=secrets['server'],
            port=secrets['mqtt_port'],
            socket_pool=self._pool,
            ssl_context=self._ssl_context,
        )
        self._mqtt_client.on_connect = self._connected
        self._mqtt_client.on_disconnect = self._disconnected
        self._mqtt_client.on_message = self._message

        try:
            wifi.radio.connect(secrets['ssid'], secrets['password'])
            self._session = adafruit_requests.Session(self._pool, self._ssl_context)
            session = self._session

            for hk in self._heating_circuits:
                hk.query_state(session)

            for s in self._swdms:
                s.query_state(session)

            for w in self._wths:
                w.query_state(session)

        except Exception as ex:
            LOGGER.error('Failed to connect to mqtt broker')
            LOGGER.info(str(ex))

    def is_dirty(self):
        return self._hk_dirty and self._swdm_dirty

    def get_current_windows_state(self):
        self._swdm_dirty = False
        return all(not swdm.value() for swdm in self._swdms)

    def get_current_heating_state(self):
        self._hk_dirty = False
        return all(not hk.value() for hk in self._heating_circuits)

    def _connected(self, client, userdata, flags, rc):
        LOGGER.info('Connected to MQTT broker!')
        for topic in self._subscriptions:
            self._mqtt_client.subscribe(topic)

    def _disconnected(self, client, userdata, rc):
        LOGGER.info('Disconnected from MQTT broker!')

    def _message(self, client, topic, message):
        binfo = self._subscriptions[topic]
        changed = binfo.process_message(message)
        if changed:
            if type(binfo) == SWDM:
                self._swdm_dirty = True
            elif type(binfo) == HeatingCircuit:
                self._hk_dirty = True

    def mqtt_client_loop(self):
        try:
            self._mqtt_client.is_connected()
            self._mqtt_client.loop()
        except (MQTT.MMQTTException) as mqttex:
            LOGGER.debug(str(mqttex))
            self._mqtt_client.reconnect()
        except (ValueError, RuntimeError, AttributeError) as ex:
            LOGGER.error('Failed retrieving data. Try to reconnect')
            LOGGER.debug(str(ex))
            self._mqtt_client.reconnect()
