"""Actual SSH transport for emulator tests. Synthetic GPUs; never uses production credentials."""
import argparse,base64,hashlib,json,re,socket,threading,time
from pathlib import Path
import paramiko

ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=41722);parser.add_argument('--key',default='build/mobile-ssh-host.pem');parser.add_argument('--events',default='build/mobile-ssh-events.json');args=parser.parse_args()
keyfile=ROOT/args.key;keyfile.parent.mkdir(parents=True,exist_ok=True)
if not keyfile.exists():paramiko.RSAKey.generate(2048).write_private_key_file(str(keyfile))
key=paramiko.RSAKey.from_private_key_file(str(keyfile))
clientfile=ROOT/'build/mobile-ssh-client.pem'
if not clientfile.exists():paramiko.RSAKey.generate(2048).write_private_key_file(str(clientfile),password='fixture-key-passphrase')
clientkey=paramiko.RSAKey.from_private_key_file(str(clientfile),password='fixture-key-passphrase')
events={'passwordAttempts':0,'passwordAccepted':0,'keyAttempts':0,'keyAccepted':0,'commands':0,'probeVerified':0}
(ROOT/args.events).write_text(json.dumps(events),encoding='utf-8')
lock=threading.Lock()
def event(name):
 with lock:
  events[name]+=1;(ROOT/args.events).write_text(json.dumps(events),encoding='utf-8')
def sample():
 try:mode=json.loads((ROOT/'build/mobile-ssh-control.json').read_text()).get('mode','gpu')
 except (OSError,ValueError):mode='gpu'
 now=time.time()
 if mode=='cpu':return {'timestamp':now,'gpus':[],'processes':[],'driver':'N/A','cuda':'N/A','gpu_status':'no_gpu','notice':'真实 SSH 测试连接；模拟无 GPU Linux 样本'}
 gpus=[]
 for index,used,util,total in [(0,14720,91,24576),(2,32,0,81920)]:
  gpus.append(dict(index=index,uuid=f'FIXTURE-{index}',name='NVIDIA A100-SXM4-80GB' if index==2 else 'GeForce RTX 4090',util=util,mem_util=64 if index==0 else 0,used=used,total=total,free=total-used,temp=66 if index==0 else 34,power=312.5 if index==0 else 29.,compute_mode='Default',mig_mode='Disabled',process_query_ok=True,device_access=True))
 return dict(timestamp=now,gpus=gpus,processes=[dict(uuid='FIXTURE-0',gpu=0,pid='12345',kind='C',name='python',memory=14720,user='mobile-test',uid=1000,ppid='12340',cwd='/home/mobile-test/experiments/read-only',exe='/usr/bin/python3')],driver='580.178.04',cuda='13.0',gpu_status='available',notice='真实 SSH 传输；GPU 数据为测试样本')
class Server(paramiko.ServerInterface):
 def check_auth_password(self,username,password):
  event('passwordAttempts');valid=(username,password)==('mobile-test','mobile-test-only')
  if valid:event('passwordAccepted')
  return paramiko.AUTH_SUCCESSFUL if valid else paramiko.AUTH_FAILED
 def check_auth_publickey(self,username,key):
  event('keyAttempts');valid=username=='mobile-test' and key==clientkey
  if valid:event('keyAccepted')
  return paramiko.AUTH_SUCCESSFUL if valid else paramiko.AUTH_FAILED
 def get_allowed_auths(self,username):return 'publickey,password'
 def check_channel_request(self,kind,chanid):return paramiko.OPEN_SUCCEEDED if kind=='session' else paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
 def check_channel_exec_request(self,channel,command):
  match=re.search(rb"b64decode\('([^']+)'\)",command)
  if not match or base64.b64decode(match[1])!=(ROOT/'src/remote_probe.py').read_bytes():return False
  event('commands');event('probeVerified')
  def send():
   try:
    while not channel.closed:channel.sendall(('GPUCHECK:'+json.dumps(sample())+'\n').encode());time.sleep(1)
   except (OSError,EOFError):pass
  threading.Thread(target=send,daemon=True).start();return True
def serve(connection):
 transport=paramiko.Transport(connection);transport.add_server_key(key)
 try:
  transport.start_server(server=Server())
  channels=[]
  while transport.is_active():
   channel=transport.accept(2)
   if channel:channels.append(channel)
   channels=[c for c in channels if not c.closed]
 except (paramiko.SSHException,OSError,EOFError):pass
 finally:transport.close()
listener=socket.socket();listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);listener.bind(('127.0.0.1',args.port));listener.listen(10)
print('Local test SSH listening:',args.port,'(synthetic GPU data)',flush=True)
while True:
 connection,_=listener.accept();threading.Thread(target=serve,args=(connection,),daemon=True).start()
