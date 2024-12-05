
def setup_proxy():
    # from django.core.management import execute_from_command_line
    # execute_from_command_line(['manage.py', 'migrate'])
    import os
    os.system('meta migrate')


if __name__ == '__main__':
    setup_proxy()
