# post2log

HTTP Postback 호출 (POST 메소드) 을 받아 그 내용을 로그로 기록한 후 [Fluentd](https://www.fluentd.org/) 등을 통해 [외부의 다양한 대상](https://www.fluentd.org/plugins/all#input-output) 으로 포워딩한다.


다음과 같은 환경변수를 이용해 설정할 수 있다:
- `P2L_PORT` - 포스트백 서버 포트. 기본값 80
- `P2L_ENDPOINT` - Postback 대상 엔드포인트. 기본값 `/postback`
- `P2L_LOG_QUERYPARAM` - HTTP 쿼리 매개변수 로깅 여부. 기본값 `true`
- `P2L_NODEPORT` - 노드포트 이용시 포트. 공백이면 사용 않음. 기본값 ""
- `P2L_INGRESS_ANNOT` - Ingress 를 사용하는 경우 Annotations. 공백이면 사용 않음. 기본값 ""
- `P2L_WORKERS` - 포스트백 서버의 워커 수. 기본값 1
- `P2L_REPLICAS` - 포스트백 서버의 레플리카(파드) 수. 기본값 1
- `P2L_STORAGE` - 로그 저장 스토리지 크기. 기본값 `4Gi`
- `P2L_ROTBYTES` - 로그 파일 로테이션 기준 바이트수. 기본값 10485760 (= 10Mi)
- `P2L_ROTBACKUPS` - 로그 파일 로테이션 백업 수. 기본값 5
- `P2L_UVICORN_LOGLEVEL` - Uvicorn 로그 레벨. 기본값 `debug`
- `P2L_FLUENTD_STORAGE` - Fluentd 용 스토리지 크기. 기본값 `4Gi`
- `P2L_FLUENTD_OUTCONF` - Fluentd 최종 출력 설정. 기본값은 아래와 같은 `stdout` 출력이다.
  ```
  <match post2log>
    @type stdout
  </match>
  ```

## 로컬 클러스터

로컬에서 테스트 할때는 다음처럼 환경변수를 설정하면서 `skaffold dev` 명령으로 실행할 수 있다.

```bash
P2L_STORAGE=1Gi skaffold dev --default-repo=<컨테이너 레포지토리>
```

컨테이너 레포지토리는 로컬에서 빌드한 이미지를 Push / Pull 하기 위해 필요하다. 예를 들어 `docker.io/haje01` 과 같은 형식으로 기술하면 된다.

> 처음에는 `No push access to specified image repository` 에러가 발생할 수 있다. 이때는  `docker login` 을 수행하자.

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
2023-04-28 09:57:43.291989606 +0000 post2log: {"p1":"v1","p2":"v2","_path":"/postback","_postTimestamp":1682675862705,"_postDatetimeGMT":"2023-04-28T09:57:42Z","_nodeName":"minikube","_workerPodHash":"7bcd9d6cdf-7jmsd","_workerProcId":"1"}
```

언더바 `_` 가 붙은 필드는 쿼리 인자값이 아닌 post2log 에서 생성한 필드로 다음과 같은 것들이 있다:
- `_endpoint` - 호출의 엔드포인드
- `_postTimestamp` - POST 타임스탬프
- `_postDateTimeGMT` - UTC 기준 일시
- `_workerPodHash` - 서버가 위치한 파드의 해쉬 
- `_workerProcId` - 서버 프로세스 ID

라이브시에는 다음처럼 `skaffold.env` 파일에 원하는 설정을 기술한 뒤,

```bash
P2L_ENDPOINT=/postback/airbridge
P2L_WORKERS=4
P2L_STORAGE=8Gi
P2_FLUETND_OUTCONF="
# 최종 결과를 Kafka 로 보내는 경우
<match post2log>
  @type kafka_buffered
  brokers my-kafka:9092
  default_topic post2log
  flush_interval 10s
  <buffer>
    flusth_interval 10s
  </buffer> 
</match>    
"
```

## 외부 설치형 클러스터

외부 서버에 K8S `minikube`, `K3s` 같은 배포본으로 클러스터를 설치하였다면, 다음처럼 NodePort 서비스를 사용하거나,

```bash
P2L_NODEPORT=30080 skaffold run --default-repo=<컨테이너 레포지토리>
```

쿠버네티스 배포판에 맞는 Ingress 의 Annotation 을 설정해 Ingress 를 이용할 수도 있다. 다음은 K3s 에서 기본 인그레스 컨트롤러인 Traefik 을 이용하는 예이다.

```bash
P2L_INGRESS_ANNOT="kubernetes.io/ingress.class: traefik" skaffold run --default-repo=<컨테이너 레포지토리>
```

## 성능 최적화

기본적으로 HTTP 요청을 FastAPI 를 통해 비동기로 받은 뒤 파일에 저장하는 단순한 일이기에, 클러스터 노드를 추가하거나 `P2L_WORKERS` 나 `P2L_REPLIS` 를 늘려주는 것으로 성능이 바로 향상되지 않을 수 있다. Fluentd 설정에 따른 다운스트림 작업의 경중에도 영향을 받을 것으로 생각되기에, 필요한 설정 후 최적화를 위한 다양한 실험이 필요할 것이다.

