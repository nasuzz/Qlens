# 클라우드 네이티브 기말 프로젝트 보고서

## Qlens — 생성형 AI 기반 서버리스 제조 불량 검사 시스템
**Amazon Bedrock을 활용한 주조 부품 품질 자동 판정 및 불량 알림 서비스**

202431534 나수경

> ✏️ 작성 메모 (제출 전 삭제)
> - 분량 목표: 표지 제외 10페이지 (1장 4p · 2장 2p · 3장 1.5p · 4장 2p)
> - `📸 [캡처]` 표시 위치에 화면 캡처를 넣는다.
> - `✏️` 표시는 본인 경험·소감으로 다듬을 부분이다.

---

## 1. 실습 해설

### 1.1 주제 소개

제조 현장의 품질 검사는 대부분 작업자의 육안에 의존한다. 육안 검사는 피로도와 숙련도에 따라 판정 편차가 크고, 검사 이력이 체계적으로 남지 않으며, 불량이 발생해도 담당자에게 즉시 전달되지 않는다는 한계가 있다.

**Qlens**(Quality + Lens)는 부품 사진을 올리기만 하면 클라우드가 자동으로 정상/불량을 판정하고, 결과를 이력으로 저장하며, 불량이 나오면 담당자에게 메일로 알리는 서비스이다. 검사 이력과 통계는 조회 API와 대시보드로 확인한다. 서버를 직접 운영하지 않는 **서버리스**, 기능별로 독립된 **마이크로서비스(MSA)**, 별도 모델 학습 없이 판정하는 **생성형 AI(Amazon Bedrock)**를 핵심 기술로 사용했다.

| 항목 | 내용 |
|---|---|
| 교재 실습 서비스 (택 1) | **AWS Lambda (서버리스)** — 교재의 Lambda 실습을 S3·DynamoDB·API Gateway와 엮어 하나의 서비스로 확장 |
| 데이터 | Kaggle *Casting Product Image Data for Quality Inspection* (펌프 임펠러 주조 부품, 300×300 흑백) |
| 사용 범위 | test 세트에서 무작위 선별한 **정상 10장 + 불량 10장** (파일명에 정답 라벨 `ok`/`def` 포함) |
| 리전 | 아시아 태평양 시드니 `ap-southeast-2` (무료 플랜 계정이 단일 리전에 고정되어 해당 리전에 구축) |
| AI 모델 | Amazon Nova Lite (`amazon.nova-lite-v1:0`, 이미지 입력 지원 멀티모달 모델) |

### 1.2 사용 서비스

| 구분 | 서비스 | 역할 |
|---|---|---|
| 수업에서 학습 | Amazon S3 | 검사 이미지(`images/`) 저장, 업로드 이벤트로 판정 시작 |
| | AWS Lambda | 판정 · 이력 조회 · 단건 조회 · 통계 · 데모 기능별 로직 (5개 함수) |
| | Amazon DynamoDB | 검사 이력(`QlensInspections`) |
| | Amazon API Gateway | 조회 · 데모용 **REST API**(`qlens-api`) |
| | Amazon Lightsail | 모니터링 대시보드 웹페이지 호스팅 (nginx) |
| 직접 조사·추가 | Amazon Bedrock | 이미지 기반 불량 판정 + 판정 근거를 자연어로 생성 |
| | Amazon SNS | 불량 발생 시 담당자 이메일 알림 |
| | Amazon CloudWatch | 전체 Lambda 실행 로그 · 지표 수집 |
| | AWS IAM | Lambda 실행 역할(`qlens-lambda-role`) 권한 관리 |

### 1.3 서비스별 구현 과정

**① 데이터 준비 및 Bedrock 연동 확인**
Kaggle 데이터셋에서 정상·불량 각 10장을 선별했다. Bedrock 콘솔의 Playground에서 Nova Lite에 부품 이미지를 넣어 판정 응답이 오는 것을 먼저 확인했다. 이때 정상 부품의 가운데 허브(원통 돌출부)를 "버(돌출 결함)"로 오판하는 사례를 발견했고, 이것이 뒤의 프롬프트 비교 실험(3.3절)의 출발점이 되었다.

