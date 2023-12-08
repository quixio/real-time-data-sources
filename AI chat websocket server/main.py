from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect
import json
import os
import uuid
import pandas as pd
import quixstreams as qx
import asyncio
import uvicorn


app = FastAPI()

# track the connections to our websocket
websocket_connections_timeseries = []
websocket_connections_events = []


def on_dataframe_received_handler(_: qx.StreamConsumer, df: pd.DataFrame):
    global websocket_connections_timeseries

    # Convert the 'timestamp' column to a datetime object
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ns')

    # Convert the datetime object to a UTC timestamp
    df['datetime'] = df['datetime'].dt.tz_localize('UTC')

    if len(websocket_connections_timeseries) > 0:
        for _, row in df.iterrows():
            data = row.to_json()
            for ws in websocket_connections_timeseries:
                ws.send_text(data)


def on_event_received_handler(_: qx.StreamConsumer, event: qx.EventData):
    global websocket_connections_events

    if len(websocket_connections_events) > 0:
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


# this is the handler for new data streams on the broker
def on_stream_received_handler(stream_consumer: qx.StreamConsumer):
    # connect the data handler
    stream_consumer.timeseries.on_dataframe_received = on_dataframe_received_handler
    stream_consumer.events.on_data_received = on_event_received_handler


@app.websocket("/ws/timeseries")
async def websocket_endpoint_timeseries(websocket: WebSocket):
    await websocket.accept()
    websocket_connections_timeseries.append(websocket)
    try:
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        if websocket in websocket_connections_timeseries:
            websocket_connections_timeseries.remove(websocket)


@app.websocket("/ws/events")
async def websocket_endpoint_events(websocket: WebSocket):
    await websocket.accept()
    websocket_connections_events.append(websocket)
    try:
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        if websocket in websocket_connections_events:
            websocket_connections_events.remove(websocket)


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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)