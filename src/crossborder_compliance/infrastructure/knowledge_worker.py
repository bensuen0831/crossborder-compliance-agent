"""Redis Streams transport with durable PostgreSQL idempotency; no graph checkpoint."""

from uuid import UUID

from redis import Redis
from redis.exceptions import ResponseError


class RedisKnowledgeTaskQueue:
    def __init__(self, redis_url, tenant_id, consumer_id="knowledge-worker"):
        self.client = Redis.from_url(redis_url, decode_responses=True)
        self.stream = f"knowledge:{UUID(str(tenant_id))}:ingestion"
        self.group = "knowledge-workers-v1"
        self.consumer = consumer_id
        try:
            self.client.xgroup_create(self.stream, self.group, id="0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def enqueue(self, *, task_id, task_type):
        if task_type != "KNOWLEDGE_INGESTION":
            raise ValueError("unsupported task type")
        self.client.xadd(self.stream, {"task_id": str(UUID(str(task_id))), "task_type": task_type})

    def receive(self):
        claimed = self.client.xautoclaim(
            self.stream, self.group, self.consumer, 60000, start_id="0-0", count=1
        )[1]
        if claimed:
            return claimed[0]
        entries = self.client.xreadgroup(
            self.group, self.consumer, {self.stream: ">"}, count=1, block=1000
        )
        return entries[0][1][0] if entries else None

    def ack(self, message_id):
        self.client.xack(self.stream, self.group, message_id)


class KnowledgeIngestionWorker:
    def __init__(self, repository, service, queue):
        self.repository, self.service, self.queue = repository, service, queue

    def run_once(self):
        self.repository.dispatch_outbox(self.queue)
        message = self.queue.receive()
        if message is None:
            return False
        message_id, payload = message
        if payload["task_type"] != "KNOWLEDGE_INGESTION":
            raise ValueError("invalid queue task")
        self.service.work(payload["task_id"])
        self.queue.ack(message_id)
        return True
