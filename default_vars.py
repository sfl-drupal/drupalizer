# coding: utf-8
#
# Copyright (C) 2016 Savoir-faire Linux Inc. (<www.savoirfairelinux.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import os
import ruamel.yaml as yaml
from fabric.api import env


# Get info of the current user id
env.local_userid = os.getuid()
env.apache_userid = 82  # The Apache user of the php service.

# Project settings
env.project_name = 'drupal'
env.workspace = os.path.join(os.path.dirname(__file__), os.path.pardir)
env.locale = False


# Get info of the current docker-compose services.
# Services see docker-compose.yml
with open('{}/docker-compose.yml'.format(env.workspace), 'r') as stream:
    try:
        config = yaml.load(stream, Loader=yaml.Loader)
        env.services = {}
        for service in config['services']:
            env.services[service] = service
    except yaml.YAMLError as e:
        print(e)


# Site
env.drupal_version = 7
env.site_root = 'src/drupal'
env.site_drush_aliases = '{}/sites/all/drush'.format(env.site_root)
env.site_name = 'Drupal'
env.site_environment = 'local'
env.site_profile = 'standard'
env.site_profile_repo = ''
env.site_profile_makefile = 'build-standard-8.x.make.yml'
env.site_profile_branch = ''
env.site_db_user = 'dev'
env.site_db_pass = 'dev'
env.site_db_host = env.services['db_server']
env.site_db_name = 'drupal'
env.site_admin_user = 'admin'
env.site_admin_pass = 'admin'
env.site_subdir = 'default'
env.site_languages = ''


# Test engines
# Specify the test engine that should be used to run the tests
# Available options : behat, phpunit
env.test_engines = ['fabfile.tests.behat']


# PatternLab
# Specify the PatternLab dir is you want the style guide to be generated
env.patternlab_dir = ''


# Database dump
# To enable it, replace the boolean value with the name of the database dump
# placed inside the build/ directory
# SQL dump file.
# Example env.db_dump = sfl_boilerplate.sql
env.db_dump = False


# Docker
env.code_workspace = '/var/www/html'
env.code_site_root = '{}/src/drupal'.format(env.code_workspace)


# Hook commands
# Example Drupal 7:
# env.hook_post_install = ['drush fra -y', 'drush cc all']
# env.hook_post_update = ['drush fra -y', 'drush cc all']
# Example Drupal 8:
# env.hook_post_install = ['drush cache-rebuild']
# env.hook_post_update = ['drush cache-rebuild']
env.hook_post_install = []
env.hook_post_update = []


# Target environments definition
env.aliases = {}
