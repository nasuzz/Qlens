"""판정 방식 비교 실험 — AWS CloudShell에서 실행 (액세스 키 설정 불필요)

  A. 기본 프롬프트   : "정상/불량 판정"만 지시
  B. 도메인 프롬프트 : 정상 부품 구조 + 불량 판정 기준 설명  (Lambda와 동일)
  C. 기준 이미지 비교 : B + 정상 기준 사진 함께 전송          (Lambda 현재 설정)
  D. 균형 프롬프트   : 허브·링은 정상 구조라는 한 줄만 남기고 'OK 편향' 문구 제거
  E. 정상+불량 기준  : D + 정상 기준 사진 + 불량 기준 사진 (few-shot)

사용법 (CloudShell):
  python3 experiment.py <버킷이름>                       # Nova Lite, A/B/C 전부
  python3 experiment.py <버킷이름> --model amazon.nova-pro-v1:0
  python3 experiment.py <버킷이름> --modes C

S3의 images/ 이미지를 읽어 Bedrock을 직접 호출하므로 DynamoDB/SNS에는 아무것도 기록되지 않는다(메일 안 감).
결과: 화면 표 + experiment_<모델>.csv
"""
import argparse
import csv
import json
import time

import boto3
from botocore.config import Config

REGION = "ap-southeast-2"
JSON_SPEC = ('{"result": "OK" 또는 "DEFECT", "defectType": "기공|균열|테두리 결함|버|표면 결함|없음", '
             '"confidence": "HIGH|MEDIUM|LOW", "reason": "판정 근거 한 문장"}')

PROMPT_A = f"""이 주조 부품(펌프 임펠러) 이미지를 보고 정상인지 불량인지 판정하세요.
다른 말 없이 아래 JSON으로만 답하세요.
{JSON_SPEC}"""

PROMPT_B = f"""당신은 주조 부품(펌프 임펠러) 품질 검사관입니다. 이미지는 임펠러를 위에서 내려다본 흑백 사진입니다.

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
{{reference_note}}
확실하지 않으면 OK로 판정합니다. 다른 말 없이 아래 JSON으로만 답하세요.
{JSON_SPEC}"""

REF_NOTE = "\n기준 이미지(정상)와 비교해 구조는 같고 위 결함이 없으면 OK입니다.\n"

# D: B가 "전부 OK"로 쏠린 원인(긴 정상 설명 + '확실하지 않으면 OK')을 제거한 균형 프롬프트
PROMPT_D = f"""당신은 주조 부품(펌프 임펠러) 품질 검사관입니다. 이미지는 임펠러를 위에서 내려다본 흑백 사진입니다.
참고: 가운데 원형 허브·축 구멍·동심원 링은 원래 있는 구조이므로 그 자체는 결함이 아닙니다.
아래 결함이 하나라도 보이면 DEFECT, 없으면 OK로 판정하세요.
- 기공: 표면의 작은 구멍이나 움푹 패인 점
- 균열: 가늘게 갈라진 선
- 테두리 결함: 바깥 테두리나 링이 깨지거나 울퉁불퉁하게 이지러짐
- 버: 테두리 밖으로 삐져나온 불규칙한 금속 조각
- 표면 결함: 거칠게 뜯겨나간 부분, 이물 자국
다른 말 없이 아래 JSON으로만 답하세요.
{JSON_SPEC}"""

# E: 정상/불량 기준 이미지를 둘 다 보여주고 어느 쪽에 가까운지 판정 (few-shot)
PROMPT_E = PROMPT_D.replace(
    "아래 결함이 하나라도 보이면",
    "기준 이미지 1(정상)과 기준 이미지 2(불량: 기공·테두리 결함)를 참고하세요.\n아래 결함이 하나라도 보이면",
)


def build_content(mode, img, ref, def_ref=None):
    if mode == "D":
        return [{"image": {"format": "jpeg", "source": {"bytes": img}}}, {"text": PROMPT_D}]
    if mode == "E":
        return [
            {"text": "[기준 이미지 1 - 정상]"},
            {"image": {"format": "jpeg", "source": {"bytes": ref}}},
            {"text": "[기준 이미지 2 - 불량]"},
            {"image": {"format": "jpeg", "source": {"bytes": def_ref}}},
            {"text": "[검사 대상 이미지]"},
            {"image": {"format": "jpeg", "source": {"bytes": img}}},
            {"text": PROMPT_E},
        ]
    if mode == "A":
        return [{"image": {"format": "jpeg", "source": {"bytes": img}}}, {"text": PROMPT_A}]
    if mode == "B":
        return [{"image": {"format": "jpeg", "source": {"bytes": img}}},
                {"text": PROMPT_B.replace("{reference_note}", "")}]
    return [
        {"text": "[기준 이미지] 아래는 정상 부품 사진입니다."},
        {"image": {"format": "jpeg", "source": {"bytes": ref}}},
        {"text": "[검사 대상 이미지]"},
        {"image": {"format": "jpeg", "source": {"bytes": img}}},
        {"text": PROMPT_B.replace("{reference_note}", REF_NOTE)},
    ]


