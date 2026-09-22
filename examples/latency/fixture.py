"""Deterministic synthetic SSE source, never a model-performance simulator."""
import json
import ssl
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def do_POST(self):
    if self.headers.get('Transfer-Encoding','').lower()=='chunked':
      raw=b''
      while True:
        size=int(self.rfile.readline().strip().split(b';')[0],16)
        if not size:self.rfile.readline();break
        raw+=self.rfile.read(size);self.rfile.read(2)
    else:raw=self.rfile.read(int(self.headers.get('Content-Length',0)))
    if self.headers.get('Authorization')!='Bearer synthetic-target-only':
      self.send_response(401);self.end_headers();return
    body=json.loads(raw)
    scenario=body['messages'][0]['content']
    chunks,width=(8,64) if scenario=='short' else (32,512)
    if scenario=='limit':chunks,width=40,1024
    if scenario=='pii':chunks,width=2,1
    self.send_response(200);self.send_header('Content-Type','text/event-stream')
    self.send_header('Connection','close');self.end_headers()
    try:
      if scenario=='timeout':time.sleep(13)
      for index in range(chunks):
        time.sleep(.02)
        text=(['alex@','example.com'][index] if scenario=='pii' else 'safe '*((width+4)//5))
        value={'id':'chatcmpl-fixture','object':'chat.completion.chunk','created':1,'model':body['model'],
          'choices':[{'index':0,'delta':{'content':text},'finish_reason':None}]}
        self.wfile.write(('data: '+json.dumps(value)+'\n\n').encode());self.wfile.flush()
      value['choices']=[{'index':0,'delta':{},'finish_reason':'stop'}]
      self.wfile.write(('data: '+json.dumps(value)+'\n\ndata: [DONE]\n\n').encode());self.wfile.flush()
    except (BrokenPipeError,ConnectionResetError):pass
    self.close_connection=True


if __name__=='__main__':
  class Server(ThreadingHTTPServer):
    request_queue_size=128
    daemon_threads=True
  server=Server(('0.0.0.0',443),Handler)
  context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
  context.load_cert_chain('/fixture/cert.pem','/fixture/key.pem')
  server.socket=context.wrap_socket(server.socket,server_side=True)
  server.serve_forever()
