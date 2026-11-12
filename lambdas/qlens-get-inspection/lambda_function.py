"""단건 조회 서비스: GET /inspections/{id}"""
import json
import os

import boto3

table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
HEADERS = {"Content-Type": "application/json; charset=utf-8", "Access-Control-Allow-Origin": "*"}


def lambda_handler(event, context):
    inspection_id = ((event or {}).get("pathParameters") or {}).get("id")
    if not inspection_id:
        return {"statusCode": 400, "headers": HEADERS, "body": json.dumps({"message": "id가 필요합니다."}, ensure_ascii=False)}

    item = table.get_item(Key={"inspectionId": inspection_id}).get("Item")
    if not item:
        return {"statusCode": 404, "headers": HEADERS, "body": json.dumps({"message": f"{inspection_id} 검사 결과가 없습니다."}, ensure_ascii=False)}
    return {"statusCode": 200, "headers": HEADERS, "body": json.dumps(item, ensure_ascii=False, default=str)}
