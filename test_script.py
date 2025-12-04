import requests
import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Configuration
MODERATION_SERVICE_URL = "http://localhost:8000/moderate"
CALLBACK_PORT = 8888
#CALLBACK_URL = f"http://host.docker.internal:{CALLBACK_PORT}" # For Docker (Mac/Windows)
# CALLBACK_URL = f"http://localhost:{CALLBACK_PORT}" # For local development without Docker or Linux Docker with host network
CALLBACK_URL = "http://172.17.0.1:8888" 

# Store received callbacks
received_callbacks = []

class CallbackHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        print(f"\n[CALLBACK RECEIVED] ID: {data.get('id')}")
        print(json.dumps(data, indent=2))
        
        received_callbacks.append(data)
        
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        return # Silence server logs

def start_callback_server():
    server = HTTPServer(('0.0.0.0', CALLBACK_PORT), CallbackHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    print(f"[*] Callback server listening on port {CALLBACK_PORT}")
    return server

def test_moderation():
    # 1. Start callback server
    start_callback_server()

    # Test cases
    test_cases = [
        {
            "id": "msg_safe_1",
            "text": "Hei, mitä kuuluu? Tämä on tavallinen viesti.",
            "expected": "allow"
        },
        {
            "id": "msg_toxic_1",
            "text": "Opettajat on tosi tyhmiä",
            "expected": "block" # Likely block due to high toxicity
        },
        {
            "id": "msg_badword_fi",
            "text": "Haista viddu",
            "expected": "block" # Should catch finnish badword
        },
        {
            "id": "msg_trivial",
            "text": ".",
            "expected": "allow" # Trivial
        }
    ]

    print(f"\n[*] Sending {len(test_cases)} test requests to {MODERATION_SERVICE_URL}...")

    # 2. Send requests
    for case in test_cases:
        payload = {
            "id": case["id"],
            "text": case["text"],
            "callback_url": CALLBACK_URL
        }
        
        try:
            response = requests.post(MODERATION_SERVICE_URL, json=payload, timeout=5)
            if response.status_code == 200:
                print(f"[SENT] {case['id']}: Queued successfully")
            else:
                print(f"[ERROR] {case['id']}: Failed with status {response.status_code}")
                print(response.text)
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
            print("Make sure the service is running!")
            return

    # 3. Wait for results
    print("\n[*] Waiting for callbacks (10s timeout)...")
    start_time = time.time()
    while len(received_callbacks) < len(test_cases):
        if time.time() - start_time > 10:
            print("[TIMEOUT] Did not receive all callbacks.")
            break
        time.sleep(0.5)

    # 4. Summary
    print("\n" + "="*30)
    print("TEST SUMMARY")
    print("="*30)
    
    for case in test_cases:
        result = next((r for r in received_callbacks if r["id"] == case["id"]), None)
        status = "MISSING"
        decision = "N/A"
        
        if result:
            decision = result["decision"]
            # Rough check: allow matches allow, block/flag matches block/flag intent
            # Adjust expectations based on strictness
            if decision == case["expected"] or (case["expected"] == "block" and decision == "flag"):
                 status = "PASS"
            else:
                 status = f"FAIL (Expected {case['expected']}, got {decision})"
        
        print(f"ID: {case['id']:<15} | Expected: {case['expected']:<8} | Got: {decision:<8} | {status}")

if __name__ == "__main__":
    # Detect if running in Docker container might need host.docker.internal
    # For Linux users running simple docker run --network host, localhost works.
    # But standard bridge network needs special handling.
    
    print("NOTE: Ensure 'CALLBACK_URL' in the script is reachable from the docker container.")
    print(f"Current CALLBACK_URL: {CALLBACK_URL}")
    print("If you are on Linux and using default bridge network, you might need to use your host IP (e.g. 172.17.0.1) instead of localhost/host.docker.internal")
    
    test_moderation()

