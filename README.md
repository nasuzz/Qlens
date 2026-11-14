# Qlens — 생성형 AI 기반 서버리스 제조 불량 검사 시스템

주조 부품 사진을 S3에 올리면 Amazon Bedrock(Nova Lite)이 정상/불량을 판정하고, DynamoDB에 저장하고, 불량이면 SNS로 메일을 보낸다.

- **리전: 아시아 태평양(시드니) `ap-southeast-2`** — 무료 플랜 계정이 이 리전에 고정되어 있음. 모든 리소스를 여기에 만든다.
- **AI 모델:** `amazon.nova-lite-v1:0`

## 폴더 구조
```
lambdas/
  qlens-inspect-image/    판정 서비스 (S3 트리거 → Bedrock → DynamoDB → SNS)
  qlens-get-inspections/  GET /inspections        (?result=DEFECT|OK)
  qlens-get-inspection/   GET /inspections/{id}
  qlens-get-stats/        GET /stats
  qlens-daily-report/     EventBridge 매일 → S3 reports/
  qlens-ws-connection/    WebSocket $connect/$disconnect → DynamoDB QlensConnections
dashboard/index.html      Lightsail에 올릴 대시보드
scripts/accuracy.py       정확도 측정 (파일명 라벨 vs AI 판정)
scripts/experiment.py     판정 방식(프롬프트) 비교 실험 — CloudShell용
scripts/lightsail_*.sh    Lightsail 시작 스크립트 / 대시보드 업데이트 스크립트
docs/architecture/        아키텍처 다이어그램 (AWS 공식 아이콘)
data/images/              테스트 이미지 20장 (정상 10, 불량 10)
data/reference/           비교 실험 C·E용 기준 이미지 (정상 1, 불량 1 — 테스트 20장과 겹치지 않음)
```

---

## 구축 순서 (콘솔)

> 각 서비스에 들어갈 때마다 주소창에 `ap-southeast-2`가 있는지 확인.

### 1. IAM 역할 `qlens-lambda-role`
IAM → 역할 → 역할 생성 → 신뢰 엔터티 **AWS 서비스 / Lambda** → 아래 정책 5개 연결 → 이름 `qlens-lambda-role`
- `AWSLambdaBasicExecutionRole` (CloudWatch 로그)
- `AmazonS3FullAccess`
- `AmazonDynamoDBFullAccess`
- `AmazonSNSFullAccess`
- `AmazonBedrockFullAccess`

> 과제용으로 단순하게 FullAccess 사용. 보고서에는 "운영 환경이라면 최소 권한 정책으로 좁힌다"고 적으면 좋다.

### 2. S3 버킷
S3 → 버킷 만들기 → 이름 `qlens-images-<본인식별자>` (전 세계 유일해야 함) → 나머지 기본값.
- 버킷 안에 `reference/` 폴더를 만들고 `data/reference/ok_reference.jpeg` 업로드
- `images/` 폴더도 만들어 두기 (이미지는 **8단계에서** 업로드)

### 3. DynamoDB 테이블
DynamoDB → 테이블 생성 → 이름 `QlensInspections`, 파티션 키 `inspectionId` (문자열) → 테이블 설정 **사용자 지정** → 용량 모드 **온디맨드** → 생성

### 4. SNS 토픽
SNS → 주제 → 생성 → 유형 **표준**, 이름 `qlens-defect-alert` → 생성 후 **구독 생성** → 프로토콜 **이메일**, 엔드포인트 본인 메일
→ **메일함에서 Confirm subscription 클릭** (안 하면 메일 안 옴). 토픽 ARN 복사해 두기.

### 5. Lambda 함수 5개
Lambda → 함수 생성 → 새로 작성 → 런타임 **Python 3.12** → 실행 역할 **기존 역할 사용: `qlens-lambda-role`**
→ 생성 후 코드 편집기의 `lambda_function.py`를 이 저장소의 같은 이름 파일 내용으로 **통째로 교체 → Deploy**

