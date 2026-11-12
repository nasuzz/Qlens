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
dashboard/index.html      Lightsail에 올릴 대시보드
scripts/accuracy.py       정확도 측정 (파일명 라벨 vs AI 판정)
data/images/              테스트 이미지 20장 (정상 10, 불량 10)
data/reference/           few-shot 기준용 정상 이미지 1장 (테스트 20장과 겹치지 않음)
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
| `qlens-inspect-image` | `TABLE_NAME=QlensInspections`<br>`TOPIC_ARN=<4단계 ARN>`<br>`MODEL_ID=amazon.nova-lite-v1:0`<br>`REFERENCE_KEY=reference/ok_reference.jpeg` | **1분**, 메모리 256MB |
| `qlens-get-inspections` | `TABLE_NAME=QlensInspections` | 10초 |
| `qlens-get-inspection` | `TABLE_NAME=QlensInspections` | 10초 |
| `qlens-get-stats` | `TABLE_NAME=QlensInspections` | 10초 |
| `qlens-daily-report` | `TABLE_NAME=QlensInspections`<br>`BUCKET_NAME=<2단계 버킷명>` | 30초 |

> `REFERENCE_KEY`를 비우면 기준 이미지 없이 프롬프트만으로 판정. 두 방식의 정확도를 비교해 보고서에 넣을 수 있다.
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

### 11. EventBridge 일일 리포트
`qlens-daily-report` → 트리거 추가 → **EventBridge (CloudWatch Events)** → 새 규칙 `qlens-daily-report-schedule` → 예약 표현식
`cron(55 14 * * ? *)`  ← UTC 14:55 = **한국시간 23:55** (그날 검사분 집계)

바로 확인하려면 Lambda **테스트** 탭에서 이벤트 `{}` 로 실행 → S3 `reports/YYYY-MM-DD.json` 생성 확인.

### 12. Lightsail 대시보드 `qlens-dashboard`
1. `dashboard/index.html`의 `REPLACE_ME` 줄을 9단계 호출 URL로 교체
2. Lightsail → 인스턴스 생성 → 리전 시드니 → **Linux/Unix → OS 전용 → Ubuntu** → 가장 작은 요금제(3개월 무료 표시된 것) → 이름 `qlens-dashboard`
3. 인스턴스 → **SSH를 사용하여 연결**(브라우저 터미널) →
   ```
   sudo apt-get update && sudo apt-get install -y nginx
   sudo nano /var/www/html/index.html
   ```
   기존 내용 지우고 수정한 `index.html` 전체 붙여넣기 → `Ctrl+O`, 엔터, `Ctrl+X`
4. 네트워킹 탭 → **고정 IP 생성 및 연결** → 브라우저에서 `http://<고정IP>` 접속

---

## API 명세
| Method | Path | 설명 |
|---|---|---|
| GET | `/inspections` | 검사 이력 (최신순). `?result=DEFECT` 또는 `?result=OK` 필터 |
| GET | `/inspections/{id}` | 검사 단건 |
| GET | `/stats` | `{ total, ok, defect, unknown, defectRate, byType, byDate[] }` |

## 리소스 정리 (공지 후)
API Gateway `qlens-api` → Lambda 5개 → DynamoDB `QlensInspections` → S3 버킷(객체 비우기 → 삭제) → SNS 토픽·구독 → EventBridge 규칙 → **Lightsail 인스턴스 + 고정 IP (고정 IP만 남으면 과금)** → IAM `qlens-lambda-role` → CloudWatch 로그 그룹 `/aws/lambda/qlens-*`
