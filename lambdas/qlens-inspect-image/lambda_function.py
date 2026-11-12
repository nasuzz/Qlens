"""판정 서비스: S3 images/ 업로드 → Bedrock(Nova Lite) 판정 → DynamoDB 저장 → 불량이면 SNS 알림"""
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
REFERENCE_KEY = os.environ.get("REFERENCE_KEY", "")  # 예: reference/ok_reference.jpeg (비우면 미사용)
KST = timezone(timedelta(hours=9))

PROMPT = """당신은 주조 부품(펌프 임펠러) 품질 검사관입니다. 이미지는 임펠러를 위에서 내려다본 흑백 사진입니다.

[정상 부품의 구조 - 아래는 결함이 아닙니다]
- 가운데 원형 허브(돌출된 원통)와 그 안의 둥근 구멍(축 구멍)
- 허브를 둘러싼 여러 겹의 동심원 홈과 링
- 바깥쪽의 넓은 원판(플랜지)과 매끈하고 둥근 바깥 테두리
- 금속 질감, 빛 반사, 미세한 가공 흔적

[불량 판정 기준 - 아래가 명확히 보일 때만 DEFECT]
- 기공: 표면의 작은 구멍이나 움푹 패인 점
- 균열: 가늘게 갈라진 선
- 테두리 결함: 바깥 테두리나 링이 깨지거나 울퉁불퉁하게 이지러짐
- 버: 테두리 밖으로 삐져나온 불규칙한 금속 조각
- 표면 결함: 거칠게 뜯겨나간 부분, 이물 자국
{reference_note}
확실하지 않으면 OK로 판정합니다. 다른 말 없이 아래 JSON으로만 답하세요.
{{"result": "OK" 또는 "DEFECT", "defectType": "기공|균열|테두리 결함|버|표면 결함|없음", "confidence": "HIGH|MEDIUM|LOW", "reason": "판정 근거 한 문장"}}"""


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
    content = []
    note = ""
    if REFERENCE_KEY:
        content += [
            {"text": "[기준 이미지] 아래는 정상 부품 사진입니다."},
            {"image": {"format": _fmt(REFERENCE_KEY), "source": {"bytes": _read(bucket, REFERENCE_KEY)}}},
            {"text": "[검사 대상 이미지]"},
        ]
        note = "\n기준 이미지(정상)와 비교해 구조는 같고 위 결함이 없으면 OK입니다.\n"
    content += [
        {"image": {"format": _fmt(key), "source": {"bytes": _read(bucket, key)}}},
        {"text": PROMPT.format(reference_note=note)},
    ]
    resp = bedrock.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": content}],
        inferenceConfig={"maxTokens": 300, "temperature": 0},
    )
    return _parse(resp["output"]["message"]["content"][0]["text"])


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
        table.put_item(Item=item)
        print(json.dumps(item, ensure_ascii=False))

        if item["result"] == "DEFECT" and TOPIC_ARN:
            sns.publish(
                TopicArn=TOPIC_ARN,
                Subject="[Qlens] 불량 부품 감지",
                Message=(
                    "Qlens가 불량 부품을 감지했습니다.\n\n"
                    f"검사 ID : {item['inspectionId']}\n"
                    f"이미지  : s3://{bucket}/{key}\n"
                    f"불량 유형: {item['defectType']}\n"
                    f"확신도  : {item['confidence']}\n"
                    f"판정 근거: {item['reason']}\n"
                    f"검사 시각: {item['inspectedAt']}"
                ),
            )
        saved.append(item)
    return {"inspected": len(saved), "items": saved}
