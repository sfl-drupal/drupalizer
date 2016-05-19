from os import path

from fabric.api import env


# Project settings

env.project_name = ''
env.workspace = path.join(path.dirname(__file__), path.pardir)
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


# PatternLab

# Specify the PatternLab dir is you want the style guide to be generated
env.patternlab_dir = ''


# Database dump
# To enable it, replace the boolean value with the absolute path of a gzipped SQL dump file.

env.db_dump = False

# Docker

env.docker_workspace = '/opt/sfl'
env.docker_site_root = '{}/src/drupal'.format(env.docker_workspace)
env.bind_port = 8001
env.apache_user = 'www-data'

# Docker auto-added container IP
env.container_ip = '172.17.0.0'


# Hook commands

env.hook_post_install = ['drush fra -y', 'drush cc all']
env.hook_post_update = ['drush fra -y', 'drush cc all']


# Target environments definition

env.aliases = {}
