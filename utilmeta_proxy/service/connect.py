from utilmeta.ops.client import SupervisorClient
from config.env import env
from utilmeta.ops.config import Operations
from utilmeta.ops.connect import connect_supervisor
from utilmeta.utils import omit
from utilmeta.bin.constant import RED
from utilmeta.ops.client import OperationsClient, ServiceInfoResponse
import time


@omit
def connect_task(config: Operations, timeout: int = env.LOAD_TIMEOUT):
    t = time.time()
    live = False
    while True:
        if time.time() - t > timeout:
            break
        info = OperationsClient(base_url=config.ops_api, fail_silently=True).get_info()
        live = isinstance(info, ServiceInfoResponse) and info.validate()
        if not live:
            time.sleep(0.5)
        else:
            break
    if not live:
        print(RED % 'UtilMeta proxy: service not live or OperationsAPI not mounted, '
                    f'please check your OperationsAPI: {config.ops_api} is accessible before connect')
        return

    from utilmeta.ops.log import _supervisor
    if _supervisor and _supervisor.node_id:
        print('supervisor already connected')
        return

    url = connect_supervisor(
        key=env.SUPERVISOR_CLUSTER_KEY,
        cluster_id=env.SUPERVISOR_CLUSTER_ID,
        base_url=env.SUPERVISOR_BASE_URL,
    )
    # add current instances?
    # probably not. because when proxy is set up, no instance is added yet
    print(f'supervisor connected at: {url}')


def connect_to_supervisor():
    if not env.SUPERVISOR_BASE_URL or not env.SUPERVISOR_CLUSTER_ID or not env.SUPERVISOR_CLUSTER_KEY:
        print('supervisor env vars not set, cannot connect to supervisor')
        return
    config = Operations.config()
    if not config:
        return
    if not config.is_local:
        print(f'UtilMeta cluster proxy cannot be local, please specify the BASE_URL env var')
        return
    connect_task(config)
