import argparse
import pathlib
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path

import board
import busio
import zmq
from adafruit_ina219 import INA219, ADCResolution, BusVoltageRange
from adafruit_shtc3 import SHTC3
from mu_interface.Utilities.data2csv import data2csv
from mu_interface.Utilities.utils import TimeFormat
from safety_monitor import BatteryVoltageCheck, BatteryLevel, ChargingState, BatteryCurrentCheck, TemperatureCheck


## Parse arguments.
parser = argparse.ArgumentParser(description="Arguments for the sensor node.")
parser.add_argument(
    "--int", action="store", type=int, default=5, help="Time interval between two measurements (in seconds)."
)
parser.add_argument(
    "--addr",
    action="store",
    default="localhost",
    help="Address of the MQTT subscriber. Can be IP, localhost, *.local, etc.",
)
parser.add_argument(
    "--dir", action="store", default=Path.home() / "measurements/", help="Directory where measurement data is saved."
)
args = parser.parse_args()


hostname = socket.gethostname()


## Set up I2C sensors.
i2c_bus = busio.I2C(board.SCL1, board.SDA1)
ina219_solar = INA219(i2c_bus, addr=0x40)
ina219_battery = INA219(i2c_bus, addr=0x41)
try:
    shtc3 = SHTC3(i2c_bus)
    temp_is_available = True
except ValueError:
    temp_is_available = False

# optional : change configuration to use 32 samples averaging for both bus voltage and shunt voltage
ina219_solar.bus_adc_resolution = ADCResolution.ADCRES_12BIT_32S
ina219_solar.shunt_adc_resolution = ADCResolution.ADCRES_12BIT_32S
# optional : change voltage range to 16V
ina219_solar.bus_voltage_range = BusVoltageRange.RANGE_16V
# optional : change configuration to use 32 samples averaging for both bus voltage and shunt voltage
ina219_battery.bus_adc_resolution = ADCResolution.ADCRES_12BIT_32S
ina219_battery.shunt_adc_resolution = ADCResolution.ADCRES_12BIT_32S
# optional : change voltage range to 16V
ina219_battery.bus_voltage_range = BusVoltageRange.RANGE_16V

## Set up csv storing.
file_path = Path(args.dir)
start_time = datetime.now()
print("Measurement started at {}.".format(start_time.strftime(TimeFormat.log)))
print(f"Saving data to: {file_path}")
file_name = f"{hostname}_{start_time.strftime(TimeFormat.file)}.csv"
csv_object = data2csv(file_path, file_name, "energy")
csv_object.fix_ownership()
last_time = datetime.now()

## Monitoring and checking.
voltage_monitor = BatteryVoltageCheck()
current_monitor = BatteryCurrentCheck()
temperature_monitor = TemperatureCheck()

shutdown_script = pathlib.Path.home() / "OrangeBox/scripts/shutdown.sh"

## Set up ZMQ publisher.
zmq_context = zmq.Context()
zmq_socket = zmq_context.socket(zmq.PUB)
zmq_socket.connect("tcp://127.0.0.1:5556")
time.sleep(1)

## Measure and display loop
try:
    while True:
        # Read data from sensor.
        bus_voltage_solar = round(ina219_solar.bus_voltage, 2)        # voltage on V- (load side)
        current_solar = round(ina219_solar.current, 1)                # current in mA
        bus_voltage_battery = round(ina219_battery.bus_voltage, 2)    # voltage on V- (load side)
        current_battery = round(ina219_battery.current, 1)            # current in mA

        voltage_monitor.update(bus_voltage_battery)
        state_changed, battery_level = voltage_monitor.check()
        if state_changed:
            if battery_level == BatteryLevel.CRIT:
                zmq_socket.send_string("Battery Voltage Is Critically Low. Shutting Down!")
                subprocess.run(str(shutdown_script.resolve()), shell=True)
            elif battery_level == BatteryLevel.LOW1:
                zmq_socket.send_string(f"Battery Voltage Is Low (<= {BatteryLevel.LOW1.value} V).")
            elif battery_level == BatteryLevel.LOW2:
                zmq_socket.send_string(f"Battery Voltage Is Low (<= {BatteryLevel.LOW2.value} V).")

        current_monitor.update(current_battery)
        charging_state = current_monitor.check()
        if charging_state == ChargingState.DANGER:
            zmq_socket.send_string("Battery Charging Current Is Unexpectedly High!")

        temperature = 0
        humidity = 0
        if temp_is_available:
            try:
                temperature = round(shtc3.temperature, 2)  # temperature in degrees Celsius
                humidity = round(shtc3.relative_humidity, 2)  # relative humidity in %
                print(f"Temperature: {temperature} °C, Humidity: {humidity} %")
            except Exception as e:
                print(f"Error reading temperature and humidity: {e}")

            if not temperature_monitor.check(temperature):
                zmq_socket.send_string(f"Temperature Inside The Box Is High! ({temperature} °C)")

        # Publish data over ZMQ.
        payload = [
            int(datetime.now().timestamp()),
            bus_voltage_solar,
            current_solar,
            bus_voltage_battery,
            current_battery,
            temperature,
            humidity,
        ]

        # Create a new csv file after the specified interval.
        current_time = datetime.now()
        if current_time.hour in {0, 12} and current_time.hour != last_time.hour:
            print("Creating a new csv file.")
            file_name = f"{hostname}_{current_time.strftime(TimeFormat.file)}.csv"
            csv_object = data2csv(file_path, file_name, "energy")
            csv_object.fix_ownership()
            last_time = current_time

        # Store data to csv file locally.
        try:
            csv_object.write2csv(payload)
        except Exception as e:
            print(f"Writing to csv file failed with error:\n{e}\n\nContinuing because this is not a fatal error.")

        # TODO: add some statistics to print out

        # Check internal calculations haven't overflowed (doesn't detect ADC overflows)
        if ina219_solar.overflow:
            print("Internal Math Overflow Detected!")
            print("")

        time.sleep(args.int)

except KeyboardInterrupt:
    pass
finally:
    zmq_socket.close()
    zmq_context.term()
