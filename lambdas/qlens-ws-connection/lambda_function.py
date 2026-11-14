"""실시간 연결 서비스: API Gateway WebSocket ($connect / $disconnect / $default)
접속한 대시보드의 connectionId를 DynamoDB(QlensConnections)에 저장·삭제한다.
판정 Lambda는 이 목록을 읽어 판정 결과를 모든 대시보드에 즉시 푸시한다."""
import os
import time

import boto3

table = boto3.resource("dynamodb").Table(os.environ["CONN_TABLE"])


def lambda_handler(event, context):
    ctx = event["requestContext"]
    route, cid = ctx["routeKey"], ctx["connectionId"]

    if route == "$connect":
        table.put_item(Item={
            "connectionId": cid,
            "connectedAt": int(time.time()),
            "sourceIp": ctx.get("identity", {}).get("sourceIp", ""),
        })
        print(f"connect {cid}")
    elif route == "$disconnect":
        table.delete_item(Key={"connectionId": cid})
        print(f"disconnect {cid}")
    # $default: 대시보드의 keep-alive ping 등 — 할 일 없음
    return {"statusCode": 200, "body": "ok"}
