from utilmeta.conf import Env
from typing import Literal


class ServiceEnvironment(Env):
    PRODUCTION: bool = False
    DJANGO_SECRET_KEY: str = ''

    # databases ---------
    DB_ENGINE: Literal['postgresql', 'mysql'] = 'postgresql'
    DB_HOST: str = '127.0.0.1'
    DB_USER: str
    DB_PASSWORD: str
    DB_PORT: int = 5432
    DB_SSL: bool = False
    DB_SSL_CAFILE: str = None
    # --------------------------

    BASE_URL: str
    PRIVATE: bool = False       # whether this is an intranet cluster
    VALIDATE_FORWARD_IPS: bool = False
    VALIDATE_REGISTRY_ADDR: bool = True

    SUPERVISOR_BASE_URL: str
    SUPERVISOR_CLUSTER_ID: str
    SUPERVISOR_CLUSTER_KEY: str

    DEFAULT_TIMEOUT: int = 15
    LOAD_TIMEOUT: int = 15
    CORS_MAX_AGE: int = 3600 * 24


# env = ServiceEnvironment(sys_env='UTILMETA_PROXY_')
env = ServiceEnvironment(sys_env='UTILMETA_PROXY_')
