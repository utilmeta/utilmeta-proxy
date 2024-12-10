import os.path

from config.env import env
from urllib.parse import urlparse
from utilmeta.utils import localhost, get_server_ips, requires
from utilmeta.core.orm.databases import DatabaseConnections
from config.service import service

PROXY_DOMAIN = urlparse(env.BASE_URL).hostname
SCRIPTS_PATH = os.path.join(os.path.dirname(__file__), 'scripts')
postgresql_script = os.path.join(SCRIPTS_PATH, 'setup-postgresql.sql')
mysql_script = os.path.join(SCRIPTS_PATH, 'setup-mysql.sql')
nginx_script = os.path.join(SCRIPTS_PATH, 'setup-nginx.sql')
server_ips = get_server_ips()

databases = DatabaseConnections.config()


def db_on_this_server():
    if localhost(env.DB_HOST):
        return True
    return env.DB_NAME in server_ips


def execute_shell_script(shell_path, **variables):
    os.system(f'chmod +x {shell_path}')
    var_list = []
    for key, value in variables.items():
        var_list.append(f'{key}="{value}"')
    var_cmd = ' '.join(var_list)
    os.system(f'sudo {var_cmd} {shell_path}')


def connect_postgresql():
    default_database = databases.get('default')
    import psycopg2
    from psycopg2 import OperationalError, Error
    try:
        # Attempt to connect to the PostgreSQL database
        conn = psycopg2.connect(default_database.dsn)
        conn.close()
        return True
    except OperationalError as e:
        if "password" in str(e).lower() or "authentication" in str(e).lower():
            # Invalid credentials are not considered as the database being down
            raise ValueError(f"Invalid credentials provided for database: {default_database.protected_dsn}")
        print(f"Database connection error: {e}")
    except Error as e:
        print(f"Unexpected error: {e}")
    return False


def setup_postgresql():
    requires('psycopg2')
    if connect_postgresql():
        print('postgresql database already setup')
        return
    # the database is down
    if not db_on_this_server():
        return False
    # we can setup database on this server
    execute_shell_script(
        postgresql_script,
        db_names=' '.join([db.name for db in databases.databases.values()]),
        username=env.DB_USER,
        password=env.DB_PASSWORD,
        port=env.DB_PORT
    )
    # todo: host: localhost or private host

    if connect_postgresql():
        print('postgresql database is setup')
        return
    raise ValueError('postgresql database failed to setup')


def connect_mysql():
    default_database = databases.get('default')
    import MySQLdb
    from MySQLdb import OperationalError
    connection = None
    try:
        connection = MySQLdb.connect(
            host=default_database.host,
            port=default_database.port,
            user=default_database.user,
            passwd=default_database.password,
        )
        connection.ping(True)  # Ping the database to confirm the connection
        print("MySQL database is live.")
        return True  # Database is live
    except OperationalError as e:
        # Handle different error cases
        if e.args[0] == 1045:
            raise ValueError(f"Invalid username or password for database: {default_database.protected_dsn}")
        elif e.args[0] == 2003:
            print("MySQL server is down or unreachable.")
        else:
            print(f"Error: {e.args}")
        return False  # Database is down or there is a connection issue
    finally:
        # Close the connection if open
        if connection and connection.open:
            connection.close()


def setup_mysql():
    requires('mysqlclient')
    if connect_mysql():
        print('mysql database already setup')
        return
    # the database is down
    if not db_on_this_server():
        return False
    # we can setup database on this server
    execute_shell_script(
        mysql_script,
        db_names=' '.join([db.name for db in databases.databases.values()]),
        username=env.DB_USER,
        password=env.DB_PASSWORD,
        port=env.DB_PORT
    )
    # todo: host: localhost or private host

    if connect_mysql():
        print('mysql database is setup')
        return
    raise ValueError('mysql database failed to setup')


def setup_database():
    if env.DB_ENGINE == 'postgresql':
        setup_postgresql()
    elif env.DB_ENGINE == 'mysql':
        setup_mysql()
    else:
        raise NotImplementedError(f'Unsupported database engine: {env.DB_ENGINE}')


def setup_gateway():
    conf_path = f'/etc/nginx/conf.d/{PROXY_DOMAIN}.conf'
    if os.path.exists(conf_path):
        print(f'Find nginx config file for {PROXY_DOMAIN} at {conf_path}')
    execute_shell_script(
        nginx_script,
        DOMAIN=PROXY_DOMAIN,
        PORT=service.port
    )


def setup_proxy():
    # from django.core.management import execute_from_command_line
    # execute_from_command_line(['manage.py', 'migrate'])
    service.setup()
    setup_database()
    setup_gateway()


if __name__ == '__main__':
    setup_proxy()
