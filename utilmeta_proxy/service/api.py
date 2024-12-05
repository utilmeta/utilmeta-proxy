from utilmeta.core import api, response
from service.proxy.api import ProxyAPI
# from service.request.api import RequestAPI
from domain.service.api import RegistryAPI
from utilmeta.ops import __spec_version__
from config.env import env


class ErrorResponse(response.Response):
    message_key = 'error'


@api.CORS(
    allow_origin='*',
    allow_headers=['x-utilmeta-proxy-type', 'x-utilmeta-cluster-id', 'authorization'],
    cors_max_age=env.CORS_MAX_AGE,
    expose_headers=['server-timing'],
    exclude_statuses=[]
)
class RootAPI(api.API):
    proxy: ProxyAPI
    registry: RegistryAPI

    @api.get('/')
    def ping(self):
        return {
            'utilmeta': __spec_version__,
            'type': 'proxy',
            'registry_url': '/registry',
            'proxy_url': '/proxy',
        }

    @api.handle('*')
    def handle_errors(self, error) -> ErrorResponse:
        return ErrorResponse(error=error)
