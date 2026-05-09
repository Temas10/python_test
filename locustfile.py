from locust import HttpUser, task, between
import random
import time

class DataSubmitter(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def send_data(self):
        device_id = random.randint(1, 5)
        payload = {
            "x": random.uniform(-100, 100),
            "y": random.uniform(-100, 100),
            "z": random.uniform(-100, 100)
        }
        self.client.post(f"/devices/{device_id}/data", json=payload)

class AnalyticsReader(HttpUser):
    wait_time = between(2, 5)

    @task(1)
    def request_device_analytics(self):
        device_id = random.randint(1, 5)
        resp = self.client.post(f"/devices/{device_id}/analytics", json={
            "start_time": None,
            "end_time": None
        })
        if resp.status_code == 200:
            task_id = resp.json()["task_id"]
            for _ in range(3):
                self.client.get(f"/tasks/{task_id}")
                time.sleep(0.5)