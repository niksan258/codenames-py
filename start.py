import subprocess,sys,os,time

PY=sys.executable
CWD=os.path.dirname(os.path.abspath(__file__))

clients=[
("Gosho","red_spymaster"),
("Pesho","blue_spymaster"),
("Ivan","red_agent"),
("Dragan","red_agent"),
("Petkan","blue_agent"),
("Mitko","blue_agent"),
]

subprocess.Popen([PY,"server.py"],cwd=CWD)
time.sleep(0.2)

for n,r in clients:
    subprocess.Popen([PY,"client.py",r,n],cwd=CWD)
    time.sleep(0.2)
