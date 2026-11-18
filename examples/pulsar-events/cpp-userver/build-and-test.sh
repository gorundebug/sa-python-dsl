#!/usr/bin/env bash
set -euo pipefail
project=/generated/pulsarevents
cmake -S "$project" -B "$project/build" \
 -DCMAKE_TOOLCHAIN_FILE=/workspace/build-redis-probe/conan/conan_toolchain.cmake \
 -DCMAKE_BUILD_TYPE=Debug -DSERVICELIB_SOURCE_DIR=/workspace \
 -DPulsarNative_ROOT=/pulsar -DUSE_CCACHE=OFF
cmake --build "$project/build" -j"${USERVER_BUILD_JOBS:-2}"
g++ -std=c++20 "$project/probe.cpp" -I/pulsar/include -L/pulsar/lib \
 -Wl,-rpath,/pulsar/lib -lpulsar -lcrypto -o "$project/build/canonical-probe"
python3 "$project/acceptance.py" "$project"
