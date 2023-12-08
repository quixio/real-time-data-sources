import json
import os
import uuid

import pandas as pd
import quixstreams as qx
from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect

app = FastAPI()

# track the connections to our websocket
websocket_connections = []
websocket_connections_events = []
websocket_connections_timeseries = []


def on_dataframe_received_handler(_: qx.StreamConsumer, df: pd.DataFrame):
    global websocket_connections, websocket_connections_timeseries

    # Convert the 'timestamp' column to a datetime object
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ns')

    # Convert the datetime object to a UTC timestamp
    df['datetime'] = df['datetime'].dt.tz_localize('UTC')

    if len(websocket_connections) + len(websocket_connections_timeseries) > 0:
        for _, row in df.iterrows():
            data = row.to_json()
            for ws in websocket_connections:
                ws.send_text(data)
            for ws in websocket_connections_timeseries:
                ws.send_text(data)


def on_event_received_handler(_: qx.StreamConsumer, event: qx.EventData):
    global websocket_connections, websocket_connections_events

    if len(websocket_connections_events) + len(websocket_connections) > 0:
        data = json.dumps(
            {
                "id": event.id,
                "timestamp": event.timestamp.timestamp(),
                "content": event.value,
                "tags": event.tags
            }
        )
        for ws in websocket_connections_events:
            ws.send_text(data)
        for ws in websocket_connections:
            ws.send_text(data)


# this is the handler for new data streams on the broker
def on_stream_received_handler(stream_consumer: qx.StreamConsumer):
    # connect the data handler
    stream_consumer.timeseries.on_dataframe_received = on_dataframe_received_handler
    stream_consumer.events.on_data_received = on_event_received_handler


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Store the WebSocket connection for later use
    await websocket.accept()
    print("Client connected to socket.")

    if websocket.url.path.endswith("/events"):
        print("Client connected to events socket")
        websocket_connections_events.append(websocket)
    elif websocket.url.path.endswith("/timeseries"):
        print("Client connected to timeseries socket")
        websocket_connections_timeseries.append(websocket)
    else:
        websocket_connections.append(websocket)

    i = len(websocket_connections) + len(websocket_connections_events) + len(websocket_connections_timeseries)
    print(F"{i} active connection{'s'[:i ^ 1]}")

    try:
        # Keep the connection open and wait for messages if needed
        print("Keep the connection open and wait for messages if needed")
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        print("Client disconnected.")
    finally:
        # Remove the connection from the list when it's closed
        print("Removing client from connection list")
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)


# Quix client
client = qx.QuixStreamingClient()
# the topic consumer, configured to read only the latest data
topic_consumer = client.get_topic_consumer(
    topic_id_or_name=os.environ["input"],
    consumer_group="websocket-" + str(uuid.uuid4()),
    auto_offset_reset=qx.AutoOffsetReset.Latest)

# connect the stream received handler
topic_consumer.on_stream_received = on_stream_received_handler

# subscribe to data arriving at the topic_consumer
topic_consumer.subscribe()