"""판정 서비스: S3 images/ 업로드 → Bedrock(Nova Lite) 판정 → DynamoDB 저장 → 불량이면 SNS 알림 → 대시보드 실시간 푸시"""
import json
import os
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone

import boto3
from botocore.config import Config

s3 = boto3.client("s3")
# 20장을 한꺼번에 올리면 신규 계정의 낮은 Bedrock 호출 한도에 걸릴 수 있어 재시도를 넉넉히 둔다
bedrock = boto3.client("bedrock-runtime", config=Config(retries={"max_attempts": 10, "mode": "adaptive"}, read_timeout=60))
sns = boto3.client("sns")
table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])

MODEL_ID = os.environ.get("MODEL_ID", "amazon.nova-lite-v1:0")
TOPIC_ARN = os.environ.get("TOPIC_ARN", "")
KST = timezone(timedelta(hours=9))

# 실시간 푸시(선택): 둘 다 설정돼 있을 때만 WebSocket으로 대시보드에 결과를 보낸다
CONN_TABLE = os.environ.get("CONN_TABLE", "")
WS_ENDPOINT = os.environ.get("WS_ENDPOINT", "")  # 예: https://abc123.execute-api.ap-southeast-2.amazonaws.com/prod
conn_table = boto3.resource("dynamodb").Table(CONN_TABLE) if CONN_TABLE else None
ws = boto3.client("apigatewaymanagementapi", endpoint_url=WS_ENDPOINT) if CONN_TABLE and WS_ENDPOINT else None

# 프롬프트 비교 실험(scripts/experiment.py, 20장) 결과 정확도 80%·재현율 90%로 1위인 'A 기본 프롬프트'.
# 정상 구조 설명·기준 이미지를 추가한 B~E는 Nova Lite가 OK 쪽으로 쏠려 50~60%에 그쳤다.
PROMPT = """이 주조 부품(펌프 임펠러) 이미지를 보고 정상인지 불량인지 판정하세요.
다른 말 없이 아래 JSON으로만 답하세요.
{"result": "OK" 또는 "DEFECT", "defectType": "기공|균열|테두리 결함|버|표면 결함|없음", "confidence": "HIGH|MEDIUM|LOW", "reason": "판정 근거 한 문장"}"""


def _read(bucket, key):
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read()


def _fmt(key):
    ext = key.rsplit(".", 1)[-1].lower()
    return "jpeg" if ext in ("jpg", "jpeg") else ext


def _parse(text):
    try:
        data = json.loads(text[text.find("{"): text.rfind("}") + 1])
        result = str(data.get("result", "")).upper()
        if result not in ("OK", "DEFECT"):
            raise ValueError(result)
        return {
            "result": result,
            "defectType": data.get("defectType") or "없음",
            "confidence": data.get("confidence") or "",
            "reason": data.get("reason") or "",
        }
    except Exception:
        return {"result": "UNKNOWN", "defectType": "없음", "confidence": "", "reason": f"응답 파싱 실패: {text[:200]}"}


def inspect(bucket, key):
    content = [
        {"image": {"format": _fmt(key), "source": {"bytes": _read(bucket, key)}}},
        {"text": PROMPT},
    ]
    resp = bedrock.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": content}],
        inferenceConfig={"maxTokens": 300, "temperature": 0},
    )
    return _parse(resp["output"]["message"]["content"][0]["text"])


def broadcast(item):
    """접속 중인 모든 대시보드에 판정 결과 푸시. 실패해도 판정 흐름은 막지 않는다."""
    if not ws:
        return
    try:
        conns, kwargs = [], {"ProjectionExpression": "connectionId"}
        while True:
            resp = conn_table.scan(**kwargs)
            conns += [c["connectionId"] for c in resp["Items"]]
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

        data = json.dumps({"type": "inspection", "item": item}, ensure_ascii=False).encode("utf-8")
        sent = 0
        for cid in conns:
            try:
                ws.post_to_connection(ConnectionId=cid, Data=data)
                sent += 1
            except ws.exceptions.GoneException:
                conn_table.delete_item(Key={"connectionId": cid})  # 이미 닫힌 연결 정리
        print(f"broadcast to {sent}/{len(conns)} dashboards")
    except Exception as e:  # noqa: BLE001
        print(f"broadcast failed: {e}")


def lambda_handler(event, context):
    saved = []
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        if not key.lower().endswith((".jpg", ".jpeg", ".png")):
            continue

        verdict = inspect(bucket, key)
        now = datetime.now(KST)
        item = {
            "inspectionId": f"insp-{now:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}",
            "imageKey": key,
            "inspectedAt": now.isoformat(timespec="seconds"),
            "model": MODEL_ID,
            **verdict,
        }
        # Human-in-the-loop: AI 확신도가 낮거나 응답이 깨지면 사람이 재검사하도록 표시
        needs_review = item["result"] == "UNKNOWN" or str(item["confidence"]).upper() == "LOW"
        item["reviewStatus"] = "PENDING" if needs_review else "NONE"

        table.put_item(Item=item)
        print(json.dumps(item, ensure_ascii=False))

        if TOPIC_ARN and (item["result"] == "DEFECT" or needs_review):
            if item["result"] == "DEFECT":
                subject, head = "[Qlens] 불량 부품 감지", "Qlens가 불량 부품을 감지했습니다."
            else:
                subject, head = "[Qlens] 재검사 요청", "AI 판정 확신도가 낮아 작업자 재검사가 필요합니다."
            if needs_review and item["result"] == "DEFECT":
                head += " (확신도 낮음 - 재검사 권장)"
            sns.publish(
                TopicArn=TOPIC_ARN,
                Subject=subject,
                Message=(
                    f"{head}\n\n"
                    f"검사 ID : {item['inspectionId']}\n"
                    f"이미지  : s3://{bucket}/{key}\n"
                    f"AI 판정 : {item['result']}\n"
                    f"불량 유형: {item['defectType']}\n"
                    f"확신도  : {item['confidence']}\n"
                    f"판정 근거: {item['reason']}\n"
                    f"검사 시각: {item['inspectedAt']}"
                ),
            )
        broadcast(item)
        saved.append(item)
    return {"inspected": len(saved), "items": saved}
