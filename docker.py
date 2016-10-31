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
from fabric.colors import red
from fabric.decorators import task

from fabfile.core import *


@task
def connect(service=env.services['php']):
    """
    Connect to a docker container using "docker -it exec <name> bash".
    """
    with lcd(env.workspace):
        # TODO: Find a proper way to match the docker container name.
        regex = re.compile('[^a-zA-Z]')
        project = regex.sub('', env.project_name)
        if docker_isrunning('{}_{}_1'.format(project, service)):
            dk_run(service, user='root', cmd='sh')
        else:
            print(red('Service {} is not running, it should be running to be '
                      'able to connect.'.format(service)))


@task
def compose_down():
    """
    Run docker-compose down
    """
    with lcd(env.workspace):
        local('docker-compose down --remove-orphans')


@task
def compose_ps():
    """
    Run docker-compose ps
    """
    with lcd(env.workspace):
        local('docker-compose ps')


@task
def compose_restart():
    """
    Run docker-compose restart
    """
    with lcd(env.workspace):
        local('docker-compose restart')


@task
def compose_start():
    """
    Run docker-compose start
    """
    with lcd(env.workspace):
        local('docker-compose start')


@task
def compose_stop():
    """
    Run docker-compose stop
    """
    with lcd(env.workspace):
        local('docker-compose stop')


@task
def compose_up():
    """
    Run docker-compose up -d
    """
    with lcd(env.workspace):
        local('docker-compose up -d')


def docker_ps(running_only=False):
    """
    Run docker ps to return the container names.
    :param running_only:
    :return: container names
    """
    args = '' if running_only else '-a'
    result = local('docker ps %s' % args, capture=True)
    lines = result.stdout.splitlines()
    # container name is supposed to be the last column
    assert lines[0].strip().endswith('NAMES')
    return [line.strip().split(' ')[-1] for line in lines[1:]]


def docker_isrunning(containername):
    """
    # Check if the containername is running.
    :param containername:
    :return: bool
    """
    running = docker_ps(running_only=True)
    print(running, containername)
    if containername in running:
        return True
    return False
