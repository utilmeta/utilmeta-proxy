from utilmeta.core import api, request
from utilmeta.ops.proxy import RegistrySchema
from utilmeta.ops.config import Operations
from utilmeta.utils import exceptions, url_join, fast_digest, json_dumps, adapt_async
from config.env import env
from urllib.parse import urlparse
from .models import Service, ServiceNameRecord, Instance
from .schema import InstanceRegistrySchema, InstanceSchema
from django.db import models
from starlette.concurrency import run_in_threadpool

ops_config = Operations.config()


class RegistryAPI(api.API):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.node_id = None

    # @orm.Atomic('default')
    async def post(self, data: RegistrySchema = request.Body) -> InstanceSchema:
        if env.PRIVATE:
            if not self.request.ip_address.is_private:
                raise exceptions.NotFound
        parsed = urlparse('http://' + data.address)
        host = parsed.hostname
        port = parsed.port or None
        if env.VALIDATE_REGISTRY_ADDR:
            if str(self.request.ip_address) != host:
                raise exceptions.PermissionDenied(f'service register failed, your request ip:'
                                                  f' {self.request.ip_address} is inconsistent '
                                                  f'to instance host: {host}')

        from utilmeta.ops.models import Resource
        instance_res: Resource = await Resource.filter(
            id=data.instance_id,
            type='instance',
            service=data.name,
            ident=data.address,
        ).afirst()
        if not instance_res:
            raise exceptions.BadRequest(f'service register failed: instance(id={data.instance_id}, '
                                        f'address={data.address}) not found in operations database')

        ops_api_parsed = urlparse(data.ops_api)
        if not ops_api_parsed.netloc:
            data.ops_api = url_join('http://' + data.address, ops_api_parsed.path)
        elif ops_api_parsed.netloc != data.address:
            raise exceptions.BadRequest(f'service register failed: OperationsAPI netloc: '
                                        f'{ops_api_parsed.netloc} inconsistent to instance address: {data.address}')

        base_url_parsed = urlparse(data.base_url)
        if not base_url_parsed.netloc:
            data.base_url = url_join('http://' + data.address, base_url_parsed.path)
        elif base_url_parsed.netloc != data.address:
            raise exceptions.BadRequest(f'service register failed: base_url netloc: '
                                        f'{ops_api_parsed.netloc} inconsistent to instance address: {data.address}')

        service: Service = await Service.objects.filter(
            models.Q(name=data.name) | models.Q(
                name_records__name=data.name,
            )
        ).afirst()
        if not service:
            service = await Service.objects.acreate(
                name=data.name,
                node_id=instance_res.node_id,
            )
        await ServiceNameRecord.objects.aget_or_create(
            service=service,
            name=data.name,
        )
        # use data.instance_id to identify and auth

        instance = await Instance.objects.filter(
            address=data.address
        ).afirst()
        inst_registry = InstanceRegistrySchema(
            **data,
            service_id=service.pk,
            remote_id=instance_res.remote_id,
            server_id=instance_res.server_id,
            host=host,
            port=port,
        )
        if data.resources:
            inst_registry.resources_etag = fast_digest(
                json_dumps(data.resources),
                compress=True,
                case_insensitive=False
            )
            inst_registry.resources = data.resources
        else:
            del inst_registry.resources
            # del inst_registry.resources_etag
            # do not participate in save

        if instance:
            if instance.service_id != service.pk:
                raise exceptions.BadRequest(f'service register failed: address: {instance.address} has been '
                                            f'registered by service: [{instance.service_id}]')
            inst_registry.id = instance.pk

        await inst_registry.asave()

        # from utilmeta import service as utilmeta_service
        if not service.node_id:
            # instance not registered
            # self.connect_supervisor(service, data=data)
            await run_in_threadpool(self.connect_supervisor, service, data=data)

            if self.node_id:
                service.node_id = self.node_id
                await service.asave(update_fields=['node_id'])
        elif data.resources:
            # has resources to sync
            # if node has checked etag and sent None, we just ignore
            # sync resources
            await run_in_threadpool(self.sync_supervisor, service, data=inst_registry)

        return await InstanceSchema.ainit(inst_registry.pk)

    @adapt_async(close_conn=ops_config.db_alias)
    def sync_supervisor(self, service: Service, data: InstanceRegistrySchema):
        from utilmeta.ops.models import Supervisor
        from utilmeta.ops.client import SupervisorClient, ResourcesSchema
        from utilmeta.ops.resources import ResourcesManager

        if not service.node_id:
            return
        if not data.resources:
            return
        supervisor: Supervisor = Supervisor.filter(
            service=service.name,
            node_id=service.node_id
        ).first()
        if not supervisor:
            return
        if supervisor.resources_etag and data.resources_etag == supervisor.resources_etag:
            print('resource is identical to supervisor')
            return

        with SupervisorClient(
            base_url=supervisor.base_url,
            node_key=supervisor.public_key,
            node_id=supervisor.node_id,
            cluster_id=env.SUPERVISOR_CLUSTER_ID,
            fail_silently=True
        ) as client:
            resp = client.upload_resources(
                data=ResourcesSchema(data.resources)
            )
            if not resp.success:
                raise ValueError(f'sync to supervisor[{supervisor.node_id}]'
                                 f' failed with error: {resp.message}')

            if supervisor.service != service.name:
                print(f'update supervisor and resources service name to [{service.name}]')
                supervisor.service = service.name
                supervisor.save(update_fields=['service'])
                ResourcesManager.update_supervisor_service(service.name, node_id=supervisor.node_id)

            if resp.status == 304:
                print('[304] resources is identical to the remote supervisor, done')
                return

            if resp.result.resources_etag:
                supervisor.resources_etag = resp.result.resources_etag
                supervisor.save(update_fields=['resources_etag'])

            ResourcesManager.save_resources(
                resp.result.resources,
                supervisor=supervisor
            )

            print(f'sync resources to supervisor[{supervisor.node_id}] successfully')
            if resp.result.url:
                if supervisor.url != resp.result.url:
                    supervisor.url = resp.result.url
                    supervisor.save(update_fields=['url'])
                print(f'you can visit {resp.result.url} to view the updated resources')

    @adapt_async(close_conn=ops_config.db_alias)
    def connect_supervisor(self, service: Service, data: RegistrySchema):
        from utilmeta.ops.client import SupervisorClient
        from utilmeta.ops.connect import save_supervisor, update_service_supervisor
        from utilmeta.ops.models import Supervisor

        supervisor_obj = Supervisor.objects.create(
            service=service.name,
            base_url=env.SUPERVISOR_BASE_URL,
            init_key=env.SUPERVISOR_CLUSTER_KEY,  # for double-check
            ops_api=service.ops_api or data.ops_api
        )

        try:
            with SupervisorClient(
                base_url=env.SUPERVISOR_BASE_URL,
                cluster_key=env.SUPERVISOR_CLUSTER_KEY,
                fail_silently=True,
                cluster_id=env.SUPERVISOR_CLUSTER_ID,
            ) as cli:
                resp = cli.add_node(
                    data=data.get_metadata()
                )
                if not resp.success:
                    raise ValueError(f'connect to supervisor failed with error: {resp.text}')

                if resp.result:
                    # supervisor is returned (cannot access)
                    supervisor_obj = save_supervisor(resp.result)
                    if not supervisor_obj.node_id or supervisor_obj.node_id != resp.result.node_id:
                        raise ValueError(f'supervisor failed to create: inconsistent node id: '
                                         f'{supervisor_obj.node_id}, {resp.result.node_id}')
                else:
                    # supervisor already updated in POST OperationsAPI/
                    supervisor_obj: Supervisor = Supervisor.objects.get(pk=supervisor_obj.pk)

                    # update after
                    if not supervisor_obj.node_id:
                        raise ValueError('supervisor failed to create')

                self.node_id = supervisor_obj.node_id

                update_service_supervisor(
                    service=supervisor_obj.service,
                    node_id=supervisor_obj.node_id
                )
                if not supervisor_obj.local:
                    if not supervisor_obj.public_key:
                        raise ValueError('supervisor failed to create: no public key')

        except Exception as e:
            supervisor_obj.delete()
            self.node_id = None
            raise e
