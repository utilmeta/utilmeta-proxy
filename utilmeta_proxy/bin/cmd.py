from utilmeta.bin.base import BaseCommand, command, Arg
import sys
import os
from utilmeta.core.cli import Client
from utilmeta.bin.constant import RED
from utilmeta.utils import write_to

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from utilmeta_proxy.config.env import env


class ProxyCommand(BaseCommand):
    PACKAGE_NAME = 'utilmeta-proxy'
    script_name = 'utilmeta-proxy'

    def __init__(self, exe: str = None, *args, cwd: str = None):
        self.exe = exe
        from utilmeta_proxy.config.service import service
        super().__init__(*args, cwd=cwd or service.project_dir)
        self.service = service

    @property
    def ini_path(self):
        return os.path.join(BASE_DIR, 'meta.ini')

    @command
    def check(self, print_down: bool = True):
        self.intro()
        with Client(
            base_url=env.BASE_URL,
            fail_silently=True,
            allow_redirects=True
        ) as client:
            resp = client.get('/')
            if resp.success:
                data = resp.data
                if isinstance(data, dict) and data.get('utilmeta'):
                    print(f'utilmeta-proxy is live at: {env.BASE_URL}')
                    return True
        if print_down:
            print(RED % f'utilmeta-proxy is not live at: {env.BASE_URL}, please setup and start the proxy service')
        return False

    @command
    def setup(self, force: bool = False):
        # check if service is connected
        print(f'setup for utilmeta-proxy: {self.service.version_str} at {env.BASE_URL}')
        if not force and self.check(print_down=False):
            print('utilmeta-proxy is already live, quit setup')
            print('(if your env vars has changed, use [utilmeta-proxy reconfigure] to re-initialize the service)')
            exit(0)
        # if already setup, skip
        from .setup import setup_proxy
        setup_proxy()
        # -------------
        os.system(f'{sys.executable} -m utilmeta migrate --ini={self.ini_path}')
        self.restart()

    @command
    def reconfigure(self):
        return self.setup(force=True)

    @command
    def restart(self):
        log_path = env.LOG_PATH or '/var/log/utilmeta-proxy/proxy.log'
        if not os.path.exists(log_path):
            os.makedirs(os.path.dirname(log_path))
        os.system(f'{sys.executable} -m utilmeta restart --ini={self.ini_path} --log={log_path}')

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
        os.system(f'{sys.executable} -m utilmeta migrate --ini={self.ini_path}')
        self.restart()

    @command
    def export_env(self,
                   file: str = Arg('--file', default='utilmeta-proxy.env'),
                   bash: bool = Arg('-b', default=False),
                   echo: bool = Arg('-e', default=False),
                   ):
        env_vars = dict(
            UTILMETA_PROXY_BASE_URL=env.BASE_URL,
            UTILMETA_OPERATIONS_DB_ENGINE=env.DB_ENGINE,
            UTILMETA_OPERATIONS_DB_HOST=env.DB_HOST,
            UTILMETA_OPERATIONS_DB_PORT=env.DB_PORT,
            UTILMETA_OPERATIONS_DB_USER=env.DB_USER,
            UTILMETA_OPERATIONS_DB_PASSWORD=env.DB_PASSWORD,
        )
        contents = []
        for key, val in env_vars.items():
            if bash:
                contents.append(f'export {key}={val}')
            else:
                contents.append(f'{key}={val}')
        if not os.path.isabs(file):
            file = os.path.join(self.cwd, file)
        content = '\n'.join(contents) + '\n'
        if echo:
            print(content)
        write_to(file, content)
        print('export utilmeta-proxy cluster environment variables to {}'.format(file))

    # @command
    # def delete_proxy(self):
    #     print('You are going to delete utilmeta-proxy service node in UtilMeta platform')
    #     from utilmeta.ops.connect import delete_supervisor

    @command('-v', 'version')
    def version(self):
        print(self.service.version_str)

    @command('')
    def intro(self):
        print(f'UtilMeta Proxy Service v{self.service.version_str}')

    def fallback(self):
        arg_cmd = ' '.join(self.argv)
        os.system(f'{sys.executable} -m utilmeta {arg_cmd} --ini={self.ini_path}')


def main():
    from .setup import prepare_service
    prepare_service()
    ProxyCommand(*sys.argv)()


if __name__ == '__main__':
    main()