| 함수 | 환경 변수 (구성 → 환경 변수) | 제한 시간 (구성 → 일반 구성) |
|---|---|---|
| `qlens-inspect-image` | `TABLE_NAME=QlensInspections`<br>`TOPIC_ARN=<4단계 ARN>`<br>`MODEL_ID=amazon.nova-lite-v1:0` | **1분**, 메모리 256MB |
| `qlens-get-inspections` | `TABLE_NAME=QlensInspections` | 10초 |
| `qlens-get-inspection` | `TABLE_NAME=QlensInspections` | 10초 |
| `qlens-get-stats` | `TABLE_NAME=QlensInspections` | 10초 |
| `qlens-daily-report` | `TABLE_NAME=QlensInspections`<br>`BUCKET_NAME=<2단계 버킷명>` | 30초 |

> 프롬프트는 비교 실험(10-1단계)에서 1위인 'A 기본 프롬프트'를 사용한다.
> 판정 시 `on-demand throughput isn't supported` 오류가 나면 `MODEL_ID`를 `apac.amazon.nova-lite-v1:0`(추론 프로파일)로 변경.

### 6. S3 트리거 연결 (`qlens-inspect-image`)
함수 개요 → **트리거 추가** → S3 → 버킷 선택 → 이벤트 유형 **모든 객체 생성 이벤트** → **접두사 `images/`** (필수! 없으면 reports/ 저장 시에도 실행됨) → 재귀 호출 경고 체크 → 추가

### 7. 동작 확인 (이미지 1장)
S3 `images/`에 `data/images/cast_def_0_1171.jpeg` 하나만 업로드 →
- DynamoDB `QlensInspections` → 항목 탐색에 결과가 생겼는지
- 불량 판정이면 메일 수신
- 안 되면 CloudWatch → 로그 그룹 `/aws/lambda/qlens-inspect-image` 에서 에러 확인

### 8. 나머지 19장 업로드
S3 콘솔에서 `data/images/` 안의 나머지 파일을 드래그 앤 드롭으로 `images/`에 업로드. (불량 10장 → 메일 약 10통)

### 9. API Gateway `qlens-api`
API Gateway → **REST API** 구축 → 이름 `qlens-api`
1. 리소스 `/inspections` 생성 → **GET** 메서드 → 통합 유형 Lambda, **Lambda 프록시 통합 ON** → `qlens-get-inspections`
2. `/inspections` 아래에 리소스 `{id}` 생성 (경로 `/inspections/{id}`) → **GET** → 프록시 ON → `qlens-get-inspection`
3. 리소스 `/stats` 생성 → **GET** → 프록시 ON → `qlens-get-stats`
4. **API 배포** → 새 스테이지 `prod` → **호출 URL** 복사 (예: `https://abcd123.execute-api.ap-southeast-2.amazonaws.com/prod`)

브라우저로 확인: `<호출URL>/inspections`, `<호출URL>/stats`, `<호출URL>/inspections/<검사ID>`

> CORS: Lambda 응답에 `Access-Control-Allow-Origin: *`가 들어 있어 GET 호출은 추가 설정 없이 대시보드에서 동작.

### 10. 정확도 측정
```
python scripts/accuracy.py <호출URL>
```
파일별 O/X, 혼동행렬, 정확도·정밀도·재현율 출력 → 보고서 3장에 사용.

### 10-1. 판정 방식 비교 실험 (CloudShell)
콘솔 아래쪽 **CloudShell** 클릭 → 오른쪽 위 **작업 → 파일 업로드** → `scripts/experiment.py` 업로드 →
```
python3 experiment.py <버킷이름>                               # Nova Lite로 A/B/C 비교
python3 experiment.py <버킷이름> --model amazon.nova-pro-v1:0  # (선택) Nova Pro 비교
```
A 기본 프롬프트 / B 도메인 프롬프트 / C 기준 이미지 비교의 정확도·정밀도·재현율·지연시간·토큰 표 출력 → 보고서용.
DynamoDB·SNS는 건드리지 않음(메일 안 감). 상세 결과는 `experiment_*.csv` → **작업 → 파일 다운로드**로 받기.

### 11. EventBridge 일일 리포트
`qlens-daily-report` → 트리거 추가 → **EventBridge (CloudWatch Events)** → 새 규칙 `qlens-daily-report-schedule` → 예약 표현식
`cron(55 14 * * ? *)`  ← UTC 14:55 = **한국시간 23:55** (그날 검사분 집계)

