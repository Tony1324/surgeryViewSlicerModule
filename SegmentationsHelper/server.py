import pyigtl
from transformers import pipeline
from time import sleep

server = pyigtl.OpenIGTLinkServer(port=18944)

def summarizeText(text):
    messages = [
        {"role": "user", "content": text},
    ]
    pipe = pipeline("text-generation", model="Qwen/Qwen2.5-1.5B-Instruct")
    response = pipe(messages, max_new_tokens=1000)
    return response[0]["generated_text"][-1]["content"]

while True:
    if not server.is_connected():
        print("Waiting for connection...")
        sleep(0.1)
    
    messages = server.get_last_messages()
    for message in messages:
        print(message)
        if message.name == "Text":
            text = message.get_string()
            print(f"Received text: {text}")
            summary = summarizeText(text)
            print(f"Summary: {summary}")
            response_message = pyigtl.StringMessage(summary, device_name="TranscriptSummary")
            server.send_message(response_message)

    
