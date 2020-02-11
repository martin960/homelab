#!/usr/bin/env python3


import re
import time

from bluepy import btle

from influxdb import InfluxDBClient

INFLUXDB_ADDRESS = 'XXXXXXXXX'
INFLUXDB_DATABASE = 'temp_sensors'

influxdb_client = InfluxDBClient(INFLUXDB_ADDRESS, 8086, None)

MIJIA_BTLE_ADDRESS = '58:2D:34:35:96:1D'

MIJIA_BATTERY_SERVICE_UUID = btle.UUID('180f')
MIJIA_BATTERY_CHARACTERISTIC_UUID = btle.UUID('2a19')

MIJIA_DATA_SERVICE_UUID = btle.UUID('226c0000-6476-4566-7562-66734470666d')
MIJIA_DATA_CHARACTERISTIC_UUID = btle.UUID('226caa55-6476-4566-7562-66734470666d')
MIJIA_DATA_CHARACTERISTIC_HANDLE = 0x0010

BTLE_SUBSCRIBE_VALUE = bytes([0x01, 0x00])
BTLE_UNSUBSCRIBE_VALUE = bytes([0x00, 0x00])

battery = None
temperature = None
humidity = None


class MyDelegate(btle.DefaultDelegate):
    def __init__(self):
        btle.DefaultDelegate.__init__(self)

    def handleNotification(self, cHandle, data):
        fetch_sensor_data(bytearray(data).decode('utf-8'))


def main():
        
        while True:

            try:

                _init_influxdb_database()
                print('Connecting to ' + MIJIA_BTLE_ADDRESS)
                dev = btle.Peripheral(MIJIA_BTLE_ADDRESS)
                print('Set delegate')
                dev.setDelegate(MyDelegate())

                # Get battery level
                if battery is None:
                    fetch_battery_level(dev)
                    print('Battery level: ' + str(battery))

                # Subscribe to data characteristic
                if temperature is None or humidity is None:
                    dev.writeCharacteristic(MIJIA_DATA_CHARACTERISTIC_HANDLE, BTLE_SUBSCRIBE_VALUE, True)
                    while True:
                        if dev.waitForNotifications(1.0):
                            print('Temperature: ' + temperature)
                            print('Humidity: ' + humidity)
                            dev.writeCharacteristic(MIJIA_DATA_CHARACTERISTIC_HANDLE, BTLE_UNSUBSCRIBE_VALUE, True)
                            dev.disconnect()
                            break

            #exception
            except (btle.BTLEDisconnectError, IOError):
                print("Disconnected :)")


            #send to influx
            if battery is not None and temperature is not None and humidity is not None:
                _send_sensor_data_to_influxdb("Temperature",float(temperature))
                _send_sensor_data_to_influxdb("Humidity",float(humidity))
                _send_sensor_data_to_influxdb("Bat_lvl",float(battery))
                reset_variables()
                break

def reset_variables():
    global battery
    global temperature
    global humidity

    battery = None
    temperature = None
    humidity = None


def fetch_battery_level(dev):
    global battery

    battery_service = dev.getServiceByUUID(MIJIA_BATTERY_SERVICE_UUID)
    battery_characteristic = battery_service.getCharacteristics(MIJIA_BATTERY_CHARACTERISTIC_UUID)[0]
    battery = ord(battery_characteristic.read())


def fetch_sensor_data(temp_hum):
    global temperature
    global humidity

    pattern = re.compile('T=([\d.-]+) H=([\d.-]+)')
    match = re.match(pattern, temp_hum)
    if match:
        temperature = match.group(1)
        humidity = match.group(2)

def _send_sensor_data_to_influxdb(measure,value):
    json_body = [
        {
            'measurement': measure,
            'tags': {
                'location': "Aussen"
            },
            'fields': {
                'value': value
            }
        }
    ]
    influxdb_client.write_points(json_body)


def _init_influxdb_database():
    databases = influxdb_client.get_list_database()
    if len(list(filter(lambda x: x['name'] == INFLUXDB_DATABASE, databases))) == 0:
        influxdb_client.create_database(INFLUXDB_DATABASE)
    influxdb_client.switch_database(INFLUXDB_DATABASE)


if __name__ == '__main__':
    print('Starting MiJia GATT client')
    main()
