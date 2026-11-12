"""통계 서비스: GET /stats  → 전체/일별 불량률, 불량 유형별 건수"""
import json
import os
from collections import Counter, defaultdict

import boto3

table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
HEADERS = {"Content-Type": "application/json; charset=utf-8", "Access-Control-Allow-Origin": "*"}


def scan_all():
    items, kwargs = [], {}
    while True:
        resp = table.scan(**kwargs)
        items += resp["Items"]
        if "LastEvaluatedKey" not in resp:
            return items
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def build_stats(items):
    total = len(items)
    defects = [i for i in items if i.get("result") == "DEFECT"]
    by_type = Counter(i.get("defectType", "없음") for i in defects)

    daily = defaultdict(lambda: {"total": 0, "defect": 0})
    for i in items:
        day = i.get("inspectedAt", "")[:10]
        daily[day]["total"] += 1
        daily[day]["defect"] += i.get("result") == "DEFECT"
    by_date = [
        {"date": d, **v, "defectRate": round(v["defect"] / v["total"], 4)}
        for d, v in sorted(daily.items())
    ]

    return {
        "total": total,
        "defect": len(defects),
        "ok": sum(i.get("result") == "OK" for i in items),
        "unknown": sum(i.get("result") not in ("OK", "DEFECT") for i in items),
        "defectRate": round(len(defects) / total, 4) if total else 0,
        "byType": dict(by_type),
        "byDate": by_date,
    }


def lambda_handler(event, context):
    return {"statusCode": 200, "headers": HEADERS, "body": json.dumps(build_stats(scan_all()), ensure_ascii=False)}
