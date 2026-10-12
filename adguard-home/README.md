# adguard-home

[AdGuard Home](https://adguard.com/adguard-home/overview.html) 네트워크 단위 광고·추적 차단 DNS 서버를 실행하기 위한 구성입니다. Docker Compose, Podman Quadlet, `podman kube play` 중 하나를 선택해 사용합니다.

다른 기기가 DNS 서버로 사용해야 하므로 다른 스택과 달리 모든 인터페이스에 포트를 공개합니다. 최초 실행 후 `http://<호스트>:3000/`에서 설정 마법사를 진행합니다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| `compose.yml` | Docker Compose / podman-compose |
| `adguard-home.quadlets` | Podman Quadlet (Pod, 볼륨, 컨테이너) |
| `pod.yaml` | `podman kube play`용 Pod, PVC |

## 포트

| 호스트 | 컨테이너 | 용도 |
|---|---|---|
| `53/tcp`, `53/udp` | `53` | 일반 DNS |
| `80/tcp` | `80` | 웹 UI (설정 마법사에서 80 선택 시) |
| `443/tcp`, `443/udp` | `443` | HTTPS 웹 UI, DNS-over-HTTPS (HTTP/3 포함) |
| `3000/tcp` | `3000` | 최초 설정 마법사 |
| `853/tcp` | `853` | DNS-over-TLS |
| `853/udp` | `853` | DNS-over-QUIC |
| `5443/tcp`, `5443/udp` | `5443` | DNSCrypt |

설정 마법사에서 웹 UI 포트는 컨테이너 기준 `80`, DNS 포트는 `53`으로 둡니다. 다른 값을 고르면 포트 매핑도 함께 바꿉니다. 암호화 DNS(DoH, DoT, DoQ, DNSCrypt)는 설정에서 인증서를 등록해야 동작하며, 쓰지 않으면 해당 포트는 지워도 됩니다. DNS-over-QUIC의 구버전 포트(`784`, `8853`)는 `AdGuardHome.yaml`의 `port_dns_over_quic`를 바꾼 경우에만 매핑을 추가합니다.

같은 호스트에서 `heimdall`(80, 443)이나 `grafana`, `wiki.js`, `llm-registry`(3000)를 함께 실행하면 포트가 충돌합니다. 한쪽의 호스트 포트를 바꿉니다.

## 사전 준비

### systemd-resolved 충돌

Ubuntu 등 systemd-resolved를 쓰는 호스트는 `127.0.0.53:53`을 이미 사용하므로 53번 포트 바인딩이 실패합니다. 스텁 리스너를 끄고 호스트 DNS를 다시 연결합니다.

```sh
sudo mkdir -p /etc/systemd/resolved.conf.d
printf '[Resolve]\nDNS=127.0.0.1\nDNSStubListener=no\n' | sudo tee /etc/systemd/resolved.conf.d/adguardhome.conf
sudo ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf
sudo systemctl reload-or-restart systemd-resolved
```

이 설정 후에는 호스트도 AdGuard Home으로 이름을 조회하므로, 컨테이너가 떠 있지 않으면 이미지를 받을 수 없습니다. 위 명령보다 먼저 `docker compose pull` 또는 `podman pull docker.io/adguard/adguardhome:latest`로 이미지를 받아 둡니다.

### rootless Podman의 낮은 포트

rootless Podman은 기본적으로 1024 미만 포트(53, 80, 443, 853)를 열 수 없습니다. 비특권 포트 시작값을 낮추거나 rootful로 실행합니다.

```sh
echo 'net.ipv4.ip_unprivileged_port_start=53' | sudo tee /etc/sysctl.d/90-unprivileged-port.conf
sudo sysctl --system
```

## 실행

### Docker Compose

```sh
cd adguard-home
docker compose config
docker compose up -d
```

### Podman Quadlet

Podman 5.6 이상이 필요합니다.

```sh
podman quadlet install adguard-home.quadlets
systemctl --user daemon-reload
systemctl --user start adguard-home
```

rootful로 실행할 때는 `sudo podman quadlet install adguard-home.quadlets` 후 `sudo systemctl daemon-reload`, `sudo systemctl start adguard-home`을 사용합니다.

컨테이너는 `AutoUpdate=registry`로 설정되어 있어 `podman auto-update`로 이미지를 갱신할 수 있습니다.

### podman kube play

```sh
podman kube play --replace pod.yaml
podman kube down pod.yaml
```

## 주의 사항

- 3000번 설정 마법사는 인증 없이 열리므로 먼저 접속한 사람이 관리자 계정을 만들 수 있습니다. 실행 직후 마법사를 완료합니다. 완료 후에는 웹 UI가 80번으로 옮겨가 3000번은 쓰이지 않으므로 매핑을 지워도 됩니다.
- 포트가 모든 인터페이스에 열리므로 공인 IP가 있는 호스트에서는 방화벽으로 53, 80, 3000번을 내부망에만 허용합니다. 외부에 열린 DNS 서버는 DNS 증폭 공격에 악용됩니다. Docker가 공개한 포트는 ufw 규칙을 우회하므로 `DOCKER-USER` 체인이나 상위 방화벽에서 막습니다.
- 설정(`AdGuardHome.yaml`)은 `/opt/adguardhome/conf`, 쿼리 로그·통계·필터 데이터는 `/opt/adguardhome/work`에 저장됩니다. 볼륨을 지우면 관리자 계정과 설정도 함께 사라집니다.
- `/opt/adguardhome` 전체를 마운트하면 이미지 안의 실행 파일까지 볼륨에 복사되어 이미지를 갱신해도 버전이 바뀌지 않습니다. 반드시 `work`, `conf`를 따로 마운트합니다.
- DHCP 서버 기능은 브리지 네트워크에서 동작하지 않습니다. 필요하면 호스트 네트워크(`network_mode: host`, Quadlet `Network=host`)로 바꾸고 포트 매핑을 제거합니다.
- rootless Podman은 네트워크 백엔드에 따라 쿼리 로그에 실제 클라이언트 IP 대신 내부 주소가 기록될 수 있습니다. 클라이언트별 통계가 중요하면 rootful 또는 호스트 네트워크로 실행합니다.
- 이미지는 `latest`를 사용합니다. 재현성이 필요하면 검증한 버전으로 고정합니다.

## 참고 자료

- [AdGuard Home Docker 이미지](https://hub.docker.com/r/adguard/adguardhome)
- [AdGuard Home 위키 - Docker](https://github.com/AdguardTeam/AdGuardHome/wiki/Docker)
- [Podman Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
