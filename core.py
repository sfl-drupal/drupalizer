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
import re
import glob


from fabric.api import lcd, local, abort
from fabric.colors import green
from fabric.contrib.console import confirm

# Import default variables
from .default_vars import *

# Import local variables' overrides, if they exist
if os.path.exists(os.path.join(os.path.dirname(__file__), 'local_vars.py')):
    from .local_vars import *


# Other env variables
env.builddir = os.path.join(env.workspace, 'build')
env.makefile = os.path.join(env.builddir, env.site_profile,
                            env.site_profile_makefile)


def add_hosts_aliases():
    """
    Helper function to update the file /etc/hosts and add alias for the
    services that made port binding with the local machine
    """
    result = local('docker-compose ps', capture=True)
    lines = result.stdout.splitlines()
    regex = re.compile('[^a-zA-Z]')
    project = regex.sub('', env.project_name)

    def get_container_ip(name):
        return local('docker inspect -f "{{{{range '
                     '.NetworkSettings.Networks}}}}'
                     '{{{{.IPAddress}}}}{{{{end}}}}" {0}'.format(name),
                     capture=True)

    for line in lines[1:]:
        container_name = line.strip().split(' ')[0]
        port_bind = '->'
        container_ports = line.strip().split(' ')[-1]
        if project in container_name and port_bind in container_ports:
            ip = get_container_ip(container_name)
            base_hostname = container_name[:-2]
            port = container_ports.split(port_bind)[1][:-4]
            remove_from_hosts('local.{0}.sfl'.format(base_hostname))
            add_to_hosts(ip, 'local.{0}.sfl'.format(base_hostname), port)


def add_to_hosts(ip, hostname, port):
    """
    Helper function to add the ip and hostname to /etc/hosts
    :param ip: the ip address of the container
    :param hostname: the hostname to add in the file /etc/hosts
    """
    if confirm(green('Do you want to add the line "{0}   {1}" in /etc/hosts?\n'
                     'If you say yes you will be able to visit the service '
                     'using a more friendly url "http://{1}:{2}".'
                     ''.format(ip, hostname, port))):
        # Add if not find the comment "# Docker auto-added host" in the file
        # /etc/hosts
        local('grep "# Docker auto-added host" /etc/hosts > /dev/null || '
              'sudo sed -i "$ a # Docker auto-added host" /etc/hosts')
        # Add the ip address and hostname after the comment "# Docker
        # auto-added host"
        local('sudo sed -i "/# Docker auto-added host/a {}     {}" /etc/hosts'
              ''.format(ip, hostname))


def dk_run(service, cmd, user=82, capture=False):
    """
    Helper function to run a command inside a docker container
    :param service: service of the container
    :param cmd: command to run
    :param user: user to run the command
    :param capture: capture the output
    :return: return the output of the command.
    """
    if service in (env.services['php'], env.services['web_server']):
        cm = 'sh -c "cd {} && {}"'.format(env.site_root, cmd)
    else:
        cm = cmd
    with lcd(env.workspace):
        opt = '' if env.get('always_use_pty', True) else '-T'
        return local("docker-compose exec {} --user={} {} {}"
                     "".format(opt, user, service, cm), capture)


def get_archive_from_dir(directory, pattern):
    """
    Find file in a directory using a pattern.
    :param directory The directory used to untar the artifact.
    """
    files = glob.glob1(directory, pattern)
    if len(files) == 0:
        abort('No file found in {}'.format(directory))
    if len(files) > 1:
        abort('More than one tarball has been found in {}. Can not decide '
              'which one to deploy.'.format(directory))
    return files[0]


def hook_execute(cmds=env.hook_post_install, service=env.services['php']):
    """
    Execute a list of drush commands after the installation or update process
    :param service Default 'role' where to run the task
    :param cmds Drush commands to run, default to POST_INSTALL, it could be
    POST_UPDATE too.
    """
    for cmd in cmds:
        dk_run(service, cmd=cmd)


def is_custom_profile(profile_name):
    """
    Helper function to check if the profile is a core profile
    :param profile_name:
    :return:
    """
    return profile_name not in ('minimal', 'standard', 'testing',
                                'config_installer')


def remove_from_hosts(hostname):
    """
    Helper function to remove the ip and the hostname to /etc/hosts
    :param hostname:
    """
    print(green('Enter your password to remove the {} from your '
                '/etc/hosts file'.format(hostname)))
    local('sudo sed -i "/{}/d" /etc/hosts'.format(hostname))


def update_profile():
    """
    Update or clone the installation profile specified in the configuration.
    The build file included will be used to build the application.
    """
    if os.path.exists('{}/{}'.format(env.builddir, env.site_profile)):
        with lcd(os.path.join(env.builddir, env.site_profile)):
            local('git checkout . && git pull')
            print(green('{} installation profile updated in '
                        '{}/{}'.format(env.site_profile, env.builddir,
                                       env.site_profile)))
    else:
        with lcd(env.builddir):
            local('git clone --branch={} {} {}'.format(env.site_profile_branch,
                                                       env.site_profile_repo,
                                                       env.site_profile))
            print(green('{} installation profile cloned in {}/{}'
                        ''.format(env.site_profile, env.builddir,
                                  env.site_profile)))


def fix_files_owner_and_permissions():
    """
    Securing file permissions and ownership
    """
    service = env.services['php']
    dk_run(service, user='root',
           cmd='chown -R {}:{} ../../*'.format(env.local_userid,
                                                  env.apache_userid))
    dk_run(service, user='root',
           cmd="find . -type d -exec chmod u=rwx,g=rx,o= '{}' \;")
    dk_run(service, user='root',
           cmd="find . -type f -exec chmod u=rw,g=r,o= '{}' \;")
    dk_run(service, user='root',
           cmd="cd sites && find . -type d -name files -exec chown -R {}:{} "
               "'{}' \;".format(env.apache_userid, env.local_userid, '{}'))
    dk_run(service, user='root',
           cmd="cd sites && find . -type d -name files -exec chmod ug=rwx,"
               "o=rx "
               "'{}' \;")
    dk_run(service, user='root',
           cmd="cd sites && find . -path '*/files/*' -type d -exec "
               "chmod ug=rwx,o=rx '{}' \; && find . -path '*/files/*' -type f "
               "-exec chmod ug=rw,o=r '{}' \;")


def clean():
    dk_run(env.services['php'], user='root', cmd='rm -rf ../drupal')
