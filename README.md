# Docker 서비스 모음

Docker Compose 또는 `docker run`으로 실행할 수 있는 서비스별 배포 구성을 모아 둔 저장소입니다. 각 최상위 디렉터리는 독립적으로 사용할 수 있습니다.

## 포함된 서비스

- 모니터링: Grafana, Prometheus
- 웹 및 프록시: Nginx, Heimdall, Linkding
- 개발 도구: Gitea, Jenkins, Nexus, Dependency-Track
- 기타: Wiki.js, Step CA, Termix, BusyBox, LLM Registry

서비스별 Compose 파일, 설정 파일, 실행 스크립트는 해당 디렉터리에 있습니다. 예를 들어 Nginx 구성은 `nginx/`, Gitea 구성은 `gitea/`에서 관리합니다.

## 사전 준비

- Docker Engine
- Docker Compose 플러그인(`docker compose`)
- 서비스에서 요구하는 `.env`, 로컬 디렉터리, 포트

저장소의 설정은 로컬 환경에 맞게 작성되어 있을 수 있습니다. 실행 전에 이미지 버전, 공개 포트, 볼륨 경로, 사용자 ID를 반드시 확인하세요.

## 기본 사용법

실행하려는 서비스 디렉터리로 이동한 뒤 Compose 구성을 검증하고 시작합니다.

```sh
cd nginx
docker compose config
docker compose up -d
docker compose ps
docker compose logs -f
```

서비스를 중지하고 컨테이너를 제거하려면 다음을 실행합니다.

```sh
docker compose down
```

일부 디렉터리는 `nginx.sh`, `prometheus.sh` 같은 직접 실행용 스크립트도 제공합니다. 스크립트를 사용하기 전에 포트와 마운트 경로를 검토하세요.

## 설정과 보안

`.env`, API 키, 비밀번호, 인증서, 실행 중 생성된 데이터는 커밋하지 마세요. 필요한 설정 예제는 실제 값을 제거한 형태로 추가하고, 운영 환경에서는 가급적 이미지 태그를 명시적으로 고정하세요.

기여 방법과 검증 기준은 [AGENTS.md](AGENTS.md)를 참고하세요.
