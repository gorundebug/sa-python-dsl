#!/bin/sh
set -eu
language=${1:?Choose go, python or typescript}
generated_service=${2:?Pass the generated service directory after overlay}
case "$language" in go|python|typescript) ;; *) echo "Unsupported runtime: $language" >&2; exit 2 ;; esac
dsl_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
workspace_root=$(CDPATH= cd -- "$dsl_root/.." && pwd)
: "${SA_QUERY_S3_IMAGE:?Set an already cached MinIO-compatible image}"
pg_image=${SA_QUERY_PG_IMAGE:-postgres:17-alpine}
docker image inspect "$pg_image" >/dev/null
docker image inspect "$SA_QUERY_S3_IMAGE" >/dev/null
suffix="$$"
pg="sa-query-pg-$suffix"
s3="sa-query-s3-$suffix"
cleanup() { docker rm -f "$pg" "$s3" >/dev/null 2>&1 || true; }
trap cleanup EXIT INT TERM
docker run -d --rm --name "$pg" --memory 256m --cpus 1 --tmpfs /var/lib/postgresql/data -p 127.0.0.1::5432 -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=query_example "$pg_image" >/dev/null
docker run -d --rm --name "$s3" --memory 512m --cpus 1 --tmpfs /data -p 127.0.0.1::9000 -e MINIO_ROOT_USER=queryexample -e MINIO_ROOT_PASSWORD=queryexampletest "$SA_QUERY_S3_IMAGE" server /data >/dev/null
export SA_QUERY_PG_PORT="$(docker port "$pg" 5432/tcp | sed 's/.*://')"
export SA_QUERY_S3_PORT="$(docker port "$s3" 9000/tcp | sed 's/.*://')"
i=0
until docker exec "$pg" pg_isready -U postgres >/dev/null 2>&1 && curl -fsS "http://127.0.0.1:$SA_QUERY_S3_PORT/minio/health/ready" >/dev/null 2>&1; do
 i=$((i+1)); [ "$i" -lt 30 ] || exit 1
 sleep 1
done
export SA_QUERY_DISPOSABLE=1 AWS_ACCESS_KEY_ID=queryexample AWS_SECRET_ACCESS_KEY=queryexampletest AWS_EC2_METADATA_DISABLED=true
case "$language" in
 go)
  mkdir -p "$generated_service/internal/app"
  cp "$dsl_root/examples/storage-query/go/internal/app/query_live_test.go" "$generated_service/internal/app/"
  GOMAXPROCS=2 GOWORK=off GOPROXY=off GOSUMDB=off "${SA_QUERY_GO:-go}" test -C "$generated_service" ./internal/app -run '^TestLiveGeneratedQueryGraph$' -count=1 -timeout=25s
  ;;
 python)
  export PYTHONPATH="$generated_service/src:$workspace_root/pyservicelib/src"
  "$workspace_root/pyservicelib/.venv/bin/python" "$dsl_root/examples/storage-query/python/test_live_graph.py"
  ;;
 typescript)
  mkdir -p "$generated_service/test"
  cp "$dsl_root/examples/storage-query/typescript/test/query-live.test.mjs" "$generated_service/test/"
  "${SA_QUERY_NODE:-node}" --test "$generated_service/test/query-live.test.mjs"
  ;;
esac
