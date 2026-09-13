import random
from locust import HttpUser, task, between

TOKEN = open("/mnt/locust/jwt.txt").read().strip()


class DjangoAuthUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task(3)
    def validate_token(self):
        with self.client.post(
            "/api/auth/internal/validate-token/",
            json={"token": TOKEN},
            catch_response=True,
            name="validate-token",
        ) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"HTTP {r.status_code}")

    @task(2)
    def check_rate_limit(self):
        # Vary user_id so this endpoint isn't just testing the 1000/hr block path
        uid = random.randint(1, 100000)
        with self.client.get(
            f"/api/auth/internal/check-rate-limit?user_id={uid}",
            catch_response=True,
            name="check-rate-limit",
        ) as r:
            # allowed:true or allowed:false are BOTH a correctly functioning
            # response — only non-200 / errors count as a failure.
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"HTTP {r.status_code}")
