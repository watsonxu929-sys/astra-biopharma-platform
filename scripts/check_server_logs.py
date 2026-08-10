import subprocess
import os

os.chdir('e:\\Codex项目设计\\招商一体化平台系统\\biopharma-intelligence-starter')

process = subprocess.Popen(
    ['.venv\\Scripts\\python.exe', '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

import time
time.sleep(5)

import urllib.request
try:
    response = urllib.request.urlopen('http://localhost:8000/platform', timeout=5)
    print(f"Status: {response.status}")
except Exception as e:
    print(f"Request Error: {e}")

process.terminate()
output, _ = process.communicate()
print("\nServer Log:")
print(output)