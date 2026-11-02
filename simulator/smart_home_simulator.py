#!/usr/bin/env python3

import random
import threading
import time

import paho.mqtt.client as mqtt

LIGHTS = ["living_room_light", "bedroom_light", "kitchen_light"]


def make_client(client_id):
    """paho-mqtt 2.x вимагає версію callback API, 1.x її не знає."""
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id)
    except AttributeError:
        return mqtt.Client(client_id)


class SmartHomeSimulator:
    def __init__(self, broker_host="localhost", broker_port=1883):
        self.client = make_client("smart_home_simulator")
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.running = False
        self.devices_state = {
            "living_room_light": {"power": False, "brightness": 50},
            "bedroom_light": {"power": False, "brightness": 70},
            "kitchen_light": {"power": False, "brightness": 60},
            "thermostat": {"current_temp": 21.0, "target_temp": 22.0, "heating": False},
            "motion_detector": {"motion": False, "battery": 95},
            "door_sensor": {"open": False, "battery": 88},
            "smart_socket": {"power": False, "consumption": 0},
        }

    # ------------------------------------------------------------------ MQTT
    def publish(self, topic, payload):
        self.client.publish(topic, payload, retain=True)

    def on_connect(self, client, userdata, flags, rc, *args):
        print(f"Підключено до MQTT брокера (код: {rc})")
        # Підписка на команди керування
        client.subscribe("smarthome/+/set")
        client.subscribe("smarthome/+/+/set")

    def on_message(self, client, userdata, msg):
        topic_parts = msg.topic.split("/")
        device = topic_parts[1]
        channel = topic_parts[2] if len(topic_parts) == 4 else None
        command = msg.payload.decode()

        print(f"Команда: {device}{'/' + channel if channel else ''} -> {command}")
        self.handle_command(device, command, channel)

    def handle_command(self, device, command, channel=None):
        """Обробка команд керування пристроями"""
        if device in LIGHTS:
            state = self.devices_state[device]
            if channel == "brightness":
                if command in ("ON", "OFF"):
                    state["power"] = command == "ON"
                elif command.replace(".", "", 1).isdigit():
                    level = max(0, min(100, int(float(command))))
                    state["brightness"] = max(level, 1) if level else state["brightness"]
                    state["power"] = level > 0
            elif command in ("ON", "OFF"):
                state["power"] = command == "ON"
            self.publish_device_state(device)

        elif device == "thermostat" and command.replace(".", "", 1).isdigit():
            self.devices_state["thermostat"]["target_temp"] = float(command)
            self.publish_device_state("thermostat")

        elif device == "smart_socket" and command in ("ON", "OFF"):
            self.devices_state[device]["power"] = command == "ON"
            if command == "OFF":
                self.devices_state[device]["consumption"] = 0
            self.publish_device_state(device)

    def connect(self):
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(self.broker_host, self.broker_port, 60)
        self.client.loop_start()
        self.running = True

    # ------------------------------------------------------------ публікація
    def publish_device_state(self, device):
        """Публікація стану пристрою"""
        state = self.devices_state[device]

        if device in LIGHTS:
            self.publish(f"smarthome/{device}/state", "ON" if state["power"] else "OFF")
            self.publish(f"smarthome/{device}/brightness", state["brightness"])

        elif device == "thermostat":
            self.publish("smarthome/thermostat/current_temp", f"{state['current_temp']:.1f}")
            self.publish("smarthome/thermostat/target_temp", f"{state['target_temp']:.1f}")
            self.publish("smarthome/thermostat/heating", "ON" if state["heating"] else "OFF")

        elif device == "smart_socket":
            self.publish("smarthome/smart_socket/state", "ON" if state["power"] else "OFF")
            self.publish("smarthome/smart_socket/power", state["consumption"])

        elif device == "motion_detector":
            self.publish("smarthome/motion_detector/state", "ON" if state["motion"] else "OFF")

        elif device == "door_sensor":
            self.publish("smarthome/door_sensor/state", "OPEN" if state["open"] else "CLOSED")

    # ------------------------------------------------------------ симуляції
    def lighting_simulator(self):
        """Симуляція освітлення: невеликі коливання яскравості увімкнених ламп"""
        while self.running:
            for device in LIGHTS:
                if self.devices_state[device]["power"]:
                    current = self.devices_state[device]["brightness"]
                    change = random.randint(-5, 5)
                    self.devices_state[device]["brightness"] = max(10, min(100, current + change))
                    self.publish_device_state(device)
            time.sleep(60)  # Оновлення кожну хвилину

    def climate_simulator(self):
        """Симуляція термостата"""
        while self.running:
            thermostat = self.devices_state["thermostat"]
            current = thermostat["current_temp"]
            target = thermostat["target_temp"]

            if current < target - 0.5:
                thermostat["heating"] = True
                current += random.uniform(0.1, 0.3)
            elif current > target + 0.5:
                thermostat["heating"] = False
                current -= random.uniform(0.1, 0.2)
            else:
                current += random.uniform(-0.1, 0.1)

            thermostat["current_temp"] = current
            self.publish_device_state("thermostat")
            time.sleep(30)  # Оновлення кожні 30 секунд

    def sensors_simulator(self):
        """Симуляція датчиків"""
        while self.running:
            # Датчик руху - випадкове спрацювання
            if random.random() < 0.1:  # 10% ймовірність
                self.devices_state["motion_detector"]["motion"] = True
                self.publish_device_state("motion_detector")
                print("Виявлено рух!")
                threading.Timer(5.0, self.reset_motion).start()  # скидання через 5 с

            # Датчик дверей - рідкісні зміни
            if random.random() < 0.05:  # 5% ймовірність
                door = self.devices_state["door_sensor"]
                door["open"] = not door["open"]
                self.publish_device_state("door_sensor")
                print(f"Двері {'відчинено' if door['open'] else 'зачинено'}")

            # Розумна розетка - імітація споживання
            socket = self.devices_state["smart_socket"]
            if socket["power"]:
                socket["consumption"] = random.randint(50, 200)  # Вт
                self.publish("smarthome/smart_socket/power", socket["consumption"])

            time.sleep(10)  # Оновлення кожні 10 секунд

    def reset_motion(self):
        """Скидання датчика руху"""
        self.devices_state["motion_detector"]["motion"] = False
        self.publish_device_state("motion_detector")

    # ---------------------------------------------------------------- запуск
    def extra_simulators(self):
        """Місце для додаткових потоків (завдання 8.1)."""
        return []

    def start_simulation(self):
        """Запуск симуляції"""
        print("Запуск симулятора розумного будинку...")
        self.connect()

        # Публікація початкових станів
        for device in self.devices_state:
            self.publish_device_state(device)

        # Запуск симуляторів в окремих потоках
        targets = [self.lighting_simulator, self.climate_simulator, self.sensors_simulator]
        targets += self.extra_simulators()
        for target in targets:
            threading.Thread(target=target, daemon=True).start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Зупинка симуляторів...")
            self.running = False
            self.client.loop_stop()
            self.client.disconnect()


if __name__ == "__main__":
    simulator = SmartHomeSimulator()
    simulator.start_simulation()
