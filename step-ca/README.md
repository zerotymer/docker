# step-ca

[Smallstep `step-ca`](https://smallstep.com/docs/step-ca/)를 Docker Compose로 실행해 내부 인증 기관(Private CA)을 운영하기 위한 구성입니다.

CA 설정, 인증서, 개인 키와 데이터베이스는 호스트의 `./data`에 저장되며 컨테이너를 다시 생성해도 유지됩니다.

## 사전 준비

- Docker Engine
- Docker Compose v2 (`docker compose`)
- 선택 사항: 클라이언트에서 사용할 [`step` CLI](https://smallstep.com/docs/step-cli/installation/)
- CA에 사용할 DNS 이름이 이 호스트를 가리키도록 구성된 DNS

## 설정

예제 환경 파일을 복사합니다.

```sh
cd step-ca
cp .env.example .env
```

`.env`에서 환경에 맞게 다음 값을 수정합니다.

```dotenv
DOCKER_STEPCA_INIT_NAME="Internal CA"
DOCKER_STEPCA_INIT_DNS_NAMES="ca.example.net"
```

- `DOCKER_STEPCA_INIT_NAME`: 발급자(issuer)에 표시할 CA 이름
- `DOCKER_STEPCA_INIT_DNS_NAMES`: 클라이언트가 CA에 접속할 DNS 이름 또는 IP. 여러 값은 쉼표로 구분합니다.

초기화 환경 변수는 `data` 디렉터리가 비어 있는 **최초 실행 시에만** 적용됩니다. 운영을 시작한 뒤 값을 바꿔도 기존 CA 설정은 변경되지 않습니다.

> 운영 환경에서는 이미지 태그를 검증된 버전으로 고정하고, 암호를 환경 변수에 직접 저장하지 마세요. 암호 파일 또는 Docker Secret 사용을 권장합니다.

## 실행

Docker Compose로 CA를 시작합니다.

```sh
docker compose up -d
docker compose logs -f step-ca
```

최초 실행 로그에 출력되는 CA fingerprint와 초기 provisioner 정보를 안전한 장소에 보관합니다. 서비스는 호스트의 TCP `9000` 포트에서 열립니다.

상태를 확인합니다.

```sh
docker compose ps
curl --cacert data/certs/root_ca.crt \
  https://ca.example.net:9000/health
```

정상 응답은 다음과 같습니다.

```json
{"status":"ok"}
```

## 클라이언트 등록

CA 루트 인증서의 fingerprint를 확인합니다.

```sh
docker compose exec step-ca \
  step certificate fingerprint /home/step/certs/root_ca.crt
```

클라이언트에서 출력된 fingerprint를 사용해 CA 정보를 등록하고 루트 인증서를 내려받습니다.

```sh
step ca bootstrap \
  --ca-url https://ca.example.net:9000 \
  --fingerprint '<CA_FINGERPRINT>'
```

시스템 신뢰 저장소에도 루트 인증서를 설치하려면 다음 명령을 실행합니다. 이 작업은 해당 CA가 발급한 인증서를 시스템 전체에서 신뢰하게 하므로 관리 대상 장치에서만 수행하세요.

```sh
step certificate install "$(step path)/certs/root_ca.crt"
```

## 운영 명령

```sh
# 로그 확인
docker compose logs -f step-ca

# 재시작
docker compose restart step-ca

# 중지 및 컨테이너 제거 (data는 보존)
docker compose down

# 다시 시작
docker compose up -d
```

## 백업 및 보안

- `data`에는 루트/중간 CA 개인 키와 인증서 데이터베이스가 포함되므로 접근 권한을 최소화합니다.
- `data` 전체를 암호화된 저장소에 정기적으로 백업합니다.
- `docker compose down`은 `data`를 삭제하지 않지만, `data`를 직접 삭제하면 기존 CA를 복구할 수 없습니다.
- `9000` 포트는 필요한 내부 네트워크에만 노출하고 방화벽으로 접근을 제한합니다.
- 실제 운영에서는 `latest` 대신 검증한 버전(예: `smallstep/step-ca:0.30.2`)으로 고정해 예기치 않은 업그레이드를 방지합니다.

## 참고 자료

- [공식 Docker 이미지](https://hub.docker.com/r/smallstep/step-ca)
- [Docker로 step-ca 실행하기](https://smallstep.com/docs/tutorials/docker-tls-certificate-authority/)
- [step-ca 시작하기](https://smallstep.com/docs/step-ca/getting-started/)
