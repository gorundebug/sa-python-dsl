#!/usr/bin/env bash
set -euo pipefail
generated=${1:?generated maintenance service directory required}
sdk=${2:?local servicelib directory required}
output=${3:?new acceptance output directory required}
fixtures=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mkdir -p "$output"
output=$(CDPATH= cd -- "$output" && pwd)
test ! -e "$output/service"
cp -R "$generated" "$output/service"
cp "$fixtures/startpendingsweepsource.go.txt" "$output/service/internal/functions/startpendingsweepsource.go"
cp "$fixtures/resolvependingoutcomes.go.txt" "$output/service/internal/functions/resolvependingoutcomes.go"
cp "$fixtures/interval_graph_test.go.txt" "$output/service/internal/app/interval_graph_test.go"
version=$(go env GOVERSION)
cat > "$output/go.work" <<EOF
go ${version#go}
use (
    "$sdk"
    "$output/service"
)
EOF
cd "$output/service"
GOWORK="$output/go.work" GOMAXPROCS=1 go test -race -p=1 -count=1 -timeout=20s -v ./internal/app -run '^TestGeneratedIntervalGraphReturnsResults$'