📸 [캡처] Bedrock Playground에서 이미지 판정 응답

**② 판정 서비스 — S3 → Lambda → Bedrock → DynamoDB → SNS**
S3 버킷 `qlens-images-nsk2026`의 `images/` 접두사에 `ObjectCreated` 이벤트 트리거를 걸어, 사진이 올라오면 `qlens-inspect-image` Lambda가 자동 실행되도록 했다. **접두사 필터(`images/`)를 걸어** 기준 이미지(`reference/`) 등 다른 폴더의 파일은 판정 Lambda를 호출하지 않게 했다. Lambda는 Bedrock Converse API로 이미지를 보내 JSON 판정을 받고, 결과를 DynamoDB에 저장한 뒤 불량이면 SNS로 메일을 보낸다. Bedrock 호출 시간을 고려해 제한 시간은 1분으로 늘렸다.

📸 [캡처] S3 트리거 설정(접두사 `images/`) / DynamoDB 저장 항목 / 불량 알림 메일

**③ 조회 API — API Gateway(REST) + Lambda 3개**
`GET /inspections`, `GET /inspections/{id}`, `GET /stats`를 각각 독립된 Lambda에 **Lambda 프록시 통합**으로 연결하고 `prod` 스테이지로 배포했다. 대시보드가 다른 도메인에서 호출하므로 Lambda 응답 헤더에 `Access-Control-Allow-Origin: *`를 넣어 CORS를 처리했다.

📸 [캡처] API Gateway 리소스 트리

**④ 대시보드 — Lightsail**
Lightsail Ubuntu 인스턴스(최소 요금제)를 만들 때 **시작 스크립트**에 nginx 설치와 대시보드 HTML 배포를 넣어, SSH 접속 없이 자동으로 웹페이지가 올라가게 했다. 이후 고정 IP를 연결했다. 대시보드는 REST API를 호출해 KPI(총 검사·정상·불량·불량률·재검사 대기), 판정 비율, 불량 유형, 검사 이력을 보여준다.

📸 [캡처] 대시보드 전체 화면 (`http://13.238.80.95`)

**⑤ 직접 테스트(데모) — API Gateway `POST /demo` → Lambda → S3**
AWS 계정이 없는 사람도 전체 흐름을 확인할 수 있도록 대시보드에 "불량/정상 샘플 검사" 버튼을 두었다. 버튼을 누르면 `qlens-demo` Lambda가 S3에 있는 Kaggle 샘플 하나를 `images/demo-<시각>-<파일명>`으로 복사한다. 복사도 S3 업로드 이벤트이므로 ②의 판정 흐름이 그대로 실행되고, 대시보드는 2초 간격으로 조회 API를 확인해 결과가 저장되면 팝업과 표로 보여준다. 남용을 막기 위해 API Gateway 스테이지에 조절(요율 5, 버스트 10)을 걸었다.

📸 [캡처] 데모 버튼 클릭 후 뜬 판정 결과 팝업

**⑥ 사람 재검사(Human-in-the-loop)**
AI 판정을 그대로 확정하지 않도록, 모델이 확신도를 `LOW`로 답하거나 응답을 해석할 수 없으면 `reviewStatus=PENDING`으로 저장하고 "재검사 요청" 메일을 보낸다. 대시보드에는 재검사 대기 건수와 필터를 두었다.

### 1.4 주요 코드

**판정 — Bedrock Converse API 호출** (`lambdas/qlens-inspect-image`)
```python
PROMPT = """이 주조 부품(펌프 임펠러) 이미지를 보고 정상인지 불량인지 판정하세요.
다른 말 없이 아래 JSON으로만 답하세요.
{"result": "OK" 또는 "DEFECT", "defectType": "기공|균열|테두리 결함|버|표면 결함|없음",
 "confidence": "HIGH|MEDIUM|LOW", "reason": "판정 근거 한 문장"}"""

resp = bedrock.converse(
    modelId=MODEL_ID,                                   # amazon.nova-lite-v1:0
    messages=[{"role": "user", "content": [
        {"image": {"format": "jpeg", "source": {"bytes": image_bytes}}},
        {"text": PROMPT},
    ]}],
    inferenceConfig={"maxTokens": 300, "temperature": 0},
)
```

