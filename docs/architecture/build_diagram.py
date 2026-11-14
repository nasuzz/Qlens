"""Qlens 아키텍처 다이어그램 생성기 (AWS 공식 Architecture Icons 사용)

사용법: python build_diagram.py <AWS 아이콘 패키지 압축 해제 폴더>
출력:  qlens_architecture.svg (같은 폴더) → 브라우저로 PNG 렌더링
아이콘 출처: https://aws.amazon.com/architecture/icons/  (Asset-Package_07312025)
"""
import base64
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
OUT = Path(__file__).with_name("qlens_architecture.svg")

ICONS = {
    "cloud": "Architecture-Group-Icons_07312025/AWS-Cloud-logo_32.svg",
    "region": "Architecture-Group-Icons_07312025/Region_32.svg",
    "s3": "Architecture-Service-Icons_07312025/Arch_Storage/48/Arch_Amazon-Simple-Storage-Service_48.svg",
    "lambda": "Architecture-Service-Icons_07312025/Arch_Compute/48/Arch_AWS-Lambda_48.svg",
    "bedrock": "Architecture-Service-Icons_07312025/Arch_Artificial-Intelligence/48/Arch_Amazon-Bedrock_48.svg",
    "dynamodb": "Architecture-Service-Icons_07312025/Arch_Database/48/Arch_Amazon-DynamoDB_48.svg",
    "sns": "Architecture-Service-Icons_07312025/Arch_App-Integration/48/Arch_Amazon-Simple-Notification-Service_48.svg",
    "apigw": "Architecture-Service-Icons_07312025/Arch_Networking-Content-Delivery/48/Arch_Amazon-API-Gateway_48.svg",
    "eventbridge": "Architecture-Service-Icons_07312025/Arch_App-Integration/48/Arch_Amazon-EventBridge_48.svg",
    "cloudwatch": "Architecture-Service-Icons_07312025/Arch_Management-Governance/48/Arch_Amazon-CloudWatch_48.svg",
    "lightsail": "Architecture-Service-Icons_07312025/Arch_Compute/48/Arch_Amazon-Lightsail_48.svg",
    "iam": "Architecture-Service-Icons_07312025/Arch_Security-Identity-Compliance/48/Arch_AWS-Identity-and-Access-Management_48.svg",
    "iot": "Architecture-Service-Icons_07312025/Arch_Internet-of-Things/48/Arch_AWS-IoT-Core_48.svg",
    "stepfn": "Architecture-Service-Icons_07312025/Arch_App-Integration/48/Arch_AWS-Step-Functions_48.svg",
    "cognito": "Architecture-Service-Icons_07312025/Arch_Security-Identity-Compliance/48/Arch_Amazon-Cognito_48.svg",
    "user": "Resource-Icons_07312025/Res_General-Icons/Res_48_Light/Res_User_48_Light.svg",
    "admin": "Resource-Icons_07312025/Res_General-Icons/Res_48_Light/Res_Authenticated-User_48_Light.svg",
    "email": "Resource-Icons_07312025/Res_General-Icons/Res_48_Light/Res_Email_48_Light.svg",
    "client": "Resource-Icons_07312025/Res_General-Icons/Res_48_Light/Res_Client_48_Light.svg",
    "camera": "Resource-Icons_07312025/Res_IoT/Res_AWS-IoT_Thing_Camera_48.svg",
    "bucket": "Resource-Icons_07312025/Res_Storage/Res_Amazon-Simple-Storage-Service_Bucket_48.svg",
}


def data_uri(name):
    raw = (ROOT / ICONS[name]).read_bytes()
    return "data:image/svg+xml;base64," + base64.b64encode(raw).decode()


W, H = 1960, 1170
ORANGE = "#c7511f"
TEAL = "#00a4a6"
GRAY = "#7d8998"
INK = "#232f3e"
VIRT = "#8c96a3"

parts = []
add = parts.append


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size=15, weight=600, color=INK, anchor="middle"):
    for i, line in enumerate(s.split("\n")):
        add(f'<text x="{x}" y="{y + i * (size + 4)}" font-size="{size}" font-weight="{weight}" '
            f'fill="{color}" text-anchor="{anchor}">{esc(line)}</text>')


