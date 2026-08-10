import urllib.request

try:
    response = urllib.request.urlopen('http://localhost:8000/platform', timeout=10)
    print(f"Status: {response.status}")
    content = response.read()[:500].decode('utf-8', errors='replace')
    print(f"Content: {content}")
except Exception as e:
    print(f"Error: {e}")