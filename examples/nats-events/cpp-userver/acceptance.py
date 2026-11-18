"""Use the same wire assertions as Coro with the stock userver process entrypoint."""
import os
from pathlib import Path
import runpy
os.environ['NATS_ACCEPTANCE_RUNTIME'] = 'userver'
os.environ.setdefault('NATS_ACCEPTANCE_IMAGE', 'cppservicelib-build:latest')
os.environ.setdefault('DEPENDENCY_CONAN_VOLUME', 'cppservicelib_cppservicelib-conan2')
runpy.run_path(str(Path(__file__).resolve().parents[1] / 'cpp-coro/acceptance.py'), run_name='__main__')
