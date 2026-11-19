#!/bin/sh
# Run against disposable stores only; build the generated development image first.
set -eu
service=${1:?Pass the generated Rust service directory}
service=$(CDPATH= cd -- "$service" && pwd)
example=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
: "${SA_QUERY_S3_IMAGE:?Set a MinIO-compatible test image}"
project="sa-query-rust-live-$$"
work=$(mktemp -d)
cleanup() {
  docker compose -p "$project" -f "$example/compose.stores.yaml" down >/dev/null 2>&1 || true
  rm -rf "$work"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mkdir -p "$service/tests"
cp -R "$example/rust/src/internal/." "$service/src/internal/"
cp "$example/rust/tests/query_live.rs" "$service/tests/"
cat > "$work/network.yaml" <<'YAML'
services:
  storageworker:
    network_mode: bridge
    networks: !reset []
YAML
docker compose -p "$project" -f "$example/compose.stores.yaml" up -d --wait
pg_port=$(docker compose -p "$project" -f "$example/compose.stores.yaml" port postgres 5432 | sed 's/.*://')
s3_port=$(docker compose -p "$project" -f "$example/compose.stores.yaml" port s3 9000 | sed 's/.*://')
cd "$service"
# Use the already-built generated development image and its shared build caches.
docker compose -p "${SA_QUERY_BUILD_PROJECT:-sa-query-rust}" \
  -f docker-compose.generated.yml -f docker-compose.dev.generated.yml \
  -f "$work/network.yaml" run --rm --no-deps -T \
  -e CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-2}" -e SA_QUERY_DISPOSABLE=1 \
  -e DATABASE_CONNECTION_STRING="postgresql://query:disposable-query@host.docker.internal:$pg_port/query" \
  -e OBJECTS_ADDRESS="http://host.docker.internal:$s3_port" \
  -e OBJECTS_REGION=us-east-1 -e OBJECTS_FORCE_PATH_STYLE=true \
  -e AWS_REGION=us-east-1 -e AWS_ACCESS_KEY_ID=queryexample \
  -e AWS_SECRET_ACCESS_KEY=disposable-query-secret -e AWS_EC2_METADATA_DISABLED=true \
  --entrypoint /bin/sh storageworker -c \
  'prepare-local-build /workspace/source /workspace/service && cargo test --test query_live -- --ignored --nocapture'