**저장 · 알림 · 재검사 분기**
```python
needs_review = item["result"] == "UNKNOWN" or item["confidence"].upper() == "LOW"
item["reviewStatus"] = "PENDING" if needs_review else "NONE"
table.put_item(Item=item)                                # DynamoDB 이력 저장
if item["result"] == "DEFECT" or needs_review:
    sns.publish(TopicArn=TOPIC_ARN, Subject=subject, Message=...)   # 메일 알림
```

### 1.5 문제 해결 과정

✏️ (본인 말로 다시 쓰기 — 아래는 실제로 겪은 문제 목록)
- **리전 고정**: 무료 플랜 계정이 시드니 리전에 고정되어 있어 서울 리전에서 리소스를 만들 수 없었다 → 전체를 `ap-southeast-2`에 구축
- **계정 혼동**: 루트 계정과 실습 계정을 오가다 IAM 역할이 "없다"고 보였다 → 계정 ID를 확인해 실습 계정으로 통일
- **SNS 구독 확인 메일 미수신**: 첫 메일 주소로는 확인 메일이 오지 않음 → 다른 주소로 구독, 미확인 구독은 3일 뒤 자동 만료
- **Lightsail 터미널 한글 깨짐**: 브라우저 터미널에 HTML을 붙여넣으면 한글이 깨짐 → 파일을 gzip+base64(영문·숫자만)로 바꿔 붙여넣고 서버에서 복원, md5로 동일성 확인
- **프롬프트 과잉 보정**: 오판을 고치려고 설명을 추가했더니 전부 정상으로 판정 → 실험으로 측정해 기본 프롬프트(A)로 되돌림 (3.4절)

---

## 2. 아키텍처

### 2.1 아키텍처 다이어그램

📸 [그림] `docs/architecture/qlens_architecture.png` (AWS 공식 Architecture Icons 사용)

**실선은 실제 구현해 동작하는 구성**(S3, Lambda 5개, Bedrock, DynamoDB, SNS, API Gateway(REST), Lightsail, CloudWatch, IAM)이고, **회색 점선은 확장 구상(가상 아키텍처, 미구현)**인 실시간 알림(WebSocket)과 일일 리포트(EventBridge)이다. 확장 구상은 4.2절에서 설명한다.

### 2.2 처리 흐름

| 흐름 | 트리거 | 경로 |
|---|---|---|
| ① 검사 | S3 업로드 이벤트 | S3 `images/` → `qlens-inspect-image` → Bedrock → DynamoDB → (불량) SNS 메일 |
| ② 조회 | HTTP 요청 | 대시보드·교수 → API Gateway(REST) → 조회 Lambda 3개 → DynamoDB |
| ③ 데모 | 대시보드 버튼 | API Gateway `POST /demo` → `qlens-demo` → S3 `images/`에 샘플 복사 → ① 실행 |

### 2.3 마이크로서비스(MSA) 설계

| 마이크로서비스 | Lambda 함수 | 트리거 / 엔드포인트 | 기능 |
|---|---|---|---|
| 판정 서비스 | `qlens-inspect-image` | S3 업로드 이벤트 | Bedrock 판정, 저장, 메일 |
| 이력 조회 서비스 | `qlens-get-inspections` | `GET /inspections` | 전체 이력 (`?result=`, `?review=` 필터) |
| 단건 조회 서비스 | `qlens-get-inspection` | `GET /inspections/{id}` | 특정 검사 결과 |
| 통계 서비스 | `qlens-get-stats` | `GET /stats` | 불량률, 유형별·일별 건수 |
| 데모 서비스 | `qlens-demo` | `POST /demo` | Kaggle 샘플을 S3 `images/`로 복사 → 판정 파이프라인 시작 (교수님 테스트용) |

