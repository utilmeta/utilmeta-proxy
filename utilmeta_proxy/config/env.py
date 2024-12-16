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

    LOG_PATH: str = None

    BASE_URL: str
    BIND_PORT: int = None
    PRIVATE: bool = False       # whether this is an intranet cluster
    VALIDATE_FORWARD_IPS: bool = False

    SUPERVISOR_BASE_URL: str
    SUPERVISOR_CLUSTER_ID: str
    SUPERVISOR_CLUSTER_KEY: str

    DEFAULT_TIMEOUT: int = 15
    LOAD_TIMEOUT: int = 15
    CORS_MAX_AGE: int = 3600 * 24


# env = ServiceEnvironment(sys_env='UTILMETA_PROXY_')
env = ServiceEnvironment(sys_env='UTILMETA_PROXY_')

import warnings
from utilmeta.utils import get_ip
from ipaddress import ip_address
import base64

try:
    PUBLIC_BASE_URL = ip_address(get_ip(env.BASE_URL)).is_global
except Exception as e:
    warnings.warn(f'proxy url IP load failed: {e}')
    PUBLIC_BASE_URL = False

CLUSTER_KEY = env.SUPERVISOR_CLUSTER_KEY

if not CLUSTER_KEY.startswith('{') or not CLUSTER_KEY.endswith('}'):
    # BASE64
    CLUSTER_KEY = base64.decodebytes(CLUSTER_KEY.encode()).decode()

__all__ = ['env', 'CLUSTER_KEY', 'PUBLIC_BASE_URL']
