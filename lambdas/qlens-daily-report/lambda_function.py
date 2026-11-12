"""리포트 서비스: EventBridge 매일 실행 → 해당 일자 검사 집계 → S3 reports/YYYY-MM-DD.json 저장
수동 실행 시 {"date": "2026-11-20"} 이벤트로 특정 날짜 지정 가능 (기본: 오늘, KST)"""
import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone

import boto3
from boto3.dynamodb.conditions import Attr

s3 = boto3.client("s3")
table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
BUCKET = os.environ["BUCKET_NAME"]
KST = timezone(timedelta(hours=9))


def lambda_handler(event, context):
    date = (event or {}).get("date") or datetime.now(KST).strftime("%Y-%m-%d")

    items, kwargs = [], {"FilterExpression": Attr("inspectedAt").begins_with(date)}
    while True:
        resp = table.scan(**kwargs)
        items += resp["Items"]
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    defects = [i for i in items if i.get("result") == "DEFECT"]
    report = {
        "date": date,
        "generatedAt": datetime.now(KST).isoformat(timespec="seconds"),
        "total": len(items),
        "defect": len(defects),
        "ok": sum(i.get("result") == "OK" for i in items),
        "defectRate": round(len(defects) / len(items), 4) if items else 0,
        "byType": dict(Counter(i.get("defectType", "없음") for i in defects)),
        "defects": [
            {k: i.get(k) for k in ("inspectionId", "imageKey", "defectType", "confidence", "reason", "inspectedAt")}
            for i in sorted(defects, key=lambda x: x.get("inspectedAt", ""))
        ],
    }

    key = f"reports/{date}.json"
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )
    print(f"saved s3://{BUCKET}/{key} total={report['total']} defect={report['defect']}")
    return {"reportKey": key, "total": report["total"], "defect": report["defect"]}