바로 확인하려면 Lambda **테스트** 탭에서 이벤트 `{}` 로 실행 → S3 `reports/YYYY-MM-DD.json` 생성 확인.

### 12. Lightsail 대시보드 `qlens-dashboard`
1. `dashboard/index.html`의 `API_URL` 기본값을 9단계 호출 URL로 설정 (현재: `https://6qymgjfjw4.execute-api.ap-southeast-2.amazonaws.com/prod`)
2. Lightsail → 인스턴스 생성 → 리전 시드니 → **Linux/Unix → OS 전용 → Ubuntu** → 가장 작은 요금제($5, Dual-stack) → 이름 `qlens-dashboard`
3. **Advanced settings → Launch script**에 `scripts/lightsail_launch.sh` 내용 전체 붙여넣기
   (nginx 설치 + `index.html` 배포를 자동 수행, SSH 불필요. Lightsail 시작 스크립트 한도 16KB 이내)
4. 네트워킹 탭 → **Attach static IP** → 브라우저에서 `http://<고정IP>` 접속 (현재: `http://13.238.80.95`)

---

### 13. 실시간 알림 (WebSocket) — 확장 기능
판정이 끝나는 순간 대시보드에 팝업으로 푸시한다 (폴링 30초 → 수 초).
1. IAM `qlens-lambda-role`에 `AmazonAPIGatewayInvokeFullAccess` 연결 (`execute-api:ManageConnections` 권한)
2. DynamoDB 테이블 `QlensConnections` (파티션 키 `connectionId`, 문자열)
3. Lambda `qlens-ws-connection` — 환경 변수 `CONN_TABLE=QlensConnections`
4. API Gateway → **WebSocket API** `qlens-ws`, 라우트 선택 표현식 `request.body.action`,
   라우트 `$connect` · `$disconnect` · `$default` 모두 → `qlens-ws-connection`, 스테이지 `prod`
5. `qlens-inspect-image` 환경 변수 추가
   - `CONN_TABLE=QlensConnections`
   - `WS_ENDPOINT=https://<ws-api-id>.execute-api.ap-southeast-2.amazonaws.com/prod` (wss:// 아님, /@connections 없음)
6. `dashboard/index.html`의 `WS_URL`을 `wss://<ws-api-id>.execute-api.ap-southeast-2.amazonaws.com/prod`로 설정 → Lightsail 반영
   - Lightsail 브라우저 SSH는 한글 붙여넣기가 깨지므로 `scripts/lightsail_update_dashboard.sh`(gzip+base64, ASCII 전용)를
     **Paste into terminal** 버튼으로 붙여넣는다. 마지막 줄 md5 값이 일치하면 성공.

동작: 대시보드 접속 → `$connect`로 connectionId 저장 → 판정 Lambda가 결과 저장 후 `post_to_connection`으로 전원에게 전송
→ 대시보드가 팝업 표시 + 즉시 갱신. 끊긴 연결(GoneException)은 자동 삭제, 대시보드는 5분마다 ping·끊기면 자동 재연결.

## API 명세
| Method | Path | 설명 |
|---|---|---|
| GET | `/inspections` | 검사 이력 (최신순). `?result=DEFECT`·`?result=OK`·`?review=PENDING` 필터 |
| GET | `/inspections/{id}` | 검사 단건 |
| GET | `/stats` | `{ total, ok, defect, unknown, review, defectRate, byType, byDate[] }` |

## 재검사(Human-in-the-loop)
AI 확신도가 `LOW`이거나 응답을 해석하지 못하면 `reviewStatus=PENDING`으로 저장하고 SNS로 **[Qlens] 재검사 요청** 메일을 보낸다.
AI 판정을 그대로 확정하지 않고 애매한 건은 작업자가 최종 확인하는 구조. 대시보드에 "재검사 필요" 건수·필터 표시.

## 리소스 정리 (공지 후)
API Gateway `qlens-api`·`qlens-ws` → Lambda 6개 → DynamoDB `QlensInspections`·`QlensConnections` → S3 버킷(객체 비우기 → 삭제) → SNS 토픽·구독 → EventBridge 규칙 → **Lightsail 인스턴스 + 고정 IP (고정 IP만 남으면 과금)** → IAM `qlens-lambda-role` → CloudWatch 로그 그룹 `/aws/lambda/qlens-*`
