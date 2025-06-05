import pyigtl
from transformers import pipeline
from time import sleep

pipe = pipeline("text-generation", model="Qwen/Qwen2.5-1.5B-Instruct")

def summarizeText(text):
    messages = [
        {"role": "user", "content": text},
    ]
    response = pipe(messages, max_new_tokens=1000)
    return response[0]["generated_text"][-1]["content"]

server = pyigtl.OpenIGTLinkServer(port=18944)

while True:
    if not server.is_connected():
        sleep(0.1)
        continue
    
    messages = server.get_latest_messages()
    for message in messages:
        print(message)
        if message.device_name == "Transcript":
            text = message.string
            print(f"Received text: {text}")
            summary = summarizeText(text)
            print(f"Summary: {summary}")
            response_message = pyigtl.StringMessage(summary.encode('unicode_escape').decode('utf-8'), device_name="TranscriptS")
            server.send_message(response_message)

    

