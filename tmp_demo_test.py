from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

r = client.get('/demo')
print('demo', r.status_code, r.json())
r2 = client.get('/emails')
print('emails', r2.status_code, r2.json())