def icon(name, cx, cy, label="", size=64, sub="", virtual=False, side="below"):
    op = ' opacity="0.45"' if virtual else ""
    add(f'<image href="{data_uri(name)}" x="{cx - size / 2}" y="{cy - size / 2}" width="{size}" height="{size}"{op}/>')
    if virtual:
        add(f'<rect x="{cx - size / 2 - 6}" y="{cy - size / 2 - 6}" width="{size + 12}" height="{size + 12}" '
            f'rx="6" fill="none" stroke="{VIRT}" stroke-width="1.5" stroke-dasharray="5 4"/>')
    if side == "right":
        x, y, anchor = cx + size / 2 + 12, cy - 2, "start"
    else:
        x, y, anchor = cx, cy + size / 2 + 20, "middle"
    if label:
        text(x, y, label, 15, 700, VIRT if virtual else INK, anchor)
        y += 19 * (label.count("\n") + 1)
    if sub:
        text(x, y, sub, 13, 500, VIRT if virtual else "#545b64", anchor)


def group(x, y, w, h, title, color=GRAY, icon_name=None, title_color=INK, title_right=False):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="{color}" stroke-width="2" stroke-dasharray="8 6"/>')
    tx = x + 14
    if icon_name:
        add(f'<image href="{data_uri(icon_name)}" x="{x}" y="{y}" width="40" height="40"/>')
        tx = x + 52
    if title_right:
        text(x + w - 14, y + 26, title, 16, 700, title_color, "end")
    else:
        text(tx, y + 26, title, 16, 700, title_color, "start")


def arrow(points, label="", lx=None, ly=None, virtual=False, both=False, anchor="middle"):
    color = VIRT if virtual else INK
    dash = ' stroke-dasharray="7 6"' if virtual else ""
    pts = " ".join(f"{x},{y}" for x, y in points)
    marker = "url(#ah-v)" if virtual else "url(#ah)"
    start = f' marker-start="{marker}"' if both else ""
    add(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"{dash} marker-end="{marker}"{start}/>')
    if label:
        if lx is None:
            (x1, y1), (x2, y2) = points[0], points[1]
            lx, ly = (x1 + x2) / 2, (y1 + y2) / 2 - 10
        text(lx, ly, label, 14, 700, VIRT if virtual else ORANGE, anchor)


# ---------- canvas ----------
add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
    f'font-family="\'Malgun Gothic\', \'Apple SD Gothic Neo\', \'Noto Sans KR\', sans-serif">')
add('<defs>'
    f'<marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{INK}"/></marker>'
    f'<marker id="ah-v" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{VIRT}"/></marker>'
    '</defs>')
