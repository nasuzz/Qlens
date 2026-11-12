"""AI 판정 정확도 측정: API의 /inspections 결과를 파일명 라벨(cast_def_* / cast_ok_*)과 비교

사용법:  python scripts/accuracy.py https://xxxx.execute-api.ap-southeast-2.amazonaws.com/prod
같은 이미지를 여러 번 검사했다면 가장 최근 결과만 사용한다.
"""
import json
import sys
import urllib.request


def label_of(key):
    name = key.rsplit("/", 1)[-1].lower()
    if "_def_" in name:
        return "DEFECT"
    if "_ok_" in name:
        return "OK"
    return None


def main(api):
    with urllib.request.urlopen(api.rstrip("/") + "/inspections") as r:
        items = json.load(r)

    latest = {}
    for i in sorted(items, key=lambda x: x.get("inspectedAt", "")):
        latest[i["imageKey"]] = i

    tp = fp = fn = tn = 0
    rows = []
    for key, i in sorted(latest.items()):
        truth, pred = label_of(key), i.get("result")
        if truth is None:
            continue
        ok = truth == pred
        tp += truth == "DEFECT" and pred == "DEFECT"
        fn += truth == "DEFECT" and pred != "DEFECT"
        fp += truth == "OK" and pred == "DEFECT"
        tn += truth == "OK" and pred != "DEFECT"
        rows.append((key.rsplit("/", 1)[-1], truth, pred, "O" if ok else "X", i.get("reason", "")))

    n = tp + fp + fn + tn
    if not n:
        print("라벨이 있는 검사 결과가 없습니다.")
        return

    print(f"{'파일':<28}{'정답':<8}{'AI':<9}{'일치':<4} 근거")
    for r in rows:
        print(f"{r[0]:<28}{r[1]:<8}{r[2]:<9}{r[3]:<4} {r[4]}")

    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    print("\n혼동행렬 (양성 = DEFECT)")
    print(f"            예측 DEFECT  예측 OK")
    print(f"실제 DEFECT   {tp:>6}     {fn:>6}")
    print(f"실제 OK       {fp:>6}     {tn:>6}")
    print(f"\n정확도(Accuracy) : {(tp + tn) / n:.1%}  ({tp + tn}/{n})")
    print(f"정밀도(Precision): {precision:.1%}")
    print(f"재현율(Recall)   : {recall:.1%}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