def parse(text):
    try:
        r = json.loads(text[text.find("{"): text.rfind("}") + 1])
        res = str(r.get("result", "")).upper()
        return (res if res in ("OK", "DEFECT") else "UNKNOWN"), str(r.get("confidence", "")), str(r.get("reason", ""))
    except Exception:
        return "UNKNOWN", "", text[:100]


def label_of(key):
    name = key.rsplit("/", 1)[-1].lower()
    return "DEFECT" if "_def_" in name else "OK" if "_ok_" in name else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bucket")
    ap.add_argument("--model", default="amazon.nova-lite-v1:0")
    ap.add_argument("--modes", default="ABC")
    ap.add_argument("--reference", default="reference/ok_reference.jpeg")
    ap.add_argument("--def-reference", default="reference/def_reference.jpeg")
    args = ap.parse_args()

    s3 = boto3.client("s3", region_name=REGION)
    br = boto3.client("bedrock-runtime", region_name=REGION,
                      config=Config(retries={"max_attempts": 10, "mode": "adaptive"}))

    keys = sorted(o["Key"] for o in s3.list_objects_v2(Bucket=args.bucket, Prefix="images/").get("Contents", [])
                  if label_of(o["Key"]))
    images = {k: s3.get_object(Bucket=args.bucket, Key=k)["Body"].read() for k in keys}
    ref = s3.get_object(Bucket=args.bucket, Key=args.reference)["Body"].read() if set("CE") & set(args.modes) else None
    def_ref = s3.get_object(Bucket=args.bucket, Key=args.def_reference)["Body"].read() if "E" in args.modes else None
    print(f"이미지 {len(keys)}장, 모델 {args.model}, 방식 {args.modes}\n")

    rows, summary = [], []
    for mode in args.modes:
        tp = fp = fn = tn = unk = low = 0
        lat, tin, tout = [], 0, 0
        for k in keys:
            t0 = time.time()
            resp = br.converse(modelId=args.model,
                               messages=[{"role": "user", "content": build_content(mode, images[k], ref, def_ref)}],
                               inferenceConfig={"maxTokens": 300, "temperature": 0})
            lat.append(time.time() - t0)
            tin += resp["usage"]["inputTokens"]
            tout += resp["usage"]["outputTokens"]
            pred, conf, reason = parse(resp["output"]["message"]["content"][0]["text"])
            truth = label_of(k)
            tp += truth == "DEFECT" and pred == "DEFECT"
            fn += truth == "DEFECT" and pred != "DEFECT"
            fp += truth == "OK" and pred == "DEFECT"
            tn += truth == "OK" and pred != "DEFECT"
            unk += pred == "UNKNOWN"
            low += conf.upper() == "LOW"
            mark = "O" if truth == pred else "X"
            print(f"[{mode}] {k.split('/')[-1]:<26} 정답 {truth:<6} AI {pred:<7} {conf:<6} {mark}  {reason}")
            rows.append({"mode": mode, "image": k, "truth": truth, "pred": pred, "confidence": conf,
                         "correct": mark, "latency_s": round(lat[-1], 2), "reason": reason})
        n = len(keys)
        summary.append({
            "mode": mode, "acc": (tp + tn) / n, "precision": tp / (tp + fp) if tp + fp else 0,
            "recall": tp / (tp + fn) if tp + fn else 0, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "unknown": unk, "low": low, "latency": sum(lat) / n, "tin": tin / n, "tout": tout / n,
        })
        print()

    names = {"A": "A 기본 프롬프트", "B": "B 도메인 프롬프트", "C": "C 기준 이미지 비교",
             "D": "D 균형 프롬프트", "E": "E 정상+불량 기준"}
    print(f"===== 결과 요약 ({args.model}, {len(keys)}장) =====")
    print(f"{'방식':<18}{'정확도':>8}{'정밀도':>8}{'재현율':>8}   TP FP FN TN  확신도LOW  평균지연  입력/출력 토큰(장당)")
    for s in summary:
        print(f"{names[s['mode']]:<16}{s['acc']:>8.0%}{s['precision']:>8.0%}{s['recall']:>8.0%}   "
              f"{s['tp']:>2} {s['fp']:>2} {s['fn']:>2} {s['tn']:>2}  {s['low']:>8}  {s['latency']:>6.2f}s  "
              f"{s['tin']:>6.0f} / {s['tout']:.0f}")

    out = f"experiment_{args.model.replace(':', '_')}.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\n상세 결과 저장: {out}")


if __name__ == "__main__":
    main()
