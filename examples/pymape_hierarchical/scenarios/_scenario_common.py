from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import TypeVar


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class DummyRedis:
    def pubsub(self):
        return DummyPubSub()

    async def close(self):
        pass

    async def publish(self, *args, **kwargs):
        return None


class DummyPubSub:
    async def psubscribe(self, **kwargs):
        pass

    async def subscribe(self, *args, **kwargs):
        pass

    async def unsubscribe(self, *args, **kwargs):
        pass

    async def run(self):
        pass


class DummyFastAPI:
    def __init__(self, *args, **kwargs):
        self.routes = []

    def get(self, *args, **kwargs):
        return self._decorator

    def post(self, *args, **kwargs):
        return self._decorator

    def put(self, *args, **kwargs):
        return self._decorator

    def delete(self, *args, **kwargs):
        return self._decorator

    def include_router(self, *args, **kwargs):
        return None

    def add_api_route(self, *args, **kwargs):
        return None

    def mount(self, *args, **kwargs):
        return None

    def on_event(self, *args, **kwargs):
        return self._decorator

    def _decorator(self, func):
        return func


class DummyHTTPException(Exception):
    def __init__(self, status_code=500, detail=None, *args, **kwargs):
        super().__init__(detail or status_code)
        self.status_code = status_code
        self.detail = detail


def dummy_depends(*args, **kwargs):
    return None


class DummyUvicornConfig:
    def __init__(self, *args, **kwargs):
        pass


class DummyUvicornServer:
    def __init__(self, *args, **kwargs):
        pass

    async def serve(self):
        return None

    def run(self):
        return None


class DummyBaseModel:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def dict(self, *args, **kwargs):
        return dict(self.__dict__)

    def model_dump(self, *args, **kwargs):
        return dict(self.__dict__)


class DummyInfluxDBClient:
    def __init__(self, *args, **kwargs):
        pass

    def write_api(self, *args, **kwargs):
        return DummyWriteAPI()

    def close(self):
        pass


class DummyWriteAPI:
    def write(self, *args, **kwargs):
        pass


class DummyPoint:
    def __init__(self, *args, **kwargs):
        pass

    def tag(self, *args, **kwargs):
        return self

    def field(self, *args, **kwargs):
        return self

    def time(self, *args, **kwargs):
        return self


class DummyWriteOptions:
    def __init__(self, *args, **kwargs):
        pass


class NullObserver:
    def __init__(self, *args, **kwargs):
        pass

    def on_next(self, value):
        pass

    def on_error(self, error):
        pass

    def on_completed(self):
        pass

    def dispose(self):
        pass


class DummyAioHttpResponse:
    def __init__(self, *args, **kwargs):
        self.status = 200
        self.reason = "OK"

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self, *args, **kwargs):
        return {}

    async def text(self, *args, **kwargs):
        return ""

    async def read(self, *args, **kwargs):
        return b""


class DummyClientSession:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def post(self, *args, **kwargs):
        return DummyAioHttpResponse()

    def get(self, *args, **kwargs):
        return DummyAioHttpResponse()

    def put(self, *args, **kwargs):
        return DummyAioHttpResponse()

    def delete(self, *args, **kwargs):
        return DummyAioHttpResponse()

    async def close(self):
        pass


class DummyClientError(Exception):
    pass


class DummyClientResponseError(DummyClientError):
    pass


class DummyClientConnectorError(DummyClientError):
    pass


class DummyPurseCollection:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.storage = {}

    def __class_getitem__(cls, item):
        return cls

    async def get(self, key=None, *args, **kwargs):
        if key is None:
            return None
        return self.storage.get(key)

    async def set(self, key, value=None, *args, **kwargs):
        self.storage[key] = value
        return True

    async def delete(self, key=None, *args, **kwargs):
        if key is not None:
            self.storage.pop(key, None)
        return True

    async def add(self, value, *args, **kwargs):
        self.storage[value] = value
        return True

    async def remove(self, value, *args, **kwargs):
        self.storage.pop(value, None)
        return True

    async def append(self, value, *args, **kwargs):
        self.storage.setdefault("_list", []).append(value)
        return True

    def __getattr__(self, name):
        async def dummy_async(*args, **kwargs):
            return None

        return dummy_async


class DummyRedlock:
    def __init__(self, *args, **kwargs):
        pass

    async def acquire(self, *args, **kwargs):
        return True

    async def release(self, *args, **kwargs):
        return True


