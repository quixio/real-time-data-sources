from bdb import GENERATOR_AND_COROUTINE_FLAGS
import faulthandler
import os
import random
import threading
from threading import Event

from random import  randint
from time import sleep
import logging

# import vendor-specfic modules
from quixstreams import Application
from quixstreams.models.serializers.quix import JSONSerializer, SerializationContext
from faker import Faker

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a Quix Application
app = Application.Quix(consumer_group="machine_generator", auto_create_topics=True)

# Define a serializer for messages, using JSON Serializer for ease
serializer = JSONSerializer()

# Define the topic using the "output" environment variable
topic_name = os.environ["output"]
topic = app.topic(topic_name)

fake = Faker()

machine_id_counter = 1


class machine():
    def __init__ (self) -> None:
        global machine_id_counter
        self.machine_id = "machine" + str(machine_id_counter)
        machine_id_counter+=1
        self.temperature = 0
        self.load = 0
        self.power = 0
        self.vibration = 0
        self.barcode= fake.ean(length=8)
        self.provider=fake.company()
        self.fault = False
        self.previous_fault_state = False

    def toggle_fault(self):
        self.previous_fault_state = self.fault
        self.fault = not self.fault

    def returnMachineID(self):
        return self.machine_id

   
    def returnTemperature(self):
        currentLoad = self.load
        if currentLoad >= 190: self.temperature = randint(95, 120)
        elif currentLoad > 110: self.temperature = randint(80, 90)
        elif currentLoad >= 40: self.temperature = randint(35, 40)
        elif currentLoad > 0: self.temperature = randint(29, 34)
        else: self.temperature = 20
        return self.temperature

    def setLoad(self, load):
        # TODO dont randomise    
        self.load = load
       

    def returnPower(self):
        currentLoad = self.load
        if currentLoad >= 190: self.power = randint(400, 500)
        elif currentLoad > 110: self.power = randint(300, 320)
        elif currentLoad >= 40: self.power = randint(200, 220)
        elif currentLoad == 0: self.power = 0
        else: self.power = randint(180, 199)
        
        return self.power
    
        
    def returnVibration(self):
        currentLoad = self.load
        if currentLoad >= 190: self.vibration = randint(500, 600)
        elif currentLoad > 110: self.vibration = randint(300, 500)
        elif currentLoad == 0: self.vibration  = 0
        elif currentLoad >= 40: self.vibration = randint(80, 90)
        else: self.vibration = randint(50, 79)
        return self.vibration

    def returnMachineHealth(self):
        # trigger load first as needs to be constent:
        return {"metadata":{"machineID": self.returnMachineID(), 
                "barcode": self.barcode, "provider": self.provider}, 
                "data": [ {"temperature": self.returnTemperature()}, 
                         {"load": self.load}, 
                         {"power": self.returnPower()}, 
                         {"vibration": self.returnVibration()}]}



def runMachine(m):
    # KAFKA_BROKER = os.getenv('KAFKA_BROKER', "localhost:9092")
    # KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', "machine_topic")
    counter = 0
    counter2 = 0

    sleeptime = 1
    m.setLoad(randint(10, 50))
    increasing = True
    

    while True:

        # Check if fault state has changed from True to False
        if m.previous_fault_state and not m.fault:
            m.setLoad(50)
            m.previous_fault_state = False

        # Chance of fault
        if m.fault:
            if counter2 == 5:
                current_load = m.load
                if current_load < 200:
                    new_load = min(current_load + 20, 200)
                    m.setLoad(new_load)
                counter2 = 0
        else:
            if counter2 == 5:
                # Gradually change load between 50 and 99
                current_load = m.load
                if increasing:
                    new_load = current_load + 5
                    if new_load >= 99:
                        increasing = False
                else:
                    new_load = current_load - 5
                    if new_load <= 50:
                        increasing = True
                
                m.setLoad(new_load)
                counter2 = 0
        
        message_key = f"INFLUX_DATA_{str(random.randint(1, 100)).zfill(3)}_{counter}"

        # Publish messages to Kafka topic
        check_machine = m.returnMachineHealth()

        with app.get_producer():
            # Serialize row value to bytes
            serialized_value = serializer(
                value=check_machine, ctx=SerializationContext(topic=topic.name)
            )

            # publish the data to the topic
            producer.produce(
                topic=topic.name,
                key=message_key,
                value=serialized_value,
            )
        
        sleep(sleeptime)
        counter = counter + 1
        counter2 = counter2 + 1

def main():
    # Initialize a machine instance
    m = machine()

    # Start running the machine to produce data
    runMachine(m)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Exiting.")


