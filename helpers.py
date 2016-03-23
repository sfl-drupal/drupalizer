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

from __future__ import unicode_literals
from getpass import getuser
from fabric.api import lcd, cd, task, roles, env, local, run, runs_once, execute
from fabric.colors import red, green
from fabric.contrib.console import confirm
from fabric.contrib.files import exists

# Import socket to find the localhost IP address
import socket

# Import datetime
from datetime import datetime

# Import default variables
from default_vars import *

# Import local variables' overrides, if they exist
if path.exists(path.join(path.dirname(__file__), 'local_vars.py')):
    from local_vars import *


#####################################################################
# Function to manage differents users, hosts, roles, and variables  #
#####################################################################

# Get info of the current user and host
user_name = getuser()
host_name = local("hostname", capture=True)

# Set the env dict with the roles and the hosts
env.roledefs['local'] = ["{}@{}".format(user_name, host_name)]
env.roledefs['docker'] = ["root@{}".format(env.site_hostname)]

env.builddir = path.join(env.workspace, 'build')
env.makefile = '{}/{}/{}'.format(env.builddir, env.site_profile, env.site_profile_makefile)
env.site_drush_aliases = path.join(env.site_root, 'sites/all/drush')

def fab_run(role="local", cmd="", capture=False):
    """
    Helper function to run the task locally or remotely
    :param role: the role to use for define the host
    :param cmd: the command to execute
    :param capture: if it should return or not the output of the command
    :return: the function to execute the command locally or remotely
    """
    if role == "local":
        return local(cmd, capture)
    else:
        return run(cmd)


def fab_cd(role, directory):
    """
    Helper function to manage the context locally or remotely
    :param role: the role to use for define the host
    :param directory: the directory of context
    :return: the function to manage the context locally or remotely
    """
    if role == "local":
        return lcd(directory)
    else:
        return cd(directory)


def fab_exists(role, directory):
    """
    Herlper function to check if a directory exist locally or remotely
    :param role: the role to use for define the host.
    :param directory: the directory to check
    :return: the function for check the existence of the directory locally or remotely
    """
    if role == "local":
        return path.exists(directory)
    else:
        return exists(directory)


def fab_add_to_hosts(ip, site_hostname):
    """
    Helper function to add the ip and hostname to /etc/hosts
    :param ip:
    :param site_hostname:
    :return:
    """
    if confirm(green('Do you want add to the /etc/hosts the line "{}    {}"? '
                     'If you say yes you will be able to visit the site using a more frienldy url '
                     '"http://{}".'.format(ip, site_hostname, site_hostname))):
        # Add if not find the comment "# Docker auto-added host" to the file /etc/hosts
        local('grep "# Docker auto-added host" /etc/hosts > /dev/null || '
              'sudo sed -i "$ a # Docker auto-added host" /etc/hosts')

        # Add the ip address and hostname after the comment "# Docker auto-added host"
        local('sudo sed -i "/# Docker auto-added host/a {}     {}" /etc/hosts'.format(ip, site_hostname))


def fab_remove_from_hosts(site_hostname):
    """
    Helper function to remove the ip  and the hostname to /etc/hosts
    :param site_hostname:
    :return:
    """
    print(green('Enter your password to remove the {} from your /etc/hosts file'.format(site_hostname)))
    local('sudo sed -i "/{}/d" /etc/hosts'.format(site_hostname))


def fab_update_hosts(ip, site_hostname):
    """
    Helper function to update the file /etc/hosts
    :param ip:
    :param site_hostname:
    :return:
    """
    fab_remove_from_hosts(site_hostname)
    fab_add_to_hosts(ip, site_hostname)


def hook_execute(hook, role='docker'):
    """
    Execute a list of drush commands after the installation or update process
    :param role Default 'role' where to run the task
    :param cmds Drush commands to run, default to POST_INSTALL, it could be POST_UPDATE too.
    """

    cmds = env.hook_post_install

    for cmd in cmds:
        with fab_cd(role, env.docker_site_root):
            fab_run(role, cmd)


def _copy_public_ssh_keys(role='local'):
    
    """
    Copy your public SSH keys to use it in the docker container to connect to it using ssh protocol.
    :param role Default 'role' where to run the task
    """

    with fab_cd(role, env.workspace):
        fab_run(role, 'cp ~/.ssh/id_rsa.pub conf/')
        print green('Public SSH key copied successful to {}/conf directory'.format(env.workspace))


def _update_profile(role='local'):
    """
    Update or clone the installation profile specified in the configuration file.
    The build file included will be used to build the application.
    """
    if fab_exists(role, '{}/{}'.format(env.builddir, env.site_profile)):
        with fab_cd(role, path.join(env.builddir, env.site_profile)):
            fab_run(role, 'git checkout . && git pull')
            print green('{} installation profile updated in {}/{}'.format(env.site_profile, env.builddir, env.site_profile))
    else:
        with fab_cd(role, env.builddir):
            fab_run(role, 'git clone {} {}'.format(env.site_profile_repo, env.site_profile))
            print green('{} installation profile cloned in {}/{}'.format(env.site_profile, env.builddir, env.site_profile))


@roles('docker')
def _init_db(role='docker'):

    """
    Create a database and a user that can access it.
    """

    container_ip = fab_run('local', 'docker inspect -f "{{{{.NetworkSettings.IPAddress}}}}" '
                                                 '{}_container'.format(env.project_name), capture=True)
    docker_iface_ip = [(s.connect((container_ip, 80)), s.getsockname()[0], s.close())
                                   for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]

    fab_run(role, 'mysql -uroot -e "CREATE DATABASE IF NOT EXISTS {}; GRANT ALL PRIVILEGES ON {}.* TO '
                  '\'{}\'@\'localhost\' IDENTIFIED BY \'{}\'; GRANT ALL PRIVILEGES ON {}.* TO \'{}\'@\'{}\' '
                  'IDENTIFIED BY \'{}\'; FLUSH PRIVILEGES;"'.format(env.site_db_name, env.site_db_name, env.site_db_user, env.site_db_pass,
                                                                    env.site_db_name, env.site_db_user, docker_iface_ip, env.site_db_user))



