from utilmeta.core.orm.backends.django.models import AwaitableModel
from django.db import models


class Service(AwaitableModel):
    name = models.CharField(max_length=60, unique=True)
    # legacy_names = models.JSONField(default=dict)
    # -name: deprecated_time
    node_id = models.CharField(max_length=50, default=None, null=True)
    base_url = models.TextField(default=None, null=True)
    ops_api = models.TextField(default=None, null=True)
    # if this service has a public base url
    routes = models.JSONField(default=None, null=True)
    public = models.BooleanField(default=False)
    created_time = models.DateTimeField(auto_now_add=True)
    # deleted_time = models.DateTimeField(default=None, null=True)
    data = models.JSONField(default=dict)

    class Meta:
        db_table = 'utilmeta_service'


class ServiceNameRecord(AwaitableModel):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='name_records')
    name = models.CharField(max_length=60, unique=True)
    # unique among the cluster
    created_time = models.DateTimeField(auto_now_add=True)
    deprecated_time = models.DateTimeField(default=None, null=True)

    class Meta:
        db_table = 'utilmeta_service_name_record'


class Instance(AwaitableModel):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='instances')
    service_id: str

    host = models.GenericIPAddressField()
    port = models.PositiveIntegerField(default=None, null=True)
    address = models.CharField(max_length=255, unique=True)
    base_url = models.TextField()
    # address + base_route
    ops_api = models.TextField()
    # address + base_route + ops_route

    resource_id = models.CharField(max_length=50, unique=True)
    server_id = models.CharField(max_length=50, null=True)
    remote_id = models.CharField(max_length=50, null=True)
    # server_mac = models.CharField(max_length=50, null=True)
    cwd = models.FilePathField(allow_files=False, allow_folders=True, default=None, null=True)

    weight = models.DecimalField(default=1, max_digits=5, decimal_places=2)
    connected = models.BooleanField(default=True)
    public = models.BooleanField(default=False)
    # ip.is_global
    version = models.CharField(max_length=32)
    version_major = models.PositiveIntegerField(default=0)
    version_minor = models.PositiveIntegerField(default=0)
    version_patch = models.PositiveIntegerField(default=0)

    # ------ PROPS
    asynchronous = models.BooleanField(default=False)
    production = models.BooleanField(default=False)
    language = models.CharField(max_length=40)
    language_version: str = models.CharField(max_length=40, default=None, null=True)
    # python / java / go / javascript / php
    utilmeta_version = models.CharField(max_length=40)
    # python version
    backend = models.CharField(max_length=40)
    # runtime framework
    backend_version = models.CharField(max_length=40, default=None, null=True)

    created_time = models.DateTimeField(auto_now_add=True)
    # deleted_time = models.DateTimeField(default=None, null=True)
    deprecated = models.BooleanField(default=False)

    resources = models.JSONField(default=None, null=True)
    resources_etag = models.JSONField(default=None, null=True)
    data = models.JSONField(default=dict)

    # ---- last cycle
    avg_load = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    avg_time = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    avg_rps = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        db_table = 'utilmeta_instance'
