from utilmeta_proxy.config.service import service
from utilmeta_proxy.service.connect import connect_to_supervisor

app = service.application()

connect_to_supervisor()

if __name__ == '__main__':
    service.run()
