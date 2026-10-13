# termix

[Termix](https://docs.termix.site/) SSH/RDP/VNC 웹 관리 도구를 로컬에서 실행하기 위한 구성입니다. 원격 데스크톱(RDP, VNC)을 처리하는 [guacd](https://guacamole.apache.org/)를 함께 실행합니다. Docker Compose, Podman Quadlet, `podman kube play` 중 하나를 선택해 사용합니다.

웹 UI는 `127.0.0.1:8080`에서만 열리며, `http://127.0.0.1:8080/`로 접속합니다. guacd(4822)는 인증 없이 동작하므로 호스트에 공개하지 않고 Termix 컨테이너에서만 접근합니다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| `compose.yml` | Docker Compose / podman-compose (Termix + guacd) |
| `default.env` | Compose 기본 환경 변수 (`.env`로 덮어쓰기 가능) |
| `termix.quadlets` | Podman Quadlet (Pod, 볼륨, Termix·guacd 컨테이너) |
| `pod.yaml` | `podman kube play`용 Pod, PVC, ConfigMap |

## 관리자 계정

별도 관리자 비밀번호 설정은 없으며, 처음 가입한 계정이 관리자가 됩니다. 서비스를 시작한 직후 바로 계정을 만들고, 필요하면 관리자 설정에서 신규 가입을 막습니다.

JWT 서명 키, 데이터베이스 암호화 키 같은 비밀값은 첫 실행 때 자동으로 생성되어 데이터 볼륨에 저장됩니다. 볼륨을 잃으면 저장된 호스트 자격 증명도 복호화할 수 없으므로 볼륨 전체를 백업합니다.

## 실행

### Docker Compose

```sh
cd termix
docker compose config
docker compose up -d
```

기본값을 바꾸려면 `.env`를 만들어 필요한 변수만 적습니다. `.env` 값이 `default.env`보다 우선합니다.

### Podman Quadlet

Podman 5.6 이상이 필요합니다.

```sh
podman quadlet install termix.quadlets
systemctl --user daemon-reload
systemctl --user start termix
```

Pod 안의 컨테이너는 네트워크를 공유하므로 `GUACD_HOST`, `GUACD_TUNNEL_HOST`를 `127.0.0.1`로 지정합니다. 두 컨테이너 모두 `AutoUpdate=registry`로 설정되어 있어 `podman auto-update`로 이미지를 갱신할 수 있습니다.

### podman kube play

```sh
podman kube play --replace pod.yaml
podman kube down pod.yaml
```

## SSH 전용으로 실행

원격 데스크톱이 필요 없으면 guacd 없이 실행할 수 있습니다.

| 실행 방식 | 방법 |
|---|---|
| Compose | `.env`에 `ENABLE_GUACAMOLE=false`를 적고 `docker compose up -d --no-deps termix` |
| Quadlet | `termix-app`에 `Environment=ENABLE_GUACAMOLE=false`를 추가하고 `termix-guacd` 섹션과 `Requires`/`After`를 제거 |
| kube play | ConfigMap에 `ENABLE_GUACAMOLE: "false"`를 추가하고 `guacd` 컨테이너를 제거 |

## 주의 사항

- 데이터(SQLite DB, 암호화 키, SSL 인증서, 세션 녹화)는 `/app/data`에 마운트한 `termix-vol` 볼륨에 저장됩니다. guacd도 같은 볼륨을 `/termix-data`에 마운트해 세션 녹화(`GUACD_RECORDING_PATH`)와 RDP 드라이브(`GUACD_DRIVE_PATH`) 파일을 씁니다.
- `PORT`를 바꾸면 컨테이너 내부 포트가 바뀌므로 Compose `ports`, Quadlet `PublishPort`, `pod.yaml`의 `containerPort`/`hostPort`도 함께 수정합니다.
- 상태 확인은 내부 백엔드의 `http://localhost:30001/health` 엔드포인트를 사용합니다. 이 포트는 공개하지 않습니다.
- 외부에서 접속해야 하면 포트를 직접 공개하기보다 TLS를 적용한 리버스 프록시 뒤에 둡니다.
- Termix 이미지는 `latest`, guacd는 `1.6.0`을 사용합니다. 재현성이 필요하면 Termix도 검증한 버전(예: `:2.8.0`)으로 고정합니다.

## 참고 자료

- [Termix Docker 설치](https://docs.termix.site/install/server/docker)
- [Termix upstream compose](https://github.com/Termix-SSH/Termix/blob/main/docker/docker-compose.yml)
- [guacd 이미지](https://hub.docker.com/r/guacamole/guacd)
- [Podman Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
