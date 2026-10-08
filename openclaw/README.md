# openclaw

[OpenClaw](https://docs.openclaw.ai/) 게이트웨이를 로컬에서 실행하기 위한 구성입니다. Docker Compose, Podman Quadlet, `podman kube play` 중 하나를 선택해 사용합니다.

게이트웨이는 `127.0.0.1:18789`에서만 열리며, Control UI는 `http://127.0.0.1:18789/`로 접속합니다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| `compose.yaml` | Docker Compose / podman-compose |
| `default.env`, `.env.example` | Compose 환경 변수 (`.env`는 선택) |
| `openclaw.quadlets` | Podman Quadlet (Pod, 볼륨, 컨테이너) |
| `pod.yaml` | `podman kube play`용 Pod, PVC, Secret |

## 게이트웨이 토큰

게이트웨이는 `--bind lan`으로 실행되므로 토큰 인증이 필요합니다. 토큰은 저장소에 포함하지 않으며 실행 전에 직접 생성합니다. 생성한 토큰은 Control UI 설정과 CLI 접속에 사용합니다.

```sh
openssl rand -hex 32
```

| 실행 방식 | 토큰 전달 방법 |
|---|---|
| Compose | `.env.example`을 `.env`로 복사한 뒤 `OPENCLAW_GATEWAY_TOKEN`에 입력 |
| Quadlet | podman secret `openclaw-gateway-token`을 미리 생성 |
| kube play | `pod.yaml`의 Secret `OPENCLAW_GATEWAY_TOKEN` 값을 교체 |

## 실행

### Docker Compose

```sh
cd openclaw
cp .env.example .env # OPENCLAW_GATEWAY_TOKEN 입력
docker compose config
docker compose up -d
```

CLI는 `tools` 프로필로 필요할 때만 실행합니다.

```sh
docker compose run --rm openclaw-cli <명령>
```

### Podman Quadlet

Podman 5.6 이상이 필요합니다. 서비스를 실행할 사용자 계정에서 secret을 한 번 생성합니다. secret은 재시작해도 유지됩니다.

```sh
openssl rand -hex 32 | tr -d '\n' | podman secret create openclaw-gateway-token -
podman quadlet install openclaw.quadlets
systemctl --user daemon-reload
systemctl --user start openclaw-pod
```

토큰 값 확인 및 교체는 다음과 같습니다. 교체 후에는 서비스를 재시작해야 반영됩니다.

```sh
podman secret inspect --showsecret --format '{{.SecretData}}' openclaw-gateway-token
openssl rand -hex 32 | tr -d '\n' | podman secret create --replace openclaw-gateway-token -
```

### podman kube play

`pod.yaml`의 `OPENCLAW_GATEWAY_TOKEN` 값을 교체한 뒤 실행합니다. 토큰을 넣은 `pod.yaml`은 커밋하지 않습니다.

```sh
podman kube play --replace pod.yaml
podman kube down pod.yaml
```

## 주의 사항

- `openclaw.json`의 `gateway.auth.token`이 설정되어 있으면 게이트웨이는 환경 변수보다 이 값을 우선합니다. 컨테이너 안에서 `onboard`나 `doctor --generate-gateway-token`을 실행하면 위에서 넣은 토큰과 달라질 수 있습니다.
- CLI는 반대로 `OPENCLAW_GATEWAY_TOKEN` 환경 변수를 우선합니다. 두 값이 다르면 `unauthorized: device token mismatch`로 실패합니다.
- 이미지는 `latest`를 사용합니다. 재현성이 필요하면 검증한 버전으로 고정합니다.

## 참고 자료

- [OpenClaw Docker 설치](https://docs.openclaw.ai/install/docker)
- [Gateway 설정](https://docs.openclaw.ai/gateway/config-gateway)
- [Podman Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
