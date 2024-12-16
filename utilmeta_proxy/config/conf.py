from utilmeta import UtilMeta
from utilmeta_proxy.config.env import env
import httpx


def configure(service: UtilMeta):
    from utilmeta.core.server.backends.django import DjangoSettings
    from utilmeta.core.orm import DatabaseConnections, Database
    from utilmeta.conf import Time, Preference
    from utilmeta.ops.config import Operations

    service.use(Preference(
        client_default_request_backend=httpx,
        api_max_retry_loops=10,
        client_max_retry_loops=100
    ))
    service.use(Operations(
        route='ops',
        base_url=env.BASE_URL,
        max_backlog=50,
        worker_cycle=20,
        database='ops',
        secure_only=env.PRODUCTION,
        trusted_hosts=[] if env.PRODUCTION else ['127.0.0.1']
    ))
    service.use(Time(
        time_zone='UTC',
        use_tz=True,
        datetime_format="%Y-%m-%dT%H:%M:%SZ"
    ))

    ssl_ctx = None
    if env.DB_SSL:
        import ssl
        ssl_ctx = ssl.create_default_context(cafile=env.DB_SSL_CAFILE)
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

    service.use(DjangoSettings(
        apps=['utilmeta_proxy.domain.service'],
        secret_key=env.DJANGO_SECRET_KEY,
    ))
    service.use(DatabaseConnections({
        'default': Database(
            name='utilmeta_proxy',
            engine=env.DB_ENGINE,
            host=env.DB_HOST,
            user=env.DB_USER,
            password=env.DB_PASSWORD,
            port=env.DB_PORT,
            ssl=ssl_ctx
        ),
        'ops': Database(
            name='utilmeta_proxy_ops',
            engine=env.DB_ENGINE,
            host=env.DB_HOST,
            user=env.DB_USER,
            password=env.DB_PASSWORD,
            port=env.DB_PORT,
            ssl=ssl_ctx
        )
    }))
    service.setup()
