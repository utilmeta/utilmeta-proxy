from utilmeta.bin.base import BaseCommand, command
import sys
import os
from utilmeta.core.cli import Client
from utilmeta.bin.constant import RED
from config.env import env


class ProxyCommand(BaseCommand):
    PACKAGE_NAME = 'utilmeta-proxy'

    def __init__(self, *args):
        from config.service import service
        service.setup()
        super().__init__(*args, cwd=service.project_dir)
        self.service = service

    @command
    def check(self):
        self.intro()
        with Client(base_url=env.BASE_URL) as client:
            resp = client.get('/')
            if resp.success:
                data = resp.data
                if isinstance(data, dict) and data.get('utilmeta'):
                    print(f'utilmeta-proxy is live at: {env.BASE_URL}')
                    return True
        print(RED % f'utilmeta-proxy is not live: {env.BASE_URL}, please setup and start the proxy service')
        return False

    @command
    def setup(self):
        # check if service is connected
        if self.check():
            print('utilmeta-proxy is already live, quit setup')
            exit(0)
        # if already setup, skip
        from .setup import setup_proxy
        setup_proxy()
        # -------------
        os.system(f'{sys.executable} -m utilmeta migrate')
        self.restart()

    @command
    def restart(self):
        os.system(f'{sys.executable} -m utilmeta restart')

    @command
    def upgrade(self):
        # pip install -U utilmeta-proxy
        print(f'Current utilmeta-proxy version: {self.service.version_str}')
        from .. import __version__
        current_version = __version__
        os.system(f'{sys.executable} -m pip install -U {self.PACKAGE_NAME}')
        from importlib.metadata import version
        new_version = version(self.PACKAGE_NAME)
        if new_version == current_version:
            print('no upgrade detected, quit...')
            exit(0)
        print(f'New utilmeta-proxy version: {new_version}, restarting service')
        os.system(f'{sys.executable} -m utilmeta migrate')
        self.restart()

    @command('-v')
    def version(self):
        print(self.service.version_str)

    @command('')
    def intro(self):
        print(f'UtilMeta Proxy Service v{self.service.version_str}')


def main():
    ProxyCommand(*sys.argv)()


if __name__ == '__main__':
    main()