각 기능을 독립된 Lambda로 분리해 **개별 배포·개별 확장**이 가능하다. 실제로 데모 기능을 추가할 때 판정 Lambda는 전혀 수정하지 않았다 — 데모 Lambda는 S3에 파일을 복사할 뿐이고, 판정은 기존 S3 이벤트가 그대로 처리한다. 서비스 간에는 직접 호출 대신 **이벤트(S3 업로드)와 공유 데이터 저장소(DynamoDB)**로 연결해 결합도를 낮췄다.

### 2.4 설계 판단

- **EC2 대신 Lambda**: 검사 요청은 사진이 올라올 때만 간헐적으로 발생하므로, 항상 켜져 있는 EC2보다 이벤트가 있을 때만 실행되고 실행한 만큼만 과금되는 Lambda가 비용·운영 면에서 적합하다. 서버 패치·확장 관리도 필요 없다.
- **REST API 선택**: 이력·통계 조회는 "요청하면 한 번 답하는" 작업이라 REST가 맞고, 브라우저 주소창으로 바로 열려 결과 확인 링크로 제출하기에도 적합하다. 불량 알림은 메일(SNS)로 충분해, 대시보드는 30초 주기 갱신(폴링)으로 단순하게 유지했다.
- **판정 모델로 Bedrock 선택**: 별도의 학습 데이터와 학습 서버 없이 바로 판정할 수 있고, 판정 근거를 자연어로 함께 제공한다. 모델은 환경 변수(`MODEL_ID`) 하나로 교체할 수 있게 설계했다.
- **보안 기본값**: S3 퍼블릭 액세스 차단 + SSE-S3 기본 암호화, Lambda는 전용 실행 역할로 필요한 서비스에만 접근한다. (과제 편의상 FullAccess 관리형 정책을 사용했으며, 운영 환경이라면 리소스 단위 최소 권한 정책으로 좁혀야 한다.)

---

## 3. 엔드포인트

### 3.1 접속 링크

> **모든 API 엔드포인트는 API Gateway → 엔드포인트별 독립 Lambda로 처리되는 서버리스·MSA 구조이다.** (상시 서버 없음, 엔드포인트마다 별도 함수 — 2.3절 표 참고)
> ※ 실습 확인용 엔드포인트이며, **공지 후 모든 서비스와 리소스를 삭제한다** (부록 체크리스트).

| 구분 | 주소 |
|---|---|
| 대시보드 (Lightsail) | http://13.238.80.95 |
| 검사 이력 API | https://6qymgjfjw4.execute-api.ap-southeast-2.amazonaws.com/prod/inspections |
| 불량만 조회 | https://6qymgjfjw4.execute-api.ap-southeast-2.amazonaws.com/prod/inspections?result=DEFECT |
| 단건 조회 API | https://6qymgjfjw4.execute-api.ap-southeast-2.amazonaws.com/prod/inspections/{inspectionId} |
| 데모 실행 API | `POST` https://6qymgjfjw4.execute-api.ap-southeast-2.amazonaws.com/prod/demo  (본문 `{"kind":"defect"}` 또는 `{"kind":"ok"}`) |
| 통계 API | https://6qymgjfjw4.execute-api.ap-southeast-2.amazonaws.com/prod/stats |

### 3.2 직접 테스트 방법 (교수님용)

1. 대시보드 http://13.238.80.95 접속
2. 맨 위 **🧪 직접 테스트해 보기**에서 **✖ 불량 샘플 검사** 또는 **✔ 정상 샘플 검사** 클릭
3. 샘플 사진이 S3에 업로드되고, 약 3초 뒤 오른쪽 아래에 판정 결과 팝업이 뜨며 검사 이력 표 맨 위에 추가된다

AWS 계정 없이 브라우저만으로 "업로드 → Bedrock 판정 → DynamoDB 저장 → 조회" 전체 흐름을 확인할 수 있다. API Gateway 스테이지 조절(요율 5, 버스트 10)로 과도한 호출을 제한했다.

### 3.3 호출 결과

`GET /stats` 응답 (20장 검사 후)
```json
{"total": 20, "defect": 13, "ok": 7, "unknown": 0, "review": 0, "defectRate": 0.65,
 "byType": {"표면 결함": 9, "균열": 4},
 "byDate": [{"date": "2026-11-12", "total": 20, "defect": 13, "defectRate": 0.65}]}
```
- `GET /inspections` → 200, 20건 최신순 / `GET /inspections/{id}` → 200, 존재하지 않는 ID는 **404**
- 모든 응답에 `Access-Control-Allow-Origin: *` 헤더 포함

