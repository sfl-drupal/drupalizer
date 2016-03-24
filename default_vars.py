from os import path

from fabric.api import env


# Project settings

env.project_name = ''
env.workspace = path.join(path.dirname(__file__), path.pardir)
env.interactive_mode = True
env.locale = False


# Site

env.site_root = '{}/src/drupal'.format(env.workspace)
env.site_name = ''
env.site_environment = 'local'
env.site_profile = ''
env.site_profile_repo = ''
env.site_profile_makefile = ''
env.site_db_user = 'dev'
env.site_db_pass = 'dev'
env.site_db_host = 'localhost'
env.site_db_name = ''
env.site_hostname = ''
env.site_admin_user = 'admin'
env.site_admin_pass = 'admin'
env.site_subdir = 'default'


# Docker

env.docker_workspace = '/opt/sfl'
env.docker_site_root = '{}/src/drupal'.format(env.docker_workspace)
env.bind_port = 8001
env.apache_user = 'www-data'
env.container_ip = '172.0.0.0'


# Hook commands

env.hook_post_install = ['drush fra -y', 'drush cc all']
env.hook_post_update = ['drush fra -y', 'drush cc all']
