"""데모 서비스: POST /demo  {"kind": "ok" | "defect"}
S3 images/에 있는 Kaggle 샘플 중 하나를 골라 images/demo-<시각>-<파일명>으로 복사한다.
복사 = S3 업로드 이벤트이므로 기존 판정 파이프라인(qlens-inspect-image)이 그대로 실행된다.
→ 교수님/방문자가 AWS 계정 없이 대시보드 버튼만으로 '업로드 → AI 판정 → 알림'을 체험할 수 있다."""
import json
import os
import random
import time

import boto3

s3 = boto3.client("s3")
BUCKET = os.environ["BUCKET_NAME"]
HEADERS = {"Content-Type": "application/json; charset=utf-8", "Access-Control-Allow-Origin": "*"}
PREFIX = {"defect": "images/cast_def_", "ok": "images/cast_ok_"}


def respond(status, body):
    return {"statusCode": status, "headers": HEADERS, "body": json.dumps(body, ensure_ascii=False)}


def list_samples(prefix):
    keys, kwargs = [], {"Bucket": BUCKET, "Prefix": prefix}
    while True:
        resp = s3.list_objects_v2(**kwargs)
        keys += [o["Key"] for o in resp.get("Contents", []) if o["Key"].lower().endswith((".jpg", ".jpeg", ".png"))]
        if not resp.get("IsTruncated"):
            return keys
        kwargs["ContinuationToken"] = resp["NextContinuationToken"]


def lambda_handler(event, context):
    event = event or {}
    try:
        body = json.loads(event.get("body") or "{}")
    except ValueError:
        body = {}
    kind = str(body.get("kind") or (event.get("queryStringParameters") or {}).get("kind") or "").lower()
    if kind not in PREFIX:
        return respond(400, {"message": "kind는 'ok' 또는 'defect'여야 합니다."})

    samples = list_samples(PREFIX[kind])
    if not samples:
        return respond(404, {"message": "샘플 이미지가 없습니다."})

    src = random.choice(samples)
    name = src.rsplit("/", 1)[-1]
    dst = f"images/demo-{int(time.time())}-{name}"
    s3.copy_object(Bucket=BUCKET, Key=dst, CopySource={"Bucket": BUCKET, "Key": src})
    print(f"demo {kind}: {src} -> {dst}")
    return respond(202, {
        "started": True,
        "kind": kind,
        "sample": name,
        "imageKey": dst,
        "message": "샘플을 업로드했습니다. 수 초 안에 AI 판정 결과가 대시보드에 표시됩니다.",
    })
