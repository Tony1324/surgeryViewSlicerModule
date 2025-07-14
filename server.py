from transformers import pipeline
from http.server import HTTPServer, BaseHTTPRequestHandler

pipe = pipeline("text-generation", model="mistralai/Mistral-7B-Instruct-v0.3")

def summarizeText(text):
    messages = [
        {"role": "system", "content": "You are part of a medical software, a visualization tool that helps surgeons explain to patients their upcoming procedure. You are provided a transcript of their conversation during a session. Provide a brief paragraph summary of the conversation, then generate a list of important questions in detail together with their responses. If the transcript is too short to provide sufficient summary or questions, reduce length of output and do not speculate. Output in valid markdown without other formatting."},
        {"role": "user", "content": text},
    ]
    response = pipe(messages, max_new_tokens=1000)
    return response[0]["generated_text"][-1]["content"]

class SummarizationHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        input_data = self.rfile.read(content_length).decode('utf-8')

        summary = summarizeText(input_data)

        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(summary.encode('utf-8'))

def run(server_class=HTTPServer, handler_class=SummarizationHandler, port=18944):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"LLM Summarization running on port {port}...")
    httpd.serve_forever()

run()

