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
            return True  # Don’t throttle unauthenticated users, or throttle by IP
        # Example: Allow 100 requests per hour
        count = redis_client.incr(cache_key)
        if count == 1:
            redis_client.expire(cache_key, 3600)  # 1 hour window
        return count <= 100
