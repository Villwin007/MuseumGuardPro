import requests
import time
import sys

def check_server():
    print("Checking server...")
    url = "http://127.0.0.1:8000"
    
    max_retries = 20
    for i in range(max_retries):
        try:
            # Check Index
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                print("Index page: OK")
                
                # Check Stats
                r_stats = requests.get(f"{url}/stats", timeout=2)
                if r_stats.status_code == 200:
                    print("Stats endpoint: OK")
                    print(r_stats.json())
                    return True
                else:
                    print(f"Stats endpoint failed: {r_stats.status_code}")
            else:
                print(f"Index page failed: {r.status_code}")
                
        except requests.ConnectionError:
            print(f"Server not ready, retrying ({i+1}/{max_retries})...")
            time.sleep(2)
        except Exception as e:
            print(f"Error: {e}")
            
    return False

if __name__ == "__main__":
    if check_server():
        print("Verification SUCCESS")
        sys.exit(0)
    else:
        print("Verification FAILED")
        sys.exit(1)
