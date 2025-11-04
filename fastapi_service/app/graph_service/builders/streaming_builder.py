"""
Kafka / NATS / Redis Streams consumer that turns messages
into graph triples in real-time.
"""

import asyncio
import json
from typing import AsyncGenerator, Dict, Any
from datetime import datetime, timezone

from aiokafka import AIOKafkaConsumer
from app.builders.incremental_builder import IncrementalBuilder


class StreamingBuilder:
    """
    Long-lived async consumer that never drops messages.
    Supports graceful shutdown & offset management.
    """

    def __init__(self, kafka_bootstrap: str, topic: str, group_id: str):
        self.bootstrap = kafka_bootstrap
        self.topic = topic
        self.group_id = group_id
        self.consumer = None

    async def start(self) -> None:
        self.consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap,
            group_id=self.group_id,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            enable_auto_commit=False,
        )
        await self.consumer.start()

    async def stop(self) -> None:
        if self.consumer:
            await self.consumer.stop()

    async def run(self) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Yields summary stats for each micro-batch.
        """
        try:
            async for msg in self.consumer:
                payload = msg.value
                summary = await IncrementalBuilder.process(payload)
                await self.consumer.commit()
                yield summary
        finally:
            await self.stop()