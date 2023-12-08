import os
import random
from pathlib import Path
from datetime import datetime

import quixstreams as qx

from huggingface_hub import hf_hub_download

from langchain.llms import LlamaCpp
from langchain.prompts import load_prompt
from langchain.chains import ConversationChain
from langchain_experimental.chat_models import Llama2Chat
from langchain.memory import ConversationTokenBufferMemory

CUSTOMER_ROLE = "customer"

role = CUSTOMER_ROLE
chat_len = 0
chat_maxlen = int(os.environ["conversation_length"]) // 2

model_name = "llama-2-7b-chat.Q4_K_M.gguf"
model_path = "./state/{}".format(model_name)
if not Path(model_path).exists():
    print("The model path does not exist in state. Downloading model...")
    hf_hub_download("TheBloke/Llama-2-7b-Chat-GGUF", model_name, local_dir="state")
else:
    print("Loading model from state...")

def get_list(file: str):
    list = []

    with open(file, "r") as fd:
        for p in fd:
            if p:
                list.append(p.strip())
    return list

moods = get_list("moods.txt")
products = get_list("products.txt")

def chain_init():
    prompt = load_prompt("prompt.yaml")
    prompt.partial_variables["mood"] = random.choice(moods)
    prompt.partial_variables["product"] = random.choice(products)

    print("Prompt:\n{}".format(prompt.to_json()))

    llm = LlamaCpp(
        model_path=model_path,
        max_tokens=250,
        top_p=0.95,
        top_k=150,
        temperature=0.7,
        repeat_penalty=1.2,
        n_ctx=2048,
        streaming=False
    )

    model = Llama2Chat(llm=llm)

    memory = ConversationTokenBufferMemory(
        llm=llm,
        max_token_limit=300,
        ai_prefix= "CUSTOMER",
        human_prefix= "AGENT",
        return_messages=True
    )

    return ConversationChain(llm=model, prompt=prompt, memory=memory)

chain = chain_init()
client = qx.QuixStreamingClient()
topic_producer = client.get_topic_producer(os.environ["topic"])
topic_consumer = client.get_topic_consumer(os.environ["topic"])

def on_stream_recv_handler(sc: qx.StreamConsumer):
    print("Received stream {}".format(sc.stream_id))

    def on_data_recv_handler(_: qx.StreamConsumer, data: qx.TimeseriesData):
        global chain, chat_len

        ts = data.timestamps[0]
        sender = ts.parameters["role"].string_value

        if sender != role:
            chat_len += 1
            
            if chat_len >= chat_maxlen:
                print("Maximum conversation length reached, ending conversation...")

                chat_len = 0
                chain = chain_init()

                td = qx.TimeseriesData()
                td.add_timestamp(datetime.utcnow()) \
                  .add_value("role", role) \
                  .add_value("text", "Noted, I think I have enough information. Thank you for your assistance. Good bye!") \
                  .add_value("conversation_id", ts.parameters["conversation_id"].string_value)

                sp = topic_producer.get_or_create_stream(sc.stream_id)
                sp.timeseries.publish(td)
                return

            msg = ts.parameters["text"].string_value
            print("{}: {}\n".format(sender.upper(), msg))

            print("Generating response...")

            reply = chain.run(msg)
            print("{}: {}\n".format(role.upper(), reply))
            
            td = qx.TimeseriesData()
            td.add_timestamp(datetime.utcnow()) \
              .add_value("role", role) \
              .add_value("text", reply) \
              .add_value("conversation_id", ts.parameters["conversation_id"].string_value)

            sp = topic_producer.get_or_create_stream(sc.stream_id)
            sp.timeseries.publish(td)

    buf = sc.timeseries.create_buffer()
    buf.packet_size = 1
    buf.on_data_released = on_data_recv_handler

topic_consumer.on_stream_received = on_stream_recv_handler

print("Listening to streams. Press CTRL-C to exit.")
qx.App.run()