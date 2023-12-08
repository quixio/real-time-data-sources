import quixstreams as qx
import pandas as pd


class QuixFunction:
    def __init__(self, consumer_stream: qx.StreamConsumer, producer_stream: qx.StreamProducer):
        self.consumer_stream = consumer_stream
        self.producer_stream = producer_stream

    # Callback triggered for each new event
    def on_event_data_handler(self, stream_consumer: qx.StreamConsumer, data: qx.EventData):
        print(data.value)

        # Transform your data here.

        self.producer_stream.events.publish(data)

    # Callback triggered for each new timeseries data
    def on_dataframe_handler(self, stream_consumer: qx.StreamConsumer, df: pd.DataFrame):
        
        df["quix"] = "This data source is provided for free by Quix. Goto https://quix.io for more information."

        self.producer_stream.timeseries.buffer.publish(df)