add(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')

text(40, 52, "Qlens 시스템 아키텍처", 26, 800, INK, "start")
# legend
add(f'<line x1="1450" y1="44" x2="1510" y2="44" stroke="{INK}" stroke-width="2.5"/>')
text(1520, 50, "실제 구현", 15, 700, INK, "start")
add(f'<line x1="1640" y1="44" x2="1700" y2="44" stroke="{VIRT}" stroke-width="2.5" stroke-dasharray="7 6"/>')
text(1710, 50, "확장 구상 (가상)", 15, 700, VIRT, "start")

# AWS Cloud / Region
add(f'<rect x="260" y="80" width="1480" height="1060" fill="none" stroke="{INK}" stroke-width="2.5"/>')
add(f'<image href="{data_uri("cloud")}" x="260" y="80" width="44" height="44"/>')
text(318, 109, "AWS Cloud", 18, 700, INK, "start")
add(f'<rect x="290" y="138" width="1420" height="975" fill="none" stroke="{TEAL}" stroke-width="2.5" stroke-dasharray="10 7"/>')
add(f'<image href="{data_uri("region")}" x="290" y="138" width="40" height="40"/>')
text(342, 165, "Region: 아시아 태평양 시드니 (ap-southeast-2)", 17, 700, TEAL, "start")

# ---------- groups ----------
group(320, 190, 740, 265, "판정 서비스  (S3 이벤트 기반)")
group(320, 505, 175, 325, "대시보드", ORANGE)
group(545, 505, 515, 325, "조회 API 서비스  (REST)")
group(320, 865, 740, 175, "리포트 서비스  (스케줄 기반)")
group(1370, 505, 340, 325, "실시간 알림 (WebSocket)", title_right=True)
group(1300, 865, 410, 175, "모니터링 · 권한")

# ---------- actors (outside cloud) ----------
icon("camera", 120, 235, "생산라인 카메라", 56, "(가상)", virtual=True)
icon("user", 120, 370, "검사자", 64)
icon("admin", 120, 665, "관리자 · 교수", 64)
icon("email", 1850, 370, "품질 담당자", 64, "이메일 수신")
icon("client", 1850, 585, "대시보드 화면", 64, "실시간 팝업")

# ---------- row 1: inspection ----------
icon("iot", 400, 255, "AWS IoT Core", 48, "(가상)", virtual=True, side="right")
icon("s3", 405, 370, "Amazon S3", 64, "images/")
icon("bedrock", 660, 255, "Amazon Bedrock", 52, "Nova Lite", side="right")
icon("lambda", 660, 370, "AWS Lambda", 64, "qlens-inspect-image")
icon("stepfn", 855, 255, "AWS Step Functions", 48, "(가상) 워크플로", virtual=True, side="right")
icon("sns", 1180, 370, "Amazon SNS", 64, "qlens-defect-alert")
icon("dynamodb", 1180, 680, "Amazon DynamoDB", 64, "QlensInspections")

arrow([(160, 235), (368, 252)], "MQTT", 212, 228, virtual=True)
arrow([(400, 287), (400, 330)], virtual=True)
arrow([(160, 370), (365, 370)], "부품 사진\n업로드", 212, 340)
arrow([(445, 370), (620, 370)], "ObjectCreated", 532, 357)
arrow([(660, 330), (660, 287)], "이미지 / 판정 JSON", 648, 314, both=True, anchor="end")
arrow([(700, 370), (1140, 370)], "불량(DEFECT)일 때 알림", 930, 357)
arrow([(1220, 370), (1806, 370)], "이메일 발송", 1500, 357)
arrow([(660, 448), (660, 478), (1180, 478), (1180, 640)])
text(1192, 560, "판정 결과 저장", 14, 700, ORANGE, "start")
arrow([(1180, 478), (1450, 478), (1450, 552)])
text(1320, 469, "판정 결과 푸시", 14, 700, ORANGE)

# ---------- row 2: query API ----------
icon("lightsail", 407, 650, "Amazon Lightsail", 64, "qlens-dashboard")
icon("cognito", 610, 572, "Amazon Cognito", 44, "(가상) 인증", virtual=True, side="right")
icon("apigw", 610, 690, "API Gateway", 64, "qlens-api")
arrow([(160, 665), (370, 655)], "HTTP", 212, 650)
arrow([(445, 665), (572, 685)], "REST\n호출", 520, 636)
arrow([(610, 652), (610, 600)], virtual=True)

for i, (route, name) in enumerate([
    ("GET /inspections", "qlens-get-inspections"),
    ("GET /inspections/{id}", "qlens-get-inspection"),
    ("GET /stats", "qlens-get-stats"),
]):
    y = 600 + i * 90
    add(f'<image href="{data_uri("lambda")}" x="{815}" y="{y - 22}" width="44" height="44"/>')
    text(868, y - 3, route, 14, 700, ORANGE, "start")
    text(868, y + 15, name, 13, 500, "#545b64", "start")
    arrow([(650, 690), (775, 690), (775, y), (810, y)])
    add(f'<polyline points="1035,{y} 1100,{y}" fill="none" stroke="{INK}" stroke-width="2"/>')
add(f'<line x1="1100" y1="600" x2="1100" y2="780" stroke="{INK}" stroke-width="2"/>')
arrow([(1100, 680), (1143, 680)])
text(1121, 668, "조회", 14, 700, ORANGE)

# ---------- row 3: daily report ----------
icon("eventbridge", 405, 940, "Amazon EventBridge", 56, "매일 23:55 (KST)")
icon("lambda", 660, 940, "AWS Lambda", 56, "qlens-daily-report")
icon("bucket", 930, 940, "Amazon S3", 56, "reports/날짜.json")
arrow([(440, 940), (625, 940)], "스케줄 실행", 532, 927)
arrow([(695, 940), (895, 940)], "리포트 저장", 795, 927)
arrow([(660, 1033), (660, 1085), (1265, 1085), (1265, 680), (1220, 680)])
text(1000, 1076, "당일 검사 결과 조회", 14, 700, ORANGE)

# ---------- realtime (WebSocket) ----------
icon("apigw", 1450, 585, "API Gateway", 56, "WebSocket · qlens-ws")
icon("lambda", 1450, 745, "AWS Lambda", 44, "qlens-ws-connection")
icon("dynamodb", 1620, 745, "Amazon DynamoDB", 44, "QlensConnections")
arrow([(1478, 585), (1806, 585)], "실시간 푸시", 1660, 572)
arrow([(1450, 662), (1450, 718)])
text(1462, 694, "$connect · $disconnect", 12, 600, ORANGE, "start")
arrow([(1474, 745), (1594, 745)])
text(1534, 735, "접속 목록", 12, 600, ORANGE)

# ---------- monitoring / IAM ----------
icon("cloudwatch", 1420, 950, "Amazon CloudWatch", 56, "Lambda 로그 · 지표")
icon("iam", 1600, 950, "AWS IAM", 56, "qlens-lambda-role")

add("</svg>")
OUT.write_text("\n".join(parts), encoding="utf-8")
print(f"wrote {OUT}")
