# 저장소 기여 가이드

## 프로젝트 구조와 구성

이 저장소는 서로 독립적인 컨테이너 배포 구성을 모아 둔다. `nginx/`, `prometheus/`, `gitea/`, `wiki.js/` 같은 최상위 디렉터리 하나가 서비스 하나에 해당한다. 서비스 설정은 해당 서비스 디렉터리에 둔다. 예를 들어 Nginx 설정은 `nginx/config/`, Prometheus 설정은 `prometheus/`에 둔다. `.data/` 같은 실행 데이터는 예제 용도가 아니라면 추적하지 않는다.

## 서비스 파일 구성

새 서비스는 아래 파일 이름을 쓴다. 이미 있는 파일은 그 파일을 가리키는 경로를 함께 고칠 때만 이름을 바꾼다. YAML 확장자는 `yaml`을 쓴다.

| 파일 | 역할 |
|---|---|
| `compose.yaml` | Podman Compose와 Docker Compose가 함께 읽는 기본 정의. 선택 기동은 `profiles`로 나눈다. |
| `docker-compose.yaml` | Docker Compose만 읽는 정의 |
| `podman-compose.yaml` | Podman Compose만 읽는 정의 |
| `compose.override.yaml` | 기본 정의에 덧붙이는 Podman/Docker 호환 정의 |
| `pod.yaml` | `podman kube play`용 Pod 정의. Pod를 적극 사용한다. |
| `<service>.quadlets` | Pod, 볼륨, 컨테이너를 한 파일에 모은 Podman Quadlet |
| `default.env` | 기본 기동에 필요한 초기 환경 변수 |
| `.env` | 기동 시 `default.env`를 덮어쓰는 추가 환경 변수 |
| `example.env` | `.env`에 적을 키와 예시 |
| `README.md` | 해당 서비스의 기동 방법, 파일 역할, 포트, 주의 사항 |
| `nginx/<service>.conf` | 해당 서비스를 Nginx 뒤에 둘 때 쓰는 `server` 블록 |
| `caddy/<service>.caddyfile` | 해당 서비스를 Caddy 뒤에 둘 때 쓰는 사이트 블록 |

공통 정의는 `compose.yaml`에 둔다. 엔진마다 달라지는 부분만 `docker-compose.yaml` 또는 `podman-compose.yaml`에 둔다. 버전, 부가 서비스, 선택 기능처럼 함께 띄우지 않을 수 있는 서비스는 `profiles`로 나눈다. 기본 정의에 덧붙일 호환 설정은 `compose.override.yaml`에 둔다. 이 파일은 Compose가 있으면 자동으로 병합한다.

환경 변수는 다음 순서로 읽힌다. 뒤에 있는 값이 앞의 값을 덮어쓴다.

```yaml
env_file:
  - default.env
  - path: .env
    required: false
```

`default.env`에는 그대로 기동할 수 있는 초기 값을 둔다. 호스트마다 다른 값과 비밀은 `.env`에 두고, 그 키와 자리 표시자는 `example.env`에 적는다. `README.md`에는 Compose, Quadlet, `podman kube play` 중 제공하는 실행 방법을 각각 적는다.

### 리버스 프록시 설정

웹 UI나 HTTP API를 여는 서비스는 서비스 디렉터리 안에 `nginx/`와 `caddy/`를 만들고 서비스 이름으로 설정 파일을 둔다. `<service>`는 최상위 디렉터리 이름과 같게 쓴다. 예를 들어 `wiremock/`이라면 다음과 같다.

```text
wiremock/
  nginx/wiremock.conf
  caddy/wiremock.caddyfile
```

두 파일은 같은 호스트 이름과 같은 업스트림을 가리킨다. 업스트림은 Compose, Quadlet, `pod.yaml`이 공개하는 호스트 포트(예: `127.0.0.1:8080`)로 맞추고, 포트를 바꾸면 두 파일도 함께 고친다. 호스트 이름과 인증서 경로는 자리 표시자로 두고 실제 값은 커밋하지 않는다. WebSocket, 업로드 크기, 관리 경로 차단처럼 서비스에 필요한 설정은 두 파일에 같은 의미로 넣는다.

