import utype
from utilmeta.core import orm
from .models import Instance
from utype.types import *


class InstanceSchema(orm.Schema[Instance]):
    id: int = orm.Field(no_input='a')
    service_id: str
    node_id: str = orm.Field('service.node_id')

    host: str
    port: Optional[int]
    address: str
    base_url: str
    ops_api: str

    resource_id: str = orm.Field(alias_from=['instance_id'])
    server_id: Optional[str]
    remote_id: Optional[str] = orm.Field(required=False)

    cwd: Optional[str] = orm.Field(required=False)

    weight: float = orm.Field(no_input='a')
    connected: bool = orm.Field(no_input='aw')
    public: bool = orm.Field(required=False)
    # ip.is_global
    version: str
    version_major: int = orm.Field(no_input='aw')
    version_minor: int = orm.Field(no_input='aw')
    version_patch: int = orm.Field(no_input='aw')

    # ------ PROPS
    asynchronous: bool
    production: bool
    language: str
    language_version: str = orm.Field(required=False)
    # python / java / go / javascript / php
    utilmeta_version: str
    # python version
    backend: str
    backend_version: Optional[str] = orm.Field(required=False)
    created_time: datetime
    # deleted_time = models.DateTimeField(default=None, null=True)
    deprecated: bool = orm.Field(required=False)

    resources: Optional[dict] = orm.Field(mode='a', default=None, defer_default=True)
    resources_etag: Optional[str] = orm.Field(default=None, defer_default=True)
    data: dict = orm.Field(required=False)

    avg_load: float = orm.Field(no_input='a')
    avg_time: float = orm.Field(no_input='a')
    avg_rps: float = orm.Field(no_input='a')


class InstanceRegistrySchema(InstanceSchema):
    __options__ = utype.Options(mode='a')

    def __validate__(self):
        if self.version:
            versions = self.version.split('-')[0].split('.')
            try:
                self.version_major = int(versions[0])
            except (TypeError, IndexError, ValueError):
                pass
            try:
                self.version_minor = int(versions[1])
            except (TypeError, IndexError, ValueError):
                pass
            try:
                self.version_patch = int(versions[2])
            except (TypeError, IndexError, ValueError):
                pass