def install_dependency_shims() -> None:
    """
    Install minimal shims for optional runtime dependencies.

    This keeps bounded desktop tracing independent from remote infrastructure
    such as Redis, REST, Uvicorn, Pydantic, InfluxDB and aiohttp.
    """

    if "aioredis" not in sys.modules:
        aioredis = types.ModuleType("aioredis")
        aioredis.Redis = DummyRedis

        def from_url(*args, **kwargs):
            return DummyRedis()

        aioredis.from_url = from_url
        sys.modules["aioredis"] = aioredis

    if "fastapi" not in sys.modules:
        fastapi = types.ModuleType("fastapi")
        fastapi.FastAPI = DummyFastAPI
        fastapi.HTTPException = DummyHTTPException
        fastapi.Depends = dummy_depends
        sys.modules["fastapi"] = fastapi

    if "uvicorn" not in sys.modules:
        uvicorn = types.ModuleType("uvicorn")
        uvicorn.Config = DummyUvicornConfig
        uvicorn.Server = DummyUvicornServer
        sys.modules["uvicorn"] = uvicorn

    if "pydantic" not in sys.modules:
        pydantic = types.ModuleType("pydantic")
        pydantic.BaseModel = DummyBaseModel
        sys.modules["pydantic"] = pydantic

    if "aiohttp" not in sys.modules:
        aiohttp = types.ModuleType("aiohttp")
        aiohttp.__path__ = []  # make it behave like a package
        aiohttp.ClientSession = DummyClientSession
        aiohttp.ClientError = DummyClientError
        aiohttp.ClientResponseError = DummyClientResponseError
        aiohttp.ClientConnectorError = DummyClientConnectorError

        client_exceptions = types.ModuleType("aiohttp.client_exceptions")
        client_exceptions.ClientError = DummyClientError
        client_exceptions.ClientResponseError = DummyClientResponseError
        client_exceptions.ClientConnectorError = DummyClientConnectorError

        aiohttp.client_exceptions = client_exceptions

        sys.modules["aiohttp"] = aiohttp
        sys.modules["aiohttp.client_exceptions"] = client_exceptions

    if "influxdb_client" not in sys.modules:
        influxdb_client = types.ModuleType("influxdb_client")
        influxdb_client.InfluxDBClient = DummyInfluxDBClient
        influxdb_client.Point = DummyPoint
        influxdb_client.WriteOptions = DummyWriteOptions
        sys.modules["influxdb_client"] = influxdb_client

        client_module = types.ModuleType("influxdb_client.client")
        write_api_module = types.ModuleType("influxdb_client.client.write_api")
        write_api_module.SYNCHRONOUS = object()
        write_api_module.ASYNCHRONOUS = object()

        sys.modules["influxdb_client.client"] = client_module
        sys.modules["influxdb_client.client.write_api"] = write_api_module

    if "purse" not in sys.modules:
        purse = types.ModuleType("purse")
        purse.__path__ = []

        collections_module = types.ModuleType("purse.collections")
        collections_module.T = TypeVar("T")
        collections_module._obj_from_raw = lambda value, *args, **kwargs: value
        collections_module._list_from_raw = lambda value, *args, **kwargs: value
        collections_module._obj_to_raw = lambda value, *args, **kwargs: value

        collection_names = [
            "RedisKeySpace",
            "RedisHash",
            "RedisSet",
            "RedisList",
            "RedisKey",
            "RedisSortedSet",
            "RedisPriorityQueue",
            "RedisQueue",
            "RedisLifoQueue",
        ]

        for name in collection_names:
            cls = type(name, (DummyPurseCollection,), {})
            setattr(purse, name, cls)
            setattr(collections_module, name, cls)

        purse.Redlock = DummyRedlock
        collections_module.Redlock = DummyRedlock
        purse.collections = collections_module

        sys.modules["purse"] = purse
        sys.modules["purse.collections"] = collections_module


def load_hierarchical_module():
    install_dependency_shims()

    module_path = PROJECT_ROOT / "hierarchical-cruise-control.py"

    spec = importlib.util.spec_from_file_location(
        "hierarchical_cruise_control_runtime",
        module_path,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    # Avoid external InfluxDB writes during tracing.
    module.InfluxObserver = NullObserver

    return module


def import_mape():
    install_dependency_shims()
    import mape

    return mape
