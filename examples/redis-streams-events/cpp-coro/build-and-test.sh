#!/usr/bin/env bash
set -euo pipefail
project=/generated/redisstreamsevents
cmake -S "$project" -B "$project/build" \
 -DCMAKE_TOOLCHAIN_FILE=/workspace/build/Release/generators/conan_toolchain.cmake \
 -DCMAKE_BUILD_TYPE=Release -DSERVICELIB_SOURCE_DIR=/workspace \
 -DCMAKE_PREFIX_PATH=/hiredis -DUSE_CCACHE=OFF
cmake --build "$project/build" -j"${CORO_BUILD_JOBS:-2}"
g++ -std=c++20 "$project/probe.cpp" -I/hiredis/include -L/hiredis/lib \
 -Wl,-rpath,/hiredis/lib -lhiredis -o "$project/build/canonical-probe"
python3 "$project/acceptance.py" "$project"
