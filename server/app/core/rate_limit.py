# -*- coding: utf-8 -*-
"""轻量内存限流器（单进程部署可用；生产多实例需迁移 Redis 实现，接口不变）"""
import threading
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    """滑动窗口限流：allow(key, limit, window_seconds)"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        with self._lock:
            q = self._records[key]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def clear(self, key: str) -> None:
        with self._lock:
            self._records.pop(key, None)


class LoginThrottle:
    """登录失败锁定：连续失败 max_fails 次，锁定 lock_minutes 分钟"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._fails: dict[str, list] = {}  # email -> [fail_count, lock_until_ts]

    def remaining_lock(self, email: str) -> int:
        now = time.time()
        with self._lock:
            row = self._fails.get(email)
            if row and row[1] > now:
                return int(row[1] - now) + 1
            return 0

    def record_fail(self, email: str, max_fails: int, lock_minutes: int) -> None:
        now = time.time()
        with self._lock:
            row = self._fails.get(email)
            if row and row[1] > now:
                return
            count = (row[0] if row else 0) + 1
            lock_until = now + lock_minutes * 60 if count >= max_fails else 0
            self._fails[email] = [count, lock_until]

    def record_success(self, email: str) -> None:
        with self._lock:
            self._fails.pop(email, None)


send_code_limiter = SlidingWindowLimiter()
login_throttle = LoginThrottle()
register_limiter = SlidingWindowLimiter()