📸 [캡처] 브라우저에서 `/stats`, `/inspections` 호출 결과

### 3.4 AI 판정 정확도

**(1) 판정 방식 비교 실험** — 같은 20장으로 프롬프트 5가지를 비교 (`scripts/experiment.py`, Nova Lite, temperature 0)

| 방식 | 내용 | 정확도 | 정밀도 | 재현율 | TP | FP | FN | TN | 평균 지연 | 입력 토큰/장 |
|---|---|---|---|---|---|---|---|---|---|---|
| **A 기본 프롬프트** | 정상/불량 판정만 지시 | **80%** | 75% | **90%** | 9 | 3 | 1 | 7 | **0.56s** | 690 |
| B 도메인 프롬프트 | 정상 구조 설명 + 불량 기준 + "애매하면 OK" | 50% | – | 0% | 0 | 0 | 10 | 10 | 2.50s | 1,172 |
| C 기준 이미지 | B + 정상 기준 사진 | 50% | – | 0% | 0 | 0 | 10 | 10 | 3.01s | 1,782 |
| D 균형 프롬프트 | 정상 구조 한 줄 + 불량 기준 ("애매하면 OK" 제거) | 50% | – | 0% | 0 | 0 | 10 | 10 | 2.50s | 1,007 |
| E 정상+불량 기준 | D + 정상·불량 기준 사진 (few-shot) | 60% | 100% | 20% | 2 | 0 | 8 | 10 | 2.99s | 2,169 |

📸 [캡처] CloudShell 실험 결과 요약 표

**발견점**
- Playground에서 정상 1장을 오판한 것을 보고 정상 구조 설명을 추가했는데(B), 오히려 **20장 전부를 정상으로 판정**하는 과잉 보정이 일어났다. "이건 결함이 아니다" 같은 예외 설명을 **한 줄만 남겨도**(D) 같은 현상이 나타났다. 경량 모델은 예외 설명이 들어가면 판정이 정상 쪽으로 크게 쏠린다.
- 기준 이미지를 함께 보내는 few-shot(E)은 불량이라고 한 것은 모두 맞혔지만(정밀도 100%), 불량 10장 중 2장만 찾았다.
- 품질 검사에서는 **불량을 놓치는 것(FN)이 정상을 잘못 잡는 것(FP)보다 훨씬 위험하다.** 놓친 불량품은 그대로 출하되지만, 잘못 잡힌 정상품은 사람이 재확인하면 된다. 따라서 재현율 90%로 가장 높고, 응답도 가장 빠르며, 토큰 비용도 가장 적은 **A를 서비스에 적용**했다.
- 그럴듯해 보이는 프롬프트 개선이 실제로는 성능을 떨어뜨릴 수 있으며, **정답 라벨로 측정해야만 알 수 있다**는 점을 확인했다.

**(2) 실제 서비스 정확도** — A 방식 적용 후 S3에 20장 업로드 (`scripts/accuracy.py`)

| | AI 불량 | AI 정상 |
|---|---|---|
| **실제 불량** | 9 | 1 |
| **실제 정상** | 4 | 6 |

정확도 **75%** (15/20) · 재현율 **90%** · 정밀도 69.2%
실험(80%)과 같은 설정이었음에도 정상 사진 1장의 판정이 달라졌다. temperature 0으로 설정해도 생성형 모델의 응답에는 약간의 변동성이 있음을 확인했다.

---

## 4. 미래 클라우드 방향 및 수업 후기

### 4.1 서버리스와 생성형 AI의 융합

