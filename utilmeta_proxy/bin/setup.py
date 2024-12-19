import os.path

from urllib.parse import urlparse
from utilmeta.utils import localhost, get_server_ips, detect_package_manager, requires
from utilmeta import UtilMeta
from utilmeta.core.orm.databases import DatabaseConnections
from utilmeta_proxy.config.env import env

PROXY_DOMAIN = urlparse(env.BASE_URL).hostname
SCRIPTS_PATH = os.path.join(os.path.dirname(__file__), 'scripts')
postgresql_script = os.path.join(SCRIPTS_PATH, 'setup-postgresql.sh')
mysql_script = os.path.join(SCRIPTS_PATH, 'setup-mysql.sh')
mysql_install_rhel_script = os.path.join(SCRIPTS_PATH, 'install-mysql-rhel.sh')
nginx_script = os.path.join(SCRIPTS_PATH, 'setup-nginx.sh')
server_ips = get_server_ips()


def execute_shell_script(shell_path, **variables):
    os.system(f'chmod +x {shell_path}')
    var_list = []
    for key, value in variables.items():
        var_list.append(f'{key}="{value}"')
    var_cmd = ' '.join(var_list)
    return os.system(f'sudo {var_cmd} {shell_path}')


class ProxySetup:
    def __init__(self, service: UtilMeta):
        self.service = service
        self.databases = self.service.get_config(DatabaseConnections)
        self.default_database = self.databases.get('default')
        self.ops_database = self.databases.get('default')

    @property
    def db_on_this_server(self):
        if localhost(env.DB_HOST):
            return True
        return env.DB_HOST in server_ips

    def connect_postgresql(self):
        requires('psycopg2')
        import psycopg2
        from psycopg2 import OperationalError, Error

        for db in [self.default_database, self.ops_database]:
            try:
                # Attempt to connect to the PostgreSQL database
                conn = psycopg2.connect(
                    host=db.host,
                    port=db.port,
                    user=db.user,
                    password=db.password,
                    database=db.name
                )
                conn.close()
            except OperationalError as e:
                if "password" in str(e).lower() or "authentication" in str(e).lower():
                    # Invalid credentials are not considered as the database being down
                    print(f"Invalid credentials provided for database: {db.protected_dsn}")
                    return False
                print(f"Database connection error: {e}")
                return False
            except Error as e:
                print(f"Unexpected error: {e}")
                return False
        return True

    def setup_postgresql(self):
        if self.connect_postgresql():
            print('postgresql database already setup')
            return
        # the database is down
        if not self.db_on_this_server:
            raise ValueError(f'postgresql database: {env.DB_HOST}:{env.DB_PORT} not connected, and not '
                             f'located in current server, auto setup cannot perform, you need to deploy it manually')
        # we can setup database on this server
        if execute_shell_script(
            postgresql_script,
            db_names=' '.join([db.name for db in self.databases.databases.values()]),
            username=env.DB_USER,
            password=env.DB_PASSWORD,
            host=env.DB_HOST,
            port=env.DB_PORT
        ):
            raise ValueError('Execute postgresql setup failed')

        if self.connect_postgresql():
            print('postgresql database is setup')
            return
        raise ValueError('postgresql database failed to setup')

    def connect_mysql(self):
        import MySQLdb
        from MySQLdb import OperationalError
        for db in [self.default_database, self.ops_database]:
            connection = None
            try:
                connection = MySQLdb.connect(
                    host=db.host,
                    port=db.port,
                    user=db.user,
                    passwd=db.password,
                    database=db.name
                )
                connection.ping(True)  # Ping the database to confirm the connection
            except OperationalError as e:
                # Handle different error cases
                if e.args[0] == 1045:
                    print(f"Invalid username or password for database: {db.protected_dsn}")
                elif e.args[0] == 2003:
                    print("MySQL server is down or unreachable.")
                else:
                    print(f"Error: {e.args}")
                return False  # Database is down or there is a connection issue
            finally:
                # Close the connection if open
                if connection and connection.open:
                    connection.close()
        return True

    def setup_mysql(self):
        if self.connect_mysql():
            print('mysql database already setup')
            return
        # the database is down
        if not self.db_on_this_server:
            raise ValueError(f'mysql database: {env.DB_HOST}:{env.DB_PORT} not connected, and not '
                             f'located in current server, auto setup cannot perform, you need to deploy it manually')
        # we can setup database on this server
        if execute_shell_script(
            mysql_script,
            db_names=' '.join([db.name for db in self.databases.databases.values()]),
            username=env.DB_USER,
            password=env.DB_PASSWORD,
            host=env.DB_HOST,
            port=env.DB_PORT
        ):
            raise ValueError('Execute mysql setup failed')

        if self.connect_mysql():
            print('mysql database is setup')
            return
        raise ValueError('mysql database failed to setup')

    def setup_database(self):
        if env.DB_ENGINE == 'postgresql':
            self.setup_postgresql()
        elif env.DB_ENGINE == 'mysql':
            self.setup_mysql()
        else:
            raise NotImplementedError(f'Unsupported database engine: {env.DB_ENGINE}')

    def setup_gateway(self):
        conf_path = f'/etc/nginx/conf.d/{PROXY_DOMAIN}.conf'
        if os.path.exists(conf_path):
            print(f'Find nginx config file for {PROXY_DOMAIN} at {conf_path}')
        if execute_shell_script(
            nginx_script,
            DOMAIN=PROXY_DOMAIN,
            PORT=self.port
        ):
            raise ValueError('Setup gateway failed')

    @property
    def port(self):
        return self.service.port

    def allow_port(self):
        if self.port:
            print(f'Allow service port: {self.port}')
            if not os.system('command -v ufw > /dev/null 2>&1'):
                os.system(f'sudo ufw allow {self.port}/tcp')
                os.system(f'sudo ufw allow http')
                os.system(f'sudo ufw allow https')
                os.system(f'sudo ufw reload')

    def setup(self):
        self.allow_port()
        self.setup_database()
        self.setup_gateway()


def setup_proxy():
    from utilmeta_proxy.config.service import service
    ProxySetup(service).setup()


def prepare_service():
    if env.DB_ENGINE == 'mysql':
        try:
            import MySQLdb
        except (ModuleNotFoundError, ImportError):
            pkg = detect_package_manager()
            if pkg == 'yum':
                if os.system('sudo yum install mysql-devel -y'):
                    if execute_shell_script(
                        mysql_install_rhel_script,
                    ):
                        raise ValueError('Cannot install mysql automatically, please install it manually')


if __name__ == '__main__':
    setup_proxy()
