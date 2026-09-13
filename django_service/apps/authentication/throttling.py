from rest_framework.throttling import SimpleRateThrottle
import redis
from django.conf import settings

redis_client = redis.StrictRedis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)

class UserRateThrottle(SimpleRateThrottle):
    scope = 'user'

    def get_cache_key(self, request, view):
        if not request.user.is_authenticated:
            return None
        return f"throttle_{request.user.pk}"

    def allow_request(self, request, view):
        cache_key = self.get_cache_key(request, view)
        if not cache_key:
            return True  # Don't throttle unauthenticated users, or throttle by IP
        return check_rate_limit(cache_key, self.num_requests, self.duration)


def check_rate_limit(key: str, num_requests: int, duration_seconds: int) -> bool:
    """
    Fixed-window counter shared by the DRF throttle and the internal
    check-rate-limit endpoint FastAPI calls, so both enforce the same limit.
    """
    count = redis_client.incr(key)
    if count == 1:
        redis_client.expire(key, duration_seconds)
    return count <= num_requests


def user_rate_limit_key(user_id) -> str:
    return f"throttle_{user_id}"
