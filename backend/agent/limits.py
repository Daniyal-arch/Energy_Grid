"""Safety caps (brief 25 stage 10): a per-IP token bucket on the hashed IP and a global daily
spend counter. DynamoDB (on demand) in Lambda; in memory locally and in tests.

Table layout (deploy/template.yaml): partition key `pk` (string); items
`ip#<hash>` {tokens, updated, ttl} and `spend#<YYYY-MM-DD>` {usd, ttl}.
"""

from __future__ import annotations

import hashlib
import threading
import time
from decimal import Decimal
from typing import Any, Protocol


def hash_ip(ip: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()[:24]


def today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


class Limits(Protocol):
    def take(self, ip_hash: str) -> bool: ...
    def spent_today(self) -> float: ...
    def add_spend(self, usd: float) -> None: ...


class MemoryLimits:
    def __init__(self, per_hour: int) -> None:
        self.per_hour = per_hour
        self.buckets: dict[str, tuple[float, float]] = {}
        self.spend: dict[str, float] = {}
        self.lock = threading.Lock()

    def take(self, ip_hash: str) -> bool:
        now = time.time()
        with self.lock:
            tokens, updated = self.buckets.get(ip_hash, (float(self.per_hour), now))
            tokens = min(self.per_hour, tokens + (now - updated) * self.per_hour / 3600)
            if tokens < 1:
                self.buckets[ip_hash] = (tokens, now)
                return False
            self.buckets[ip_hash] = (tokens - 1, now)
            return True

    def spent_today(self) -> float:
        return self.spend.get(today(), 0.0)

    def add_spend(self, usd: float) -> None:
        with self.lock:
            self.spend[today()] = self.spend.get(today(), 0.0) + usd


class DynamoLimits:
    def __init__(self, table: str, region: str, per_hour: int) -> None:
        import boto3

        self.table = boto3.resource("dynamodb", region_name=region).Table(table)
        self.per_hour = per_hour

    def take(self, ip_hash: str) -> bool:
        from botocore.exceptions import ClientError

        now = Decimal(str(round(time.time(), 3)))
        item = self.table.get_item(Key={"pk": f"ip#{ip_hash}"}).get("Item")
        tokens = Decimal(self.per_hour)
        if item:
            elapsed = now - Decimal(item["updated"])
            tokens = min(
                Decimal(self.per_hour), Decimal(item["tokens"]) + elapsed * self.per_hour / 3600
            )
        if tokens < 1:
            return False
        try:
            # conditional write: a concurrent request that updated the item first wins
            self.table.put_item(
                Item={
                    "pk": f"ip#{ip_hash}",
                    "tokens": tokens - 1,
                    "updated": now,
                    "ttl": int(now) + 7200,
                },
                ConditionExpression="attribute_not_exists(pk) OR updated = :u",
                ExpressionAttributeValues={":u": item["updated"] if item else now},
            )
        except ClientError:
            return False
        return True

    def spent_today(self) -> float:
        item = self.table.get_item(Key={"pk": f"spend#{today()}"}).get("Item")
        return float(item["usd"]) if item else 0.0

    def add_spend(self, usd: float) -> None:
        self.table.update_item(
            Key={"pk": f"spend#{today()}"},
            UpdateExpression="ADD usd :c SET #t = :t",
            ExpressionAttributeNames={"#t": "ttl"},
            ExpressionAttributeValues={
                ":c": Decimal(str(round(usd, 6))),
                ":t": int(time.time()) + 3 * 86400,
            },
        )


_limits: Limits | None = None


def get_limits(settings: Any) -> Limits:
    global _limits
    if _limits is None:
        _limits = (
            DynamoLimits(
                settings.dynamodb_table, settings.aws_region, settings.ip_requests_per_hour
            )
            if settings.dynamodb_table
            else MemoryLimits(settings.ip_requests_per_hour)
        )
    return _limits


def reset_limits() -> None:
    global _limits
    _limits = None
