from utilmeta.bin.base import BaseCommand, command
import sys
import os


class ProxyCommand(BaseCommand):
    def __init__(self, *args):
        from config.service import service
        service.setup()
        super().__init__(*args, cwd=service.project_dir)
        self.service = service

    @command
    def setup(self):
        pass

    @command('-v')
    def version(self):
        print(self.service.version_str)


def main():
    ProxyCommand(*sys.argv)()


if __name__ == '__main__':
    main()