`nginx/<service>.conf`는 `server` 블록만 담아 프록시 쪽 `conf.d/`에서 바로 읽을 수 있게 한다. `caddy/<service>.caddyfile`은 사이트 블록만 담아 프록시 쪽 Caddyfile에서 `import`로 읽을 수 있게 한다. 최상위 `nginx/` 디렉터리는 Nginx 서비스 자체의 구성이고, 서비스별 프록시 설정은 각 서비스 디렉터리에 둔다. `README.md`에는 두 파일을 프록시에 연결하는 방법과 프록시 경로를 적는다.

## 실행 및 개발 명령어

저장소 전체를 대상으로 하는 빌드 명령은 없다. 작업할 서비스 디렉터리에서 다음 명령을 실행한다.

```sh
cd nginx
docker compose config                 # Compose 구성 파싱 및 검증
docker compose up -d                  # 백그라운드에서 서비스 시작
docker compose logs -f                # 시작 및 실행 로그 확인
docker compose down                   # 스택 중지 및 제거
```

도우미 스크립트가 있다면 포트와 볼륨 경로를 검토한 뒤 실행한다(예: `./prometheus.sh`). 이미지를 갱신할 때는 `docker compose pull`을 사용한다.

## 코딩 스타일과 이름 규칙

YAML은 공백 두 칸으로 들여쓰기하고 서비스와 디렉터리 이름은 소문자로 작성한다. 파일 이름은 [서비스 파일 구성](#서비스-파일-구성)을 따른다. 모호한 YAML 값은 따옴표로 감싸고 가능한 경우 상대 경로로 바인드 마운트한다. 셸 스크립트에는 올바른 shebang을 사용하고 `"$(pwd)"`처럼 경로를 인용하며 컨테이너 옵션은 한 줄에 하나씩 작성한다. Python 유틸리티는 PEP 8과 `snake_case`를 따른다.

## 테스트 지침

자동 테스트나 커버리지 기준은 없다. 변경한 모든 스택에서 `docker compose config`를 실행한 뒤 서비스를 시작한다. `podman-compose.yaml`을 바꾼 경우에는 `podman compose config`로 검증한다. 프록시 설정을 바꾼 경우에는 `nginx -t`와 `caddy validate --adapter caddyfile --config <file>`로 문법을 확인한다. `docker compose ps`와 `docker compose logs`로 컨테이너 상태, 공개 포트, 마운트 파일, 로그를 확인한다. 스모크 테스트에서 생성된 데이터는 커밋하지 않는다.

## 커밋과 Pull Request 지침

최근 커밋은 `gitea`, `heimdall`, `[fix]wiki.js`처럼 서비스 중심의 짧은 제목을 사용한다. 커밋 범위를 작게 유지하고 `nginx: exporter 상태 엔드포인트 활성화`처럼 대상과 작업을 명확히 적는다. 풀 리퀘스트에는 영향받는 서비스, 설정이나 포트 변경, 수행한 검증을 설명하고 관련 이슈를 연결한다. 화면 변경이 있을 때만 스크린샷을 첨부한다.

## 보안 및 설정 주의사항

`.env`, 비밀번호, API 키, 인증서, 호스트별 데이터는 커밋하지 않는다. 기동에 필요한 초기 값은 `default.env`에 두고, `.env`에 채워야 할 항목은 실제 비밀을 뺀 `example.env`로 안내한다. 실행 전 공개 포트와 쓰기 가능한 마운트를 검토한다.

## 이미지 태그

이 저장소는 실서버에 그대로 실행하지 않는 기준 파일이다. 버전 지정은 실서버 측 책임이다. Compose, Quadlet, `pod.yaml`의 이미지는 `latest` 태그로 쓴다. 버전별로 함께 제공해야 하는 구성(예: PostgreSQL 16, 17, 18)만 `profiles`로 나누고 주 버전 태그를 쓴다. 최신 이미지 기준으로 작성하되, `latest`가 가리키는 버전과 설정이 맞지 않으면 그 사실을 `README.md`에 적는다.
