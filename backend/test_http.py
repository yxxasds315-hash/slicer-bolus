import requests, json

BASE = "http://localhost:8765"

def test_health():
    r = requests.get(f"{BASE}/api/health")
    print("Health:", r.json())

def test_status():
    r = requests.get(f"{BASE}/api/slicer/status")
    print("Status:", r.json())

def test_preview(dicom_dir):
    r = requests.post(f"{BASE}/api/preview", json={"dicom_dir": dicom_dir})
    print("Preview:", r.json())

def test_execute(thickness=5.0):
    r = requests.post(f"{BASE}/api/execute", json={"thickness_mm": thickness})
    print("Execute:", r.json())

if __name__ == "__main__":
    test_health()
    test_status()
