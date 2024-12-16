from utilmeta.core import api, request, cli, response
from utype.types import *
from utilmeta.utils import exceptions, DEFAULT_IDEMPOTENT_METHODS, DEFAULT_RETRY_ON_STATUSES, Headers, is_hop_by_hop
from django.db import models
from utilmeta.ops.config import Operations
from utilmeta.ops.log import request_logger, Logger
from utilmeta_proxy.config.env import env, CLUSTER_KEY
from utilmeta_proxy.domain.service.models import Service, Instance

UTILMETA_HEADER_PREFIX = 'x-utilmeta-'
EXCLUDE_HEADERS = [
    'content-length',
    'x-forwarded-for',
    'x-real-ip',
    'remote_addr',
]


def forward_header(header):
    return (not str(header).lower().startswith(UTILMETA_HEADER_PREFIX)
            and not is_hop_by_hop(header) and header not in EXCLUDE_HEADERS)


# @api.CORS(allow_origin='*')
class ProxyAPI(api.API):
    # 1. reverse-proxy from supervisor (for All apis includes OperationsAPI)
    # 2. request proxy to supervisor
    # 3. cluster proxy for a service to a service

    cluster_id: str = request.HeaderParam('X-UtilMeta-Cluster-Id', alias_from=[
        'x-cluster-id'
    ], default=None)
    node_id: str = request.HeaderParam('X-UtilMeta-Node-Id', alias_from=[
        'x-node-id'
    ], default=None)
    service_name: str = request.HeaderParam('X-UtilMeta-Service-Name', alias_from=[
        'x-service-name'
    ], default=None)
    accept_version: str = request.HeaderParam('X-UtilMeta-Accept-Version', alias_from=[
        'x-accept-version'
    ], default=None)
    operation_idempotent: bool = request.HeaderParam('X-UtilMeta-Operation-Idempotent', alias_from=[
        'x-operation-idempotent'
    ], default=None)
    instance_id: str = request.HeaderParam('X-UtilMeta-Instance-Id', alias_from=[
        'x-instance-id'
    ], default=None)

    proxy_type: Literal[
        'discovery',
        'supervisor',
        'operations',
        'forward'
    ] = request.HeaderParam('X-UtilMeta-Proxy-Type', alias_from=[
        'x-proxy-type'
    ], default=None)
    timeout: int = request.HeaderParam('X-UtilMeta-Request-Timeout', alias_from=[
        'x-request-timeout'
    ], default=env.DEFAULT_TIMEOUT)

    proxy_authorization: str = request.HeaderParam('Proxy-Authorization', alias_from=[
        'x-utilmeta-proxy-token',
        'x-proxy-token',
    ], default=None)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.supervisor = None
        self.service = None
        self.instances = []
        self.base_urls = []
        self.base_url = None
        self.instance = None
        self.retries = 0
        self.token_type, self.token = self.request.authorization
        self.headers = Headers({k: v for k, v in self.request.headers.items() if forward_header(k)})
        if self.operation_idempotent is None:
            self.operation_idempotent = str(self.request.adaptor.request_method).upper() in DEFAULT_IDEMPOTENT_METHODS

        self.logger: Logger = request_logger.getter(self.request)
        self.logger.make_events_only(True)

    async def make_request(self, path: str):
        if not self.base_urls:
            raise exceptions.NotFound
        for i, base_url in enumerate(self.base_urls):
            with cli.Client(
                base_url=base_url,
                default_timeout=self.timeout,
                fail_silently=True
            ) as client:
                resp = await client.async_request(
                    method=self.request.adaptor.request_method,
                    path=path,
                    query=self.request.query,
                    headers=dict(self.headers),
                    data=await self.request.aread(),
                )
                self.base_url = base_url
                if self.instances:
                    try:
                        self.instance = self.instances[i]
                    except IndexError:
                        pass
                if not self.should_retry(resp) or i == len(self.base_urls) - 1:
                    # should not retry of its the last response
                    return resp
                self.retries += 1

    def should_retry(self, resp: response.Response) -> bool:
        if not self.operation_idempotent:
            return False
        if resp.is_aborted:
            return True
        if resp.status in DEFAULT_RETRY_ON_STATUSES:
            return True
        return False

    @api.get('{path}')
    async def handle_get(self, path: str = request.PathParam(regex='(.*)')):
        return await self.make_request(path)

    @api.post('{path}')
    async def handle_post(self, path: str = request.PathParam(regex='(.*)')):
        return await self.make_request(path)

    @api.patch('{path}')
    async def handle_patch(self, path: str = request.PathParam(regex='(.*)')):
        return await self.make_request(path)

    @api.put('{path}')
    async def handle_put(self, path: str = request.PathParam(regex='(.*)')):
        return await self.make_request(path)

    @api.delete('{path}')
    async def handle_delete(self, path: str = request.PathParam(regex='(.*)')):
        return await self.make_request(path)

    @api.options('{path}')
    async def handle_options(self, path: str = request.PathParam(regex='(.*)')):
        return await self.make_request(path)

    @api.head('{path}')
    async def handle_head(self, path: str = request.PathParam(regex='(.*)')):
        return await self.make_request(path)

    async def handle_discovery(self):
        if not self.service_name:
            raise exceptions.NotFound
        if env.PRIVATE:
            if not self.request.ip_address.is_private:
                raise exceptions.NotFound
        instance: Instance = await Instance.objects.filter(
            ip=self.request.ip_address,
        ).afirst()
        if instance:
            if instance.remote_id:
                self.headers['x-utilmeta-source-instance-id'] = instance.remote_id
            self.headers['x-utilmeta-source-service'] = instance.service_id
        else:
            if env.VALIDATE_FORWARD_IPS:
                raise exceptions.NotFound
        await self.handle_service()

    async def handle_service(self):
        self.service = await Service.objects.filter(
            models.Q(name=self.service_name) | models.Q(
                name_records__name=self.service_name
            )
        ).afirst()
        if not self.service:
            raise exceptions.NotFound
        instance_qs = Instance.objects.filter(service=self.service, connected=True)
        if self.instance_id:
            instance_qs = instance_qs.filter(remote_id=self.instance_id)
        else:
            if self.accept_version and self.accept_version != '*':
                # 1.1
                # 1.*
                # 1.2
                # ^1.2.3
                # 1
                # 1
                version = self.accept_version.lstrip('v')
                versions = version.lstrip('~').lstrip('^').split('.')
                if len(versions) < 3:
                    versions += ['*'] * (3 - len(versions))
                major, minor, patch = versions[:3]
                version_q = models.Q()
                if major != '*':
                    version_q = models.Q(
                        version_major=major,
                    )
                if minor != '*':
                    if version.startswith('^'):
                        version_q &= models.Q(
                            version_minor__gte=minor,
                        )
                    else:
                        version_q &= models.Q(
                            version_minor=minor,
                        )
                if patch != '*':
                    if version.startswith('~'):
                        version_q &= models.Q(
                            version_patch__gte=patch,
                        )
                    elif not version.startswith('^'):
                        version_q &= models.Q(version_patch=patch)
                instance_qs = instance_qs.filter(version_q)
        self.instances = self.rank_instances([inst async for inst in instance_qs])
        if self.proxy_type == 'operations':
            self.base_urls = [inst.ops_api for inst in self.instances]
        else:
            self.base_urls = [inst.base_url for inst in self.instances]

    @classmethod
    def rank_instances(cls, instances: List[Instance]) -> List[Instance]:
        import random
        connected = [inst for inst in instances if inst.connected]
        if not connected:
            raise exceptions.ServiceUnavailable
        if len(connected) == 1:
            return connected
        inst_scores = {}
        sort_by_load = sorted(
            connected, key=lambda inst: inst.avg_load, reverse=True)
        sort_by_time = sorted(
            connected, key=lambda inst: inst.avg_time, reverse=True)
        sort_by_rps = sorted(
            connected, key=lambda inst: inst.rps, reverse=True)
        for inst in connected:
            inst_scores[inst] = (sort_by_load.index(inst) + sort_by_time.index(inst) + sort_by_rps.index(inst) + 1) \
                                * inst.weight * random.randrange(8, 12) / 10  # add randomness
        return sorted(connected, key=lambda inst: inst_scores[inst], reverse=True)

    async def handle_forward(self):
        # 1. forward to supervisor
        # 2. forward to other services (not supported here)
        if not self.node_id:
            raise exceptions.NotFound
        if env.PRIVATE:
            if not self.request.ip_address.is_private:
                raise exceptions.NotFound
        if env.SUPERVISOR_CLUSTER_ID:
            self.headers['x-cluster-id'] = env.SUPERVISOR_CLUSTER_ID
        instance: Instance = await Instance.objects.filter(
            ip=self.request.ip_address,
        ).afirst()

        if instance:
            if instance.remote_id:
                self.headers['x-source-instance-id'] = instance.remote_id
        else:
            if env.VALIDATE_FORWARD_IPS:
                raise exceptions.NotFound

        from utilmeta.ops.models import Supervisor
        supervisor: Supervisor = await Supervisor.filter(
            node_id=self.node_id,
        ).afirst()
        if not supervisor:
            raise exceptions.NotFound
        self.headers.setdefault('x-node-id', self.node_id)
        self.headers.setdefault('x-node-key', supervisor.public_key)
        self.supervisor = supervisor
        self.base_urls = []
        config = Operations.config()
        for base_url in [supervisor.base_url] + supervisor.backup_urls:
            try:
                if config:
                    config.check_supervisor(base_url)
            except ValueError:
                continue
            # also check supervisor here
            # --- THIS IS A SECURITY MEASURE
            # in the worst case scenario, attacker got the ops db permission
            # and changed the base url of supervisor (to a hostile address)
            # the request will not be sent since it violate the [trusted_hosts]
            self.base_urls.append(base_url)

    def validate_proxy_authorization(self):
        if not self.proxy_authorization:
            raise exceptions.ProxyAuthenticationRequired
        if ' ' in self.proxy_authorization:
            self.proxy_authorization = self.proxy_authorization.split()[1]

        from utilmeta.ops.key import decode_token
        try:
            token_data = decode_token(self.proxy_authorization, public_key=CLUSTER_KEY)
        except ValueError:
            raise exceptions.BadRequest('Invalid token format', state='token_expired')

        token_node_id = token_data.get('nid')
        if token_node_id != self.node_id:
            raise exceptions.Conflict(f'Invalid node id')
        issuer = token_data.get('iss') or ''
        if not str(env.SUPERVISOR_BASE_URL).startswith(issuer):
            raise exceptions.Conflict(f'Invalid token issuer: {repr(issuer)}')
        audience = token_data.get('aud') or ''
        if env.SUPERVISOR_CLUSTER_ID != audience:
            raise exceptions.Conflict(f'Invalid cluster id: {repr(audience)}')
        expires = token_data.get('exp')
        if not expires:
            raise exceptions.UnprocessableEntity('Invalid token: no expires')
        if self.request.time.timestamp() > expires:
            raise exceptions.BadRequest('Invalid token: expired', state='token_expired')

    async def handle_supervisor(self):
        # this is from outside (or this is a global cluster)
        if not self.cluster_id:
            raise exceptions.NotFound
        elif self.cluster_id != env.SUPERVISOR_CLUSTER_ID:
            raise exceptions.NotFound
        if not self.node_id:
            # node is required for both inside and outside proxy
            raise exceptions.NotFound
        # handle proxy from utilmeta supervisor
        # 1. request OperationsAPI
        # 2. request other apis (test endpoint)
        self.validate_proxy_authorization()
        from utilmeta.ops.models import Supervisor
        self.supervisor: Supervisor = await Supervisor.filter(
            node_id=self.node_id,
        ).afirst()
        if not self.supervisor:
            raise exceptions.NotFound
        self.service_name = self.supervisor.service
        await self.handle_service()

    async def handle_operations(self):
        # handle OperationsAPI request proxy from admin user (carrying authorization)
        # 1.
        self.node_id = self.node_id or self.request.query.get('node')
        if not self.node_id:
            raise exceptions.NotFound
        if self.token:
            # from client directly
            # take the token to authorize
            from utilmeta.ops.models import Supervisor
            from utilmeta.ops.key import decode_token

            async for supervisor in Supervisor.objects.filter(
                node_id=self.node_id,
                # we don't use service name as identifier
                # that might not be synced
                disabled=False,
                public_key__isnull=False
            ):
                try:
                    token_data = decode_token(self.token, public_key=supervisor.public_key)
                except ValueError:
                    raise exceptions.PermissionDenied
                if not token_data:
                    continue
                self.supervisor = supervisor

        elif self.proxy_authorization:
            # maybe from utilmeta platform, use proxy authorization to auth
            if not self.cluster_id:
                raise exceptions.NotFound
            elif self.cluster_id != env.SUPERVISOR_CLUSTER_ID:
                raise exceptions.NotFound
            self.validate_proxy_authorization()
            from utilmeta.ops.models import Supervisor
            self.supervisor: Supervisor = await Supervisor.filter(
                node_id=self.node_id,
            ).afirst()

            if not self.supervisor:
                # maybe the first time /ops query when supervisor is not created
                # we will pass since the proxy authorization check has passed
                if not self.service_name:
                    raise exceptions.NotFound
                self.supervisor = Supervisor(
                    service=self.service_name,
                    base_url=env.SUPERVISOR_BASE_URL,
                )

        else:
            raise exceptions.ProxyAuthenticationRequired

        if not self.supervisor:
            raise exceptions.NotFound
        self.service_name = self.supervisor.service
        self.headers['x-utilmeta-node-id'] = self.headers['x-node-id'] = self.node_id
        self.headers['x-forwarded-for'] = str(self.request.ip_address)
        # set remote IP
        await self.handle_service()
        # do not proxy this request unless in has validated token
        # we don't implement detailed authentication here

    @api.before('*')
    async def handle_proxy(self):
        if not self.proxy_type:
            raise exceptions.NotFound
        if self.proxy_type == 'discovery':
            return await self.handle_discovery()
        elif self.proxy_type == 'supervisor':
            return await self.handle_operations()
        elif self.proxy_type == 'operations':
            return await self.handle_operations()
        elif self.proxy_type == 'forward':
            return await self.handle_forward()

    @api.after('*')
    def process_response(self, resp: response.Response):
        server_timing = resp.headers.get('server-timing')
        proxy_timing = f'proxy;dur={resp.duration_ms}'
        if server_timing:
            server_timing = f'{proxy_timing},{server_timing}'
        else:
            server_timing = proxy_timing
        resp.set_header('server-timing', server_timing)
        if self.base_url:
            resp.set_header('X-UtilMeta-Proxy-Destination-Base-URL', self.base_url)
            if self.retries:
                resp.set_header('X-UtilMeta-Proxy-Retries', self.retries)
            if self.instance and self.instance.remote_id:
                resp.set_header('X-UtilMeta-Proxy-Destination-Instance-Id', self.instance.remote_id)
            # marked this response as a normally returned response (instead of a threw error)
