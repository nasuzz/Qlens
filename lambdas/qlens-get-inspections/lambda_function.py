"""이력 조회 서비스: GET /inspections  (?result=DEFECT|OK 필터 선택)"""
import json
import os

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


def lambda_handler(event, context):
    items = scan_all()
    want = ((event or {}).get("queryStringParameters") or {}).get("result")
    if want:
        items = [i for i in items if i.get("result") == want.upper()]
    items.sort(key=lambda i: i.get("inspectedAt", ""), reverse=True)
    return {"statusCode": 200, "headers": HEADERS, "body": json.dumps(items, ensure_ascii=False, default=str)}
