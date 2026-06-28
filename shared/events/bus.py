import json
import logging

import redis

from .models import Event

logger = logging.getLogger(__name__)

LOSTIFY_CHANNEL = "lostify:events"


class EventBus:
    """Redis pub/sub event bus for async inter-service communication."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._client: redis.Redis | None = None

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(self.redis_url, decode_responses=True)
        return self._client

    def publish(self, event: Event) -> None:
        message = json.dumps(event.to_dict())
        subscribers = self.client.publish(LOSTIFY_CHANNEL, message)
        logger.info(
            "Published event %s (%s) to %d subscriber(s)",
            event.event_type.value,
            event.event_id,
            subscribers,
        )

    def subscribe(self):
        """Return a pubsub object listening on the Lostify channel."""
        pubsub = self.client.pubsub()
        pubsub.subscribe(LOSTIFY_CHANNEL)
        logger.info("Subscribed to channel %s", LOSTIFY_CHANNEL)
        return pubsub
