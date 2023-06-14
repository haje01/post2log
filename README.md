# post2log

외부 서버에서 HTTP Postback 호출 (POST 메소드) 을 받으면, 그 내용을 로그로 기록한 후 [Fluentd](https://www.fluentd.org/) 등을 통해 외부의 다양한 대상으로 포워딩할 수 있다. post2log 는 쿠버네티스 환경에서 설치 및 이용한다.

post2log 는 자체 서버와 Fluentd 가 같은 노드에 설치되어 함께 동작한다. 내장된 Fluentd 컨테이너 이미지는 다음과 같은 플러그인이 미리 설치되어 있다.
- `fluentd-plugin-kafka`
- `fluentd-plugin-influxdb`

## 설정

`helm/values.yaml` 에서 변수와 그 기본값을 확인할 수 있다. 아래는 그 내용이다.

```yaml
# Helm 차트 기본값
post2log:
  image: docker.io/haje01/post2log:latest
fluentd:
  image: docker.io/haje01/post2log_fluentd:latest
  # Fluentd 용 스토리지 크기
  storage: 4Gi
  # Fluentd 최종 출력 설정
  extraCfg: |
    <match {{ .Values.appName }}>
      # Helm 변수 참조 테스트
      # Release Name : {{ .Release.Name }}
      @type stdout
    </match>"
# 앱 이름. 엔드포인트는 `/postback/앱이름` 형식으로 결정된다
appName: test
# 포스트백 서버 포트. 기본값 80
port: 80  
# 노드포트 이용시 포트. 공백이면 사용 않음
nodePort: ""
# 배포 대상 노드 셀렉터
nodeSelector: {}
logQueryParam: true
# 값이 Null 인 필드 제외 여부
skipNullFields: true
ingress:
  # 자체 Ingress 사용 여부
  enabled: false
  hostname: ""
  annotations: {}
# 포스트백 서버 (FastAPI) 의 워커 수
workers: 1
# 포스트백 서버의 레플리카(파드) 수
replicas: 1
# 로그 저장 스토리지 크기
storage: 4Gi
# 로그 파일 로테이션 기준 바이트수
rotBytes: "10485760"
# 로그 파일 로테이션 백업 수
rotBackups: 5
uvicorn:
  # Uvicorn 로그 레벨
  logLevel: debug
```

## 배포 

배포를 위해선는 용도에 맞게 위 변수 파일을 수정하여 저장하여 그것을 이용한다. 

참고로 `configs/` 폴더 아래에 테스트용 변수 파일 `local.yaml` 이 있는데, 이것을 이용해 아래와 같이 Helm 으로 설치할 수 있다.

```bash
helm install -f configs/local.yaml p2l helm/
```

> Helm 으로 설치시는 기본 레지스트리인 `docker.io` 를 이용한다.

`skaffold.yaml` 의 `local` 프로파일에는 `configs/local.yaml` 을 이용하도록 지정되어 있기에 다음과 같이 Skaffold 프로파일을 지정해 설치할 수도 있다.

```
skaffold run -p local
```

> Skaffold 로 설치시는 로컬 레지스트리가 있는 경우 그것을 이용한다.

### 로컬 테스트

로컬 클러스터인 경우 먼저 포트포워딩을 해주고,

```bash
kubectl port-forward svc/post2log 8080:80
```

`curl` 을 통해 POST 호출을 수행한 뒤,

```bash
curl -X POST "localhost:8080/postback?p1=v1&p2=v2"
```

> 이때 엔드포인트가 맞지 않으면 `{"detail":"Not Found"}` 가 출력되고, 성공하면 `{"status":"success"}` 가 출력된다.

`stdout` 출력의 경우 `kubectl logs` 명령으로 Fluentd 파드의 로그를 보면 결과를 확인할 수 있다. 예를들어 아래와 같은 식으로 남는다.

```
2023-04-28 09:57:43.291989606 +0000 post2log: {"p1":"v1","p2":"v2","_path":"/postback","_timestamp":1682675862705,"_dateTimeGMT":"2023-04-28T09:57:42Z","_nodeName":"minikube","_workerPodHash":"7bcd9d6cdf-7jmsd","_workerProcId":"1"}
```

언더바 `_` 가 붙은 필드는 쿼리 인자값이 아닌 post2log 에서 생성한 필드로 다음과 같은 것들이 있다:
- `_path` - 호출의 엔드포인드 경로
- `_timestamp` - 호출의 타임스탬프
- `_dateTimeGMT` - 호출의 UTC 기준 일시
- `_workerPodHash` - post2log 서버가 위치한 파드의 해쉬 
- `_workerProcId` - post2log 서버 프로세스 ID


### 인그레스 이용

외부 서버에 `K3s` 같은 쿠버네티스 배포본으로 클러스터를 설치하였다면, 배포판에 맞는 Ingress 의 Annotation 을 설정해 이용할 수 있다. 다음은 `configs/ingress.yaml` 에서 가져온 것으로, K3s 에서 기본 인그레스 컨트롤러인 Traefik 을 이용하는 설정이다.

```yaml
ingress:
  enabled: true
  hostname: k3s.remote
  annotations: 
  - kubernetes.io/ingress.class: traefik
```

### Kafka 로 출력 

다음은 `configs/kafka.yaml` 파일의 내용으로, 수집된 로그를 카프카로 보내는 예이다.

```yaml
appName: test 
ingress:
  enabled: fase
fluentd: 
  extraCfg: |
    <match {{ .Values.appName }}> 
      @type kafka2
      brokers <카프카 IP>:<카프카 Port>
      use_event_time true
      default_topic {{ .Values.appName }}
      
      <format>
        @type json
      </format>

      <buffer>
        @type memory
        flush_mode interval
        flush_interval 10s
      </buffer>

      # 디버깅용
      # @log_level trace
      # get_kafka_client_log true
    </match>"

    <system>
      log_level info
    </system>
```

위와 같이 하면, 엔드포인트 `/postback/test` 호출의 내용을 Kafka 의 `test` 토픽으로 저장하게 된다. 

> Fluentd 카프카 플러그인은 Kafka 에서 메시지를 보낼 파티션 리더의 도메인 명을 얻어와 접속을 시도하기에, post2log 가 설치된 서버에서 도메인 이름으로 각 브로커에 접속할 수 없다면 다음과 같은 방식을 검토해야 한다:
> - Fluentd 장비의 /etc/hosts 에 도메인 등록하기
> - 쿠버네티스 환경의 경우 같은 클러스터내에 배포하기 

## InfluxDB 로 출력 

다음은 `configs/kafka.yaml` 파일의 내용으로, 수집된 로그를 InfluxDB 로 보내는 예이다.

```yaml
appName: test 
ingress:
  enabled: fase
skipNullFields: true
fluentd: 
  extraCfg: |
    <match {{ .Values.appName }}> 
      @type influxdb
      host "myi-influxdb"
      port 8086
      dbname post2log
      user admin
      password admindjemals
      time_precision ns
      use_ssl false
      <buffer>
        @type memory
        chunk_limit_size 1m
        flush_mode interval
        flush_interval 10
      </buffer>
    </match>

    <system>
      log_level trace
    </system>
```

위와 같이 하면, 엔드포인트 `/postback/test` 호출의 내용을 InfluxDB 의 `post2log` 데이터베이스 아래 `test` 메저먼트 (Measurement) 로 저장하게 된다. 

> InfluxDB 에 `post2log` 데이터베이스는 미리 만들어 두어야 한다.

InfluxDB 는 null 값을 직접 지원하지 않기에, 기본적으로 null 값이 있는 레코드는 생략되게 된다. 예제에서는 이를 방지하기 위해서는 `skipNullFields` 을 `true` 로 설정하였다.

## 최적화와 배포

### 적절한 워커 수와 레플리카 지정

기본적으로 HTTP 요청을 FastAPI 를 통해 비동기로 받은 뒤 파일에 저장하는 단순한 일이기에, 클러스터 노드를 추가하거나 `workers` 나 `replicas` 를 늘려주는 것으로 성능이 바로 향상되지 않을 수 있다. Fluentd 설정에 따른 다운스트림 작업의 경중에도 영향을 받을 것으로 생각되기에, 필요한 설정 후 최적화를 위한 다양한 실험이 필요할 것이다.

### 배포

성능을 위해 post2log 의 서버와 Fluentd 는 노드 당 하나씩만 존재해야 한다. 이를 위해 `podAntiAffinity` 가 설정되어 이미 post2log 파드가 있는 노드에는 배포되지 않는 것에 유의하자. 예를 들어 `replicas` 의 값을 3 으로 했다면, 실제 쿠버네티스 클러스터의 워커 노드도 세 대가 필요하다.

### 대상 노드 선택

클러스터에 다양한 노드가 있는 경우, post2log 레플리카를 특정 노드에만 배포하려면 `nodeSelector` 을 이용한다. 예를 들어 다음처럼 특정 노드에 `noderole=ingest` 라벨을 붙여주고, 

```bash
kubectl label nodes svr-01 svr-02 noderole=ingest
```
post2log 설치시 `nodeSelector` 에 같은 값을 지정하면 `ingest` 라벨이 있는 노드에만 배포된다.
