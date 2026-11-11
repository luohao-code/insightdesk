"""轻量事件总线。

批量任务的进度通过 SSE 推送给浏览器。为避免引入 Redis / 消息队列，
这里使用进程内 ``queue.Queue`` 广播：

* 每个 SSE 连接一个独立队列，互不阻塞；
* 队列满时丢弃最旧事件，保证慢客户端不会拖垮工作线程；
* 服务重启后前端会自动重连并通过批次详情接口补齐状态。
"""

from __future__ import annotations

import queue
import threading
from typing import Any

_MAX_QUEUE_SIZE = 256


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[queue.Queue] = set()
        self._lock = threading.Lock()
        self._sequence = 0

    def subscribe(self) -> queue.Queue:
        subscriber: queue.Queue = queue.Queue(maxsize=_MAX_QUEUE_SIZE)
        with self._lock:
            self._subscribers.add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: queue.Queue) -> None:
        with self._lock:
            self._subscribers.discard(subscriber)

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

    def publish(self, event: dict[str, Any]) -> None:
        with self._lock:
            self._sequence += 1
            payload = {**event, "seq": self._sequence}
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            try:
                subscriber.put_nowait(payload)
            except queue.Full:
                try:
                    subscriber.get_nowait()
                    subscriber.put_nowait(payload)
                except (queue.Empty, queue.Full):
                    continue


bus = EventBus()
