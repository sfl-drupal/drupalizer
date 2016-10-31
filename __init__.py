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
from fabric.api import task, env, execute

from fabfile import core
from fabfile import docker
from fabfile import deploy
from fabfile import drush
from fabfile import patternlab
from fabfile import tests


@task
def clean():
    """
    Remove all files inside src/drupal.
    """
    core.clean()


@task
def deployment(environment):
    """
    Deploy code and run database updates on a target Drupal environment.
    """
    execute(deploy.provision, environment)
    execute(deploy.push, environment, hosts=env.hosts)
    execute(deploy.migrate, environment, hosts=env.hosts)


@task
def hosts():
    """
    Update the file /etc/hosts and add aliases for each services that made port
    binding with the local machine
    """
    execute(docker.compose_up)
    core.add_hosts_aliases()


@task
def init():
    """
    Complete local installation process, used generally when
    building the docker image for install and configure Drupal.
    """
    execute(docker.compose_up)
    execute(docker.compose_start)
    execute(drush.make, 'install')
    execute(drush.site_install)
    execute(drush.aliases)


@task
def install():
    """
    Run the full installation process.
    """
    execute(drush.make, 'install')
    execute(drush.site_install)


@task
def release():
    """
    Generate all artefacts related to a release process or a deployment
    process.
    """
    execute(drush.archive_dump)
    execute(drush.gen_doc)


@task
def test(pattern=''):
    """
    Setup tests engines and run the complete tests suite.
    :param pattern Specific tests to run that match the pattern.
    """
    if pattern:
        execute(tests.run, tags=pattern)
    else:
        execute(tests.run)


@task
def update():
    """
    Update the full codebase and run the availabe database updates.
    """
    execute(drush.make, 'update')
    execute(drush.updatedb)
