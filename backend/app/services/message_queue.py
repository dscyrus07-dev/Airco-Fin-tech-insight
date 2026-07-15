"""
RabbitMQ message queue client for event-driven architecture.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

try:
    import pika
except ImportError:
    pika = None

from ..core.config import settings
from ..utils.logging import get_logger

logger = get_logger(__name__)

# Maximum number of times a message is retried on a transient (exception)
# failure before it is routed to the dead-letter queue.
MAX_DELIVERY_ATTEMPTS = 3
DEAD_LETTER_QUEUE = "dead_letter_queue"


class MessageQueue:
    """RabbitMQ message queue client built on pika BlockingConnection."""

    def __init__(self):
        self.connection_url = settings.RABBITMQ_URL
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.adapters.blocking_connection.BlockingChannel] = None
        self._publisher_connection: Optional[pika.BlockingConnection] = None
        self._publisher_channel: Optional[pika.adapters.blocking_connection.BlockingChannel] = None
        self._consumers: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
        self._connected = False
        self._consumer_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _create_connection(self) -> None:
        if pika is None:
            raise RuntimeError("RabbitMQ support is unavailable because pika is not installed")
        parameters = pika.URLParameters(self.connection_url)
        # Increase heartbeat to 300s (5 min) for long bank processing tasks
        # Blocked connection timeout must be > heartbeat to avoid false timeouts
        parameters.heartbeat = 300
        parameters.blocked_connection_timeout = 150
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()
        self.channel.basic_qos(prefetch_count=1)
        self._declare_topology()
        self._connected = True

    def _probe_connection(self) -> None:
        if pika is None:
            raise RuntimeError("RabbitMQ support is unavailable because pika is not installed")
        parameters = pika.URLParameters(self.connection_url)
        # Use same heartbeat settings for consistency
        parameters.heartbeat = 300
        parameters.blocked_connection_timeout = 150
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.basic_qos(prefetch_count=1)
        self._declare_topology_on_channel(channel)
        connection.close()
        self._connected = True

    # Active topology: a single work exchange/queue plus a dead-letter queue.
    # (The previous pdf/ai/report exchanges were declared but never used.)
    _ACTIVE_QUEUES = [
        ("file_upload_queue", "file_processing", "file.uploaded"),
    ]

    def _declare_topology(self) -> None:
        assert self.channel is not None
        self._declare_topology_on_channel(self.channel)

    def _declare_topology_on_channel(self, channel) -> None:
        channel.exchange_declare(exchange="file_processing", exchange_type="topic", durable=True)

        for queue_name, exchange, routing_key in self._ACTIVE_QUEUES:
            channel.queue_declare(queue=queue_name, durable=True)
            channel.queue_bind(queue=queue_name, exchange=exchange, routing_key=routing_key)

        # Dead-letter queue for messages that exhaust their retry budget.
        channel.queue_declare(queue=DEAD_LETTER_QUEUE, durable=True)

    def _ensure_publisher_channel(self):
        if pika is None:
            return None
        if (
            self._publisher_connection
            and self._publisher_connection.is_open
            and self._publisher_channel
            and self._publisher_channel.is_open
        ):
            return self._publisher_channel

        parameters = pika.URLParameters(self.connection_url)
        # Extended heartbeat for long processing tasks
        parameters.heartbeat = 300
        parameters.blocked_connection_timeout = 150
        self._publisher_connection = pika.BlockingConnection(parameters)
        self._publisher_channel = self._publisher_connection.channel()
        self._publisher_channel.basic_qos(prefetch_count=1)
        self._declare_topology_on_channel(self._publisher_channel)
        return self._publisher_channel

    def _close_publisher_connection(self) -> None:
        with self._lock:
            try:
                if self._publisher_connection and self._publisher_connection.is_open:
                    self._publisher_connection.close()
            except Exception:
                pass
            self._publisher_connection = None
            self._publisher_channel = None

    async def connect(self):
        """Connect to RabbitMQ without blocking the event loop."""
        if pika is None:
            self._connected = False
            logger.warning("RabbitMQ unavailable; continuing without queue support")
            return False

        try:
            await asyncio.to_thread(self._probe_connection)
            logger.info("Connected to RabbitMQ", url=self.connection_url)
        except Exception as e:
            self._connected = False
            logger.warning("RabbitMQ unavailable; continuing without queue", error=str(e))

    def register_consumer(self, queue_name: str, callback: Callable[[Dict[str, Any]], Any]):
        """Register a consumer for a queue."""
        self._consumers[queue_name] = callback
        logger.info("Consumer registered", queue=queue_name)

    def _route_to_dead_letter(self, ch, body: bytes, headers: Dict[str, Any], reason: str) -> None:
        """Publish a poison message to the dead-letter queue so it is never lost."""
        try:
            dead_headers = dict(headers or {})
            dead_headers["x-death-reason"] = reason[:500]
            ch.basic_publish(
                exchange="",  # default exchange routes by queue name
                routing_key=DEAD_LETTER_QUEUE,
                body=body,
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type="application/json",
                    headers=dead_headers,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to route message to dead-letter queue", error=str(exc))

    def _message_callback(self, queue_name: str, user_callback: Callable[[Dict[str, Any]], Any]):
        def _callback(ch, method, properties, body):
            headers = (properties.headers if properties and properties.headers else {}) or {}
            attempts = int(headers.get("x-retry-count", 0))
            try:
                payload = json.loads(body.decode("utf-8"))
                logger.info("Consumed message", queue=queue_name, payload_keys=list(payload.keys()))

                if inspect.iscoroutinefunction(user_callback):
                    loop = self._loop
                    if loop is None or loop.is_closed():
                        loop = asyncio.new_event_loop()
                        self._loop = loop
                    result = loop.run_until_complete(user_callback(payload))
                else:
                    result = user_callback(payload)

                if result is False:
                    # Deliberate rejection by the handler: do not retry, dead-letter it.
                    logger.warning("Handler rejected message; dead-lettering", queue=queue_name)
                    self._route_to_dead_letter(ch, body, headers, "handler_rejected")
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                # Transient failure: retry up to MAX_DELIVERY_ATTEMPTS, then dead-letter.
                logger.error("Consumer failed", queue=queue_name, error=str(e), attempt=attempts)
                if attempts + 1 < MAX_DELIVERY_ATTEMPTS:
                    retry_headers = dict(headers)
                    retry_headers["x-retry-count"] = attempts + 1
                    try:
                        ch.basic_publish(
                            exchange=method.exchange,
                            routing_key=method.routing_key,
                            body=body,
                            properties=pika.BasicProperties(
                                delivery_mode=2,
                                content_type="application/json",
                                headers=retry_headers,
                            ),
                        )
                        logger.warning("Requeued message for retry", queue=queue_name, attempt=attempts + 1)
                    except Exception as exc:  # noqa: BLE001
                        logger.error("Retry republish failed; dead-lettering", error=str(exc))
                        self._route_to_dead_letter(ch, body, headers, f"retry_failed:{exc}")
                else:
                    logger.error("Message exhausted retries; dead-lettering", queue=queue_name)
                    self._route_to_dead_letter(ch, body, headers, str(e))
                ch.basic_ack(delivery_tag=method.delivery_tag)

        return _callback

    def _start_consumer_loop(self):
        if pika is None:
            logger.warning("RabbitMQ unavailable; consumer loop will not start")
            return

        while not self._stop_event.is_set():
            connection = None
            channel = None
            # Fresh loop each reconnect cycle so _message_callback never holds a closed loop.
            self._loop = asyncio.new_event_loop()
            try:
                parameters = pika.URLParameters(self.connection_url)
                # Extended heartbeat for long processing tasks
                parameters.heartbeat = 300
                parameters.blocked_connection_timeout = 150
                connection = pika.BlockingConnection(parameters)
                channel = connection.channel()
                channel.basic_qos(prefetch_count=1)
                self._connected = True
                self.connection = connection
                self.channel = channel

                self._declare_topology_on_channel(channel)

                for queue_name, callback in self._consumers.items():
                    channel.basic_consume(
                        queue=queue_name,
                        on_message_callback=self._message_callback(queue_name, callback),
                        auto_ack=False,
                    )

                logger.info("RabbitMQ consumer loop starting", queues=list(self._consumers.keys()))
                channel.start_consuming()
            except pika.exceptions.ConnectionClosedByBroker:
                logger.warning("RabbitMQ broker closed consumer connection; retrying")
            except Exception as e:
                logger.error("RabbitMQ consumer initialization failed", error=str(e))
            finally:
                try:
                    if connection and connection.is_open:
                        connection.close()
                except Exception:
                    pass
                self._connected = False

            if not self._stop_event.is_set():
                time.sleep(5)

    async def start_consuming(self):
        """Start consuming messages in a background thread."""
        if pika is None:
            logger.warning("RabbitMQ unavailable; consumer thread not started")
            return

        if self._consumer_thread and self._consumer_thread.is_alive():
            return

        self._stop_event.clear()
        self._consumer_thread = threading.Thread(target=self._start_consumer_loop, daemon=True)
        self._consumer_thread.start()
        logger.info("RabbitMQ consumer thread started")

    def _publish_sync(
        self,
        exchange: str,
        routing_key: str,
        message: Dict[str, Any],
        headers: Optional[Dict[str, Any]] = None,
    ) -> bool:
        try:
            if pika is None:
                logger.warning("RabbitMQ unavailable; message not published", exchange=exchange, routing_key=routing_key)
                return False

            with self._lock:
                channel = self._ensure_publisher_channel()
                if channel is None:
                    logger.warning("RabbitMQ publisher channel unavailable; message not published", exchange=exchange, routing_key=routing_key)
                    return False
                body = json.dumps(message).encode("utf-8")
                channel.basic_publish(
                    exchange=exchange,
                    routing_key=routing_key,
                    body=body,
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        content_type="application/json",
                        headers=headers or {},
                        timestamp=int(datetime.now(timezone.utc).timestamp()),
                    ),
                )
            return True
        except Exception as e:
            self._close_publisher_connection()
            logger.warning("RabbitMQ publish connection failed", error=str(e))
            return False

    async def publish_message(
        self,
        exchange: str,
        routing_key: str,
        message: Dict[str, Any],
        headers: Optional[Dict[str, Any]] = None,
    ):
        """Publish a message to RabbitMQ."""
        try:
            success = await asyncio.to_thread(self._publish_sync, exchange, routing_key, message, headers)
            if not success:
                logger.warning("RabbitMQ not connected; message not published", exchange=exchange, routing_key=routing_key)
                return False

            logger.info("Message published", exchange=exchange, routing_key=routing_key)
            return True
        except Exception as e:
            logger.error("Failed to publish message", exchange=exchange, routing_key=routing_key, error=str(e))
            return False

    async def close(self):
        """Close the connection and stop consumers."""
        self._stop_event.set()
        self._close_publisher_connection()
        if pika is None:
            self._connected = False
            logger.info("RabbitMQ support unavailable; queue already disabled")
            return
        if self.connection and self.connection.is_open:
            try:
                self.connection.add_callback_threadsafe(lambda: self.channel and self.channel.stop_consuming())
            except Exception:
                pass

        if self.connection and self.connection.is_open:
            try:
                await asyncio.to_thread(self.connection.close)
            except Exception:
                pass

        self._connected = False
        logger.info("RabbitMQ connection closed")


# Global message queue instance
message_queue = MessageQueue()
