from quixstreams import SecurityOptions, KafkaStreamingClient
import quixstreams as qx
import os
import pandas as pd


kafka_password = os.environ["kafka_password"]
kafka_username = os.environ["kafka_username"]

security = SecurityOptions("/certs", kafka_username, kafka_password)
client = KafkaStreamingClient('kafka-k1.quix.io:9093,kafka-k2.quix.io:9093,kafka-k3.quix.io:9093', security)

topic_consumer = client.get_topic_consumer(os.environ["input"], consumer_group = "empty-transformation")

def on_stream_received_handler(stream_consumer: qx.StreamConsumer):

    def on_dataframe_received_handler(stream_consumer: qx.StreamConsumer, df: pd.DataFrame):
        print(df)

    def on_event_data_received_handler(stream_consumer: qx.StreamConsumer, data: qx.EventData):
        print(data)

    stream_consumer.events.on_data_received = on_event_data_received_handler # register the event data callback
    stream_consumer.timeseries.on_dataframe_received = on_dataframe_received_handler


# subscribe to new streams being received
topic_consumer.on_stream_received = on_stream_received_handler

print("Listening to streams. Press CTRL-C to exit.")

# Handle termination signals and provide a graceful exit
qx.App.run()