이번 프로젝트에서 서버를 한 대도 직접 관리하지 않고 업로드 → AI 판정 → 저장 → 알림 → 조회까지 구성할 수 있었다. 각 기능은 이벤트가 있을 때만 실행되어 사진이 올라오지 않는 동안에는 비용이 거의 발생하지 않는다. 생성형 AI도 Bedrock처럼 **API 호출 한 번으로 쓰는 관리형 서비스**가 되면서, AI 기능이 별도 인프라가 아니라 서버리스 아키텍처의 한 부품처럼 조립되고 있다. 판정 모델을 환경 변수 하나로 교체할 수 있게 설계한 것처럼, 앞으로는 더 좋은 모델이 나오면 시스템 구조는 그대로 둔 채 모델만 갈아 끼우는 방식이 일반화될 것이다.

### 4.2 스마트팩토리 전망과 Qlens의 확장 방향 (가상 아키텍처)

아키텍처 다이어그램의 회색 점선 영역이 아래 확장 구상 중 일부를 나타낸다.

- **실시간 알림 (API Gateway WebSocket)**: 지금은 대시보드가 30초마다 조회(폴링)하므로 반영이 최대 30초 늦다. WebSocket 연결을 두면 판정 Lambda가 결과를 저장하자마자 접속 중인 대시보드로 바로 푸시할 수 있다.
- **일일 리포트 (EventBridge 스케줄)**: 매일 23:55에 Lambda를 실행해 당일 검사 결과를 집계하고 S3 `reports/`에 저장해 품질 담당자에게 보고한다.
- **현장 연결 (IoT Core)**: 사람이 사진을 올리는 대신 생산라인 카메라가 MQTT로 직접 전송하면 전수 검사가 가능해진다.
- **워크플로 (Step Functions)**: 판정 → 확신도 낮으면 재촬영·재검사 → 최종 확정 → 알림의 다단계 흐름을 상태 머신으로 관리할 수 있다.
- **인증 (Cognito)**: 검사자·관리자 로그인과 API 접근 제어를 추가한다.
- **단계적 모델 전략**: 지금은 범용 모델이라 정확도 75~80%에 한계가 있다. 운영 중 쌓인 판정 결과와 작업자 재검사 결과를 학습 데이터로 모으면, Bedrock 모델 맞춤화나 전용 비전 모델로 단계적으로 전환해 정확도를 높일 수 있다. 이번에 만든 재검사(Human-in-the-loop) 구조가 그 데이터를 모으는 출발점이 된다.

### 4.3 한계

- 20장 소규모 표본이라 정확도 수치의 신뢰구간이 넓다.
- 모델이 확신도를 거의 항상 `HIGH`로 답해 재검사 기능이 실제로 작동할 일이 드물었다. 모델이 스스로 보고하는 확신도는 그대로 믿기 어렵다.
- 무료 플랜 제약으로 리전이 시드니로 고정되었다. 국내 공장이라면 서울 리전에 두어 지연 시간을 줄이는 것이 바람직하다.

### 4.4 수업 후기

✏️ (본인 경험으로 작성 — 아래는 뼈대)
- 수업에서 배운 S3·Lambda·DynamoDB·API Gateway·Lightsail을 하나의 서비스로 엮어 보며 각 서비스의 역할 분담을 체감한 점
- Bedrock·SNS를 직접 조사해 붙이면서 막혔던 부분 (예: 리전 고정, SNS 구독 확인 메일, 새 콘솔 화면, Lightsail 터미널 한글 붙여넣기)과 해결 과정
- AI 판정 결과를 실험으로 측정하며 "그럴듯한 개선"이 실제로는 성능을 떨어뜨린 경험에서 배운 점
- 앞으로 클라우드·AI를 어떻게 활용하고 싶은지

---

## 부록. 리소스 정리 체크리스트 (공지 후 삭제)

- [ ] API Gateway `qlens-api`(REST)
- [ ] Lambda 5개 (`qlens-*`)
- [ ] DynamoDB `QlensInspections`
- [ ] S3 버킷 `qlens-images-nsk2026` (객체 비우기 → 버킷 삭제)
- [ ] SNS 토픽 `qlens-defect-alert` 및 구독
- [ ] Lightsail 인스턴스 `qlens-dashboard` **+ 고정 IP** (고정 IP만 남으면 과금)
- [ ] IAM 역할 `qlens-lambda-role`
- [ ] CloudWatch 로그 그룹 `/aws/lambda/qlens-*`
