import urllib.parse

from utilmeta import UtilMeta
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from utilmeta_proxy.config.conf import configure
from utilmeta_proxy.config.env import env
from utilmeta_proxy import __version__
port = urllib.parse.urlparse(env.BASE_URL).port or env.BIND_PORT or 8888

service = UtilMeta(
    __name__,
    name='utilmeta-proxy',
    description='A proxy service that connect API services in a internal network to UtilMeta cluster',
    backend='starlette',
    asynchronous=True,
    production=env.PRODUCTION,
    version=__version__,
    host='127.0.0.1',
    port=port,
)
service.mount('service.api.RootAPI', route='/api')
configure(service)
