# coding: utf-8
#
# Copyright (C) 2014 Savoir-faire Linux Inc. (<www.savoirfairelinux.com>).
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
from fabric.contrib.files import exists
from fabric.contrib.console import confirm

# Import socket to find the localhost IP address
import socket

# Import datetime
from datetime import datetime

# Import default variables
from default_vars import *

# Import local variables' overrides, if they exist
if path.exists(path.join(path.dirname(__file__), 'local_vars.py')):
    from local_vars import *


# Function to manage differents users, hosts, roles, and variables  #
#####################################################################
# Get info of the current user and host
user_name = getuser()
host_name = local("hostname", capture=True)

# Set the env dict with the roles and the hosts
env.roledefs['local'] = ["{}@{}".format(user_name, host_name)]
env.roledefs['docker'] = ["root@{}".format(SITE_HOSTNAME)]

# Flag to use for install the site with or without translations
LOCALE = False

# The CONTAINER_IP will be set at the creation of the container, see @task docker_run_container
CONTAINER_IP = None


def set_env(role):
    """
    Helper function to set the correct values of the global variables in function of the role
    :param role: the role to use for define the host
    :return:
    """
    global INTERACTIVE_MODE
    INTERACTIVE_MODE = False if hasattr(env, 'mode') and env.mode == 'release' else True

    global WORKSPACE
    WORKSPACE = {
        'local': LOCAL_WORKSPACE,
        'docker': DOCKER_WORKSPACE
    }[role]

    global DRUPAL_ROOT
    DRUPAL_ROOT = {
        'local': LOCAL_DRUPAL_ROOT,
        'docker': DOCKER_DRUPAL_ROOT
    }[role]

    global BUILDDIR
    BUILDDIR = path.join(WORKSPACE, 'build')

    global MAKEFILE
    MAKEFILE = '{}/{}/{}'.format(BUILDDIR, PROFILE.keys()[0], PROFILE_MAKE_FILE)

    global DRUSH_ALIASES
    DRUSH_ALIASES = path.join(DRUPAL_ROOT, 'sites/all/drush')

    global DOCKER_IFACE_IP
    DOCKER_IFACE_IP = None
    if CONTAINER_IP:
        DOCKER_IFACE_IP = [(s.connect((CONTAINER_IP, 80)), s.getsockname()[0], s.close())
                           for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]


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


# Helper functions to manage docker images and containers #
###########################################################

def docker_ps(running_only=False):
    args = '' if running_only else '-a'
    result = local('docker ps %s' % args, capture=True)
    lines = result.stdout.splitlines()
    # container name is supposed to be the last column
    assert lines[0].strip().endswith('NAMES')
    return [line.strip().split(' ')[-1] for line in lines[1:]]


def docker_tryrun(imgname, containername=None, opts='', mounts=None, cmd='', restart=True):
    # mounts is a list of (from, to, canwrite) path tuples. ``from`` is relative to the project root.
    # Returns True if the container was effectively ran (false if it was restarted or aborted)
    if not mounts:
        mounts = []
    if containername and containername in docker_ps(running_only=True):
        print green("%s already running" % containername)
        return False
    if containername and containername in docker_ps(running_only=False):
        if restart:
            print green("%s already exists and is stopped. Restarting!" % containername)
            local('docker restart %s' % containername)
            return True
        else:
            print red("There's a dangling container %s! That's not supposed to happen. Aborting" % containername)
            print "Run 'docker rm %s' to remove that container" % containername
            return False
    for from_path, to_path, canwrite in mounts:
        abspath = from_path
        opt = ' -v %s:%s' % (abspath, to_path)
        if not canwrite:
            opt += ':ro'
        opts += opt
    if containername:
        containername_opt = '--name %s' % containername
    else:
        containername_opt = ''
    local('docker run %s %s %s %s' % (opts, containername_opt, imgname, cmd))
    return True


def docker_ensureruns(containername):
    # Makes sure that containername runs. If it doesn't, try restarting it. If the container
    # doesn't exist, spew an error.
    if containername not in docker_ps(running_only=True):
        if containername in docker_ps(running_only=False):
            local('docker restart %s' % containername)
            return True
        else:
            return False
    else:
        return True


def docker_ensure_data_container(containername, volume_paths=None, base_image='busybox'):
    # Make sure that we have our data containers running. Data containers are *never* removed.
    # Their only purpose is to hold volume data.
    # Returns whether a container was created by this call
    if containername not in docker_ps(running_only=False):
        if volume_paths:
            volume_args = ' '.join('-v %s' % volpath for volpath in volume_paths)
        else:
            volume_args = ''
        local('docker create %s --name %s %s' % (volume_args, containername, base_image))
        return True
    return False


def docker_isrunning(containername):
    # Check if the containername is running.
    if containername not in docker_ps(running_only=True):
        return False
    else:
        return True


def docker_images():
    result = local('docker images', capture=True)
    lines = result.stdout.splitlines()
    # image name is supposed to be the first column
    assert lines[0].strip().startswith('REPOSITORY')
    return [line.strip().split(' ')[0] for line in lines]


# Task to manage docker's images and containers generally in the localhost#
###########################################################################

@task(alias='icreate')
@roles('local')
def docker_create_image(role='local'):
    """
    Create docker images
    :param role Default 'role' where to run the task
    """
    set_env(role)
    with fab_cd(role, WORKSPACE):
        if '{}/drupal'.format(PROJECT_NAME) in docker_images():
            print(red('Docker image {}/drupal was found, you has already build this image'.format(PROJECT_NAME)))
        else:
            fab_run(role, 'docker build -t {}/drupal .'.format(PROJECT_NAME))
            print(green('Docker image {}/drupal was build successful'.format(PROJECT_NAME)))


@task(alias='crun')
@roles('local')
def docker_run_container(role='local'):
    """
    Run docker containers
    :param role Default 'role' where to run the task
    """
    set_env(role)
    with fab_cd(role, WORKSPACE):
        if '{}/drupal'.format(PROJECT_NAME) in docker_images():
            if docker_tryrun('{}/drupal'.format(PROJECT_NAME),
                             '{}_container'.format(PROJECT_NAME),
                             '-d -p {}:80'.format(DOCKER_PORT_TO_BIND),
                             mounts=[(WORKSPACE, DOCKER_WORKSPACE, True)]):
                # If container was successful build, get the IP address and show it to the user.
                global CONTAINER_IP
                CONTAINER_IP = fab_run(role, 'docker inspect -f "{{{{.NetworkSettings.IPAddress}}}}" '
                                             '{}_container'.format(PROJECT_NAME), capture=True)
                fab_update_hosts(CONTAINER_IP, SITE_HOSTNAME)
                print(green('Docker container {}_container was build successful. '
                            'To visit the Website open a web browser in http://{} or '
                            'http://localhost:{}.'.format(PROJECT_NAME, SITE_HOSTNAME, DOCKER_PORT_TO_BIND)))

        else:
            print(red('Docker image {}/drupal not found and is a requirement to run the {}_container.'
                      'Please, run first "fab create" in order to build the {}/drupal '
                      'image'.format(PROJECT_NAME, PROJECT_NAME, PROJECT_NAME)))


@task(alias='cstop')
@roles('local')
def docker_stop_container(role='local'):
    """
    Stop docker containers
    :param role Default 'role' where to run the task
    """
    set_env(role)
    with fab_cd(role, WORKSPACE):
        if '{}_container'.format(PROJECT_NAME) in docker_ps():
            fab_remove_from_hosts(SITE_HOSTNAME)
            fab_run(role, 'docker stop {}_container'.format(PROJECT_NAME))
            print(green('Docker container {}_container was successful stopped'.format(PROJECT_NAME)))
        else:
            print(red('Docker container {}_container was not running or paused'.format(PROJECT_NAME)))


@task(alias='cremove')
@roles('local')
def docker_remove_container(role='local'):
    """
    Stop docker containers
    :param role Default 'role' where to run the task
    """
    set_env(role)
    with fab_cd(role, WORKSPACE):
        if '{}_container'.format(PROJECT_NAME) in docker_ps():
            fab_remove_from_hosts(SITE_HOSTNAME)
            fab_run(role, 'docker rm -f {}_container'.format(PROJECT_NAME))
            print(green('Docker container {}_container was successful removed'.format(PROJECT_NAME)))
        else:
            print(red('Docker container {}_container was already removed'.format(PROJECT_NAME)))


@task(alias='iremove')
@roles('local')
def docker_remove_image(role='local'):
    """
    Remove docker container and images
    :param role Default 'role' where to run the task
    """
    set_env(role)
    with fab_cd(role, WORKSPACE):
        if docker_isrunning('{}_container'.format(PROJECT_NAME)):
            print(red('Docker container {}_container is running, '
                      'you should stopped it after remove the image {}/drupal'.format(PROJECT_NAME, PROJECT_NAME)))
        if '{}/drupal'.format(PROJECT_NAME) in docker_images():
            fab_run(role, 'docker rmi -f {}/drupal'.format(PROJECT_NAME))
            # Remove dangling docker images to free space.
            if '<none>' in docker_images():
                fab_run(role, 'docker images --filter="dangling=true" -q | xargs docker rmi -f')
            print(green('Docker image {}/drupal was successful removed'.format(PROJECT_NAME)))
        else:
            print(red('Docker image {}/drupal was not found'.format(PROJECT_NAME)))


@task(alias='connect')
@roles('local')
def docker_connect(role='local'):
    """
    Connect to a docker container using "docker -it exec <name> bash".
    This is a better way to connect to the container than using ssh'
    :param role Default 'role' where to run the task
    """
    set_env(role)
    with fab_cd(role, WORKSPACE):
        if docker_isrunning('{}_container'.format(PROJECT_NAME)):
            fab_run(role, 'docker exec -it {}_container bash'.format(PROJECT_NAME))
        else:
            print(red('Docker container {}_container is not running, it should be running to be able to connect.'))


@task(alias='ssh')
@roles('local')
def docker_ssh(role='local', path_key='~/.ssh/id_rsa'):
    """
    Connect to a docker container through ssh protocol using you private key that should be in '~/.ssh/id_rsa'
    :param role Default 'role' where to run the task
    :param path_key Location of the private ssh key
    """
    set_env(role)
    global CONTAINER_IP
    if CONTAINER_IP:
        fab_run(role, 'ssh -i {} root@{}'.format(path_key, CONTAINER_IP))


@task(alias='dkuh')
@roles('docker')
def docker_update_host():
    """
    Helper function to update the IP and hostname in docker container
    # Fix complains of sendmail about "unable to qualify my own domain name"
    :return:
    """
    # Get the IP of the container, this
    global CONTAINER_IP
    if CONTAINER_IP:
        site_hostname = run("hostname")
        run("sed  '/{}/c\{} {}  localhost.domainlocal' "
            "/etc/hosts > /root/hosts.backup".format(CONTAINER_IP, CONTAINER_IP, site_hostname))
        run("cat /root/hosts.backup > /etc/hosts")


@task(alias='cp_keys')
@roles('local')
def copy_ssh_keys(role='local', ):
    """
    Copy your public SSH keys to use it in the docker container to connect to it using ssh protocol.
    :param role Default 'role' where to run the task
    """
    set_env(role)
    copy = True
    if fab_exists(role, '{}/conf/id_rsa.pub'.format(WORKSPACE)):
        if confirm(red('There is a public SSH key in your conf directory Say [Y] to keep this key, say [n] to '
                       'overwrite the key')):
            copy = False

    with fab_cd(role, WORKSPACE):
        if copy:
            fab_run(role, 'cp ~/.ssh/id_rsa.pub conf/')
            print(green('Public SSH key copied successful'))
        else:
            print(red('Keeping the existing public SSH key'))


# Task to manage Git task in projetcs generally in the localhost#
#################################################################

@task(alias='gpp')
@roles('local')
def git_pull_profile(role='local'):
    """
    Git pull for install profile
    :param role Default 'role' where to run the task
    """
    set_env(role)
    for profile in PROFILE:
        with fab_cd(role, path.join(BUILDDIR, profile)):
            print(green('git pull for project {}'.format(profile)))
            fab_run(role, 'git pull')


@task(alias='gcp')
@roles('local')
def git_clone_profile(role='local'):
    """
    Git clone for install profile
    :param role Default 'role' where to run the task
    """
    set_env(role)
    for profile in PROFILE:
        with fab_cd(role, BUILDDIR):
            if fab_exists(role, path.join(BUILDDIR, profile)):
                print(red('This project {} was already clone'.format(profile)))
                continue
            print(green('git clone for project {}'.format(profile)))
            fab_run(role, 'git clone {} {}'.format(PROFILE[profile], profile))


@task(alias='rel')
@roles('local')
def gen_doc(role='local'):
    """
    Generate README file
    :param role Default 'role' where to run the task
    """
    set_env(role)
    print(green('Generate the README'))
    fab_run(role, 'asciidoctor -b html5 -o {}/README.html {}/README'.format(BUILDDIR, WORKSPACE))


@task(alias='ard')
@roles('docker')
def archive_dump(role='docker'):
    """
    Archive the platform for release or deployment
    :param role Default 'role' where to run the task
    """
    set_env(role)
    with fab_cd(role, DRUPAL_ROOT):
        platform = '{}-{}.tar.gz'.format(PROJECT_NAME, datetime.now().strftime('%Y%m%d_%H%M%S'))
        print(green('Cleaning previous archives'))
        fab_run(role, 'rm -f {}/*.tar.gz'.format(BUILDDIR))
        print(green('Archiving the platform'))
        fab_run(
            role,
            'drush archive-dump --destination={}/{} --tar-options="--exclude=.git"'.format(BUILDDIR, platform)
        )


# Task to manage Drupal site generally in the docker container#
###############################################################


@task(alias='dr')
@roles('docker')
def delete_root(role='docker'):
    """
    Delete existing Drupal installation
    :param role Default 'role' where to run the task
    """
    set_env(role)
    if fab_exists(role, DRUPAL_ROOT):
        if (INTERACTIVE_MODE or confirm(red('A Drupal installation is already present, do you really whish to remove '
                                            'it? (everything will be lost)'))) or not INTERACTIVE_MODE:
            fab_run(role, 'rm -rf {}'.format(DRUPAL_ROOT))
            print green('Drupal installation deleted.')
        else:
            print(red('Drupal installation was not deleted.'))
    else:
        print green('No Drupal installation is present, we can build a new one.')


@task(alias='make')
@roles('local')
def drush_make(role='local', action='install'):
    """
    Prepare the site for installation with makefile
    :param role Default 'role' where to run the task
    :param action Default to 'install' it could be 'update' too.
    """
    set_env(role)
    drush_opts = "--prepare-install " if action != 'update' else ''

    print green('Interactive mode enabled: {}'.format(INTERACTIVE_MODE))

    if (INTERACTIVE_MODE and confirm(red('Say [Y] to {} the site at {} with the French translation, if you say [n] '
                                         'the site will be installed in English only'.format(action, DRUPAL_ROOT)))
        ) or not INTERACTIVE_MODE:
        drush_opts += "--translations=fr "
        global LOCALE
        LOCALE = True

    drush_opts += "--contrib-destination=profiles/{} ".format(PROFILE.keys()[0])
    if INTERACTIVE_MODE:
        drush_opts += " --working-copy --no-gitinfofile"
    if not fab_exists(role, DRUPAL_ROOT):
        fab_run(role, "mkdir {}".format(DRUPAL_ROOT))
    with fab_cd(role, DRUPAL_ROOT):
        fab_run(role, 'drush make {} {} -y'.format(drush_opts, MAKEFILE))
    print green('Drush make finished!')


@task(alias='dc')
@roles('docker')
def drush_commands(role='docker', cmds=POST_INSTALL):
    """
    Execute a list of drush commands after the installation or update process
    :param role Default 'role' where to run the task
    :param cmds Drush commands to run, default to POST_INSTALL, it could be POST_UPDATE too.
    """
    set_env(role)

    if not LOCALE:
        cmds.remove('drush po-import fr --custom-only')

    for cmd in cmds:
        with fab_cd(role, DRUPAL_ROOT):
            fab_run(role, cmd)

    print green('These Drush commands were executed: {}.'.format(', '.join(cmds)))


@task(alias='dcf')
@roles('local')
def drush_config(role='local'):
    """
    Create drush aliases
    :param role Default 'role' where to run the task
    """
    set_env(role)
    if not fab_exists(role, DRUSH_ALIASES):
        fab_run(role, 'mkdir {}'.format(DRUSH_ALIASES))
    with fab_cd(role, DRUSH_ALIASES):
        # Create aliases
        if fab_exists(role, '{}/aliases.drushrc.php'.format(DRUSH_ALIASES)):
            fab_run(role, 'rm aliases.drushrc.php')
        fab_run(role, 'ln -s {}/conf/aliases.drushrc.php .'.format(WORKSPACE))
        # Download other drush commands
        # if not fab_exists(role, '{}/po-import'.format(DRUSH_ALIASES)):
        #     fab_run(role, 'git clone git@gitlab.savoirfairelinux.com:drupal/drupalizer.git')
    print green('Drush configuration done.')


@task(alias='csy')
@roles('docker')
def create_symlinks(role='docker'):
    """
    Create symlinks for the
    :param role Default 'role' where to run the task
    """
    set_env(role)
    fab_run(role, 'rm -rf {}'.format(DRUPAL_ROOT))
    fab_run(role, 'ln -s {}/src/drupal {}'.format(WORKSPACE, DRUPAL_ROOT))
    print green('Symlinks created')


@task(alias='dbs')
@roles('docker')
def data_base_setup(role='docker'):
    """
    Setup database for site install
    :param role Default 'role' where to run the task
    """
    set_env(role)
    fab_run(role, 'mysql -uroot -e "CREATE DATABASE IF NOT EXISTS {}; GRANT ALL PRIVILEGES ON {}.* TO '
                  '\'{}\'@\'localhost\' IDENTIFIED BY \'{}\'; GRANT ALL PRIVILEGES ON {}.* TO \'{}\'@\'{}\' '
                  'IDENTIFIED BY \'{}\'; FLUSH PRIVILEGES;"'.format(DB_NAME, DB_NAME, DB_USER, DB_PASS,
                                                                    DB_NAME, DB_USER, DOCKER_IFACE_IP, DB_PASS))


@task(alias='cs')
@roles('docker')
def copy_settings(role='docker', site_env=SITE_ENVIRONMENT):
    """
    Copy settings for the current environment
    :param role Default 'role' where to run the task
    :param site_env The site environment to setup the settings.
    """
    set_env(role)
    fab_run(role,
            'cp {}/conf/env/settings.{}.php {}/sites/default/settings.{}.php'.format(WORKSPACE, site_env, DRUPAL_ROOT,
                                                                                     site_env))
    print green('settings.{}.php copied in "sites/default".'.format(site_env))


@task(alias='es')
@roles('docker')
def edit_settings(role='docker', site_env=SITE_ENVIRONMENT):
    """
    Include environment settings in settings.php
    :param role Default 'role' where to run the task
    :param site_env The site environment to setup the settings.
    """
    set_env(role)
    settings = '{}/sites/default/settings.php'.format(DRUPAL_ROOT)
    fab_run(role, "echo \" \n/**\n "
                  "* Call environment settings file.\n */\n"
                  "require_once \'settings.{}.php\';\n \" >> {}".format(site_env, settings))
    print green('settings.{}.php has been included in settings.php.'.format(site_env))


@task(alias='ss')
@roles('docker')
def secure_settings(role='docker'):
    """
    Set the correct permissions for settings.php
    :param role Default 'role' where to run the task
    """
    set_env(role)
    fab_run(role, 'chmod 644 {}/sites/default/settings.php'.format(DRUPAL_ROOT))
    print green('settings.php has been secured.')


@task(alias='sp')
@roles('docker')
def set_permission(role='docker'):
    """
    Set the correct permissions for the entire site.
    :param role Default 'role' where to run the task
    """
    set_env(role)
    fab_run(role, 'sudo chown -R {}:{} {}'.format(user_name, APACHE, DRUPAL_ROOT))
    fab_run(role, 'chmod -R 750 {}'.format(DRUPAL_ROOT))
    fab_run(role, 'chmod -R 755 {}/sites/default'.format(DRUPAL_ROOT))
    fab_run(role, 'chmod -R 770 {}/sites/*/files'.format(DRUPAL_ROOT))
    secure_settings(env)


@task(alias='cb')
@roles('docker')
def behat_config(role='docker', rewrite=True):
    """
    Create and configure behat.yml
    :param role Default 'role' where to run the task
    :param rewrite If the behat.yml file should be rewrited or not.
    """
    set_env(role)
    if not fab_exists(role, '{}/tests/behat/behat.yml'.format(WORKSPACE)) or rewrite:
        with fab_cd(role, '{}/tests/behat'.format(WORKSPACE)):
            fab_run(role, 'cp example.behat.yml behat.yml')
            fab_run(role, 'sed -i "s@%DRUPAL_ROOT@{}@g" behat.yml'.format(DRUPAL_ROOT))
            fab_run(role, 'sed -i "s@%URL@http://{}@g" behat.yml'.format(SITE_HOSTNAME))
            fab_run(role, 'echo "127.0.0.1  {}" >> /etc/hosts'.format(SITE_HOSTNAME))
        print green('Behat configured.')
    else:
        print green('behat.yml is already present.')


@task(alias='ib')
@roles('docker')
def install_behat(role='docker'):
    """
    Install behat
    :param role Default 'role' where to run the task
    """
    set_env(role)
    if not fab_exists(role, '/usr/local/bin/behat'):
        with fab_cd(role, '{}/tests/behat'.format(WORKSPACE)):
            fab_run(role, 'curl -s https://getcomposer.org/installer | php')
            fab_run(role, 'php composer.phar install')
            fab_run(role, 'ln -s bin/behat /usr/local/bin/behat')
        print green('Behat has been installed.')
    else:
        print(green('Behat is already installed, not need for a new installation'))


@task(alias='rb')
@roles('docker')
def run_behat(role='docker'):
    """
    Run behat tests
    :param role Default 'role' where to run the task
    """
    set_env(role)
    fab_run(role, 'mkdir -p {}/logs/behat'.format(WORKSPACE))
    # In the container behat is installed globaly, so check before install it inside the tests directory
    if not fab_exists(role, '/usr/local/bin/behat') or not fab_exists(role, '../tests/behat/bin/behat'):
        install_behat()
    # If the configuration file behat.yml doesn't exist, call behat_config before run the test.
    if not fab_exists(role, '{}/tests/behat/behat.yml'.format(WORKSPACE)):
        behat_config()
    with fab_cd(role, '{}/tests/behat'.format(WORKSPACE)):
        fab_run(role, 'behat --format junit --format pretty --tags "~@wip&&~@disabled&&~@test" --colors')
        # To run behat with only one test for example, comment previous line
        # and uncomment next one
        # fab_run(role, 'behat --format pretty --tags "~@wip&&~@disabled&&@yourTest" --colors')


@task(alias='install')
@roles('docker')
def site_install(role='docker'):
    """
    Install site
    :param role Default 'role' where to run the task
    """
    set_env(role)
    with fab_cd(role, DRUPAL_ROOT):
        locale = '--locale="fr"' if LOCALE else ''

        fab_run(role, 'sudo -u {} drush site-install {} {} --db-url=mysql://{}:{}@{}/{} --site-name={} '
                      '--account-name={} --account-pass={} --sites-subdir={} -y'.format(APACHE, SITE_PROFILE, locale,
                                                                                        DB_USER, DB_PASS,
                                                                                        DB_HOST, DB_NAME, SITE_NAME,
                                                                                        SITE_ADMIN_NAME,
                                                                                        SITE_ADMIN_PASS,
                                                                                        SITE_SUBDIR))
    print green('Site installed successfully!')

    print green('Running post-install commands.')
    execute(drush_commands)


@task(alias='su')
@roles('docker')
def site_update(role='docker'):
    """
    Update site
    :param role Default 'role' where to run the task
    """
    set_env(role)
    if confirm(red('Update the site will wipe out contrib and custom modules, '
                   'you should commit your changes or you will lost them. '
                   'Do you want to continue with the SITE UPDATE?')):
        with fab_cd(role, DRUPAL_ROOT):
            site_environment = fab_run(role, 'drush vget environment --format=string')
            execute(git_pull_profile)
            execute(drush_make, action='update')
            copy_settings(role, site_environment)
            fab_run(role, 'drush updb -y')
            # execute(drush_config)
            drush_commands(role, POST_UPDATE)
            execute(behat_config)
        print green('Site updated successfully!')
    else:
        print green('Aborting site updated!')


@task(alias='sr')
def site_reinstall():
    """
    Complete local re-installation process. To use generally inside the running container to reinstall the Drupal site.
    The same that run: $ fab dr gpp dmk si dcf cs es ss dc cb
    """
    execute(delete_root)
    execute(git_pull_profile)
    execute(drush_make)
    execute(site_install)
    execute(drush_config)
    execute(copy_settings)
    execute(edit_settings)
    execute(secure_settings)
    execute(drush_commands)
    execute(behat_config)
    print green('Site reinstalled with success!')


@task(alias='tests')
def run_tests():
    print green('Tests execution tasks is about to start')
    execute(behat_config)
    execute(run_behat)
    print green('Tests: Done!')


@task(alias='release')
def release():
    print green('Generating release artefacts')
    execute(archive_dump)
    execute(gen_doc)


@task(alias='ls')
@runs_once
def local_setup():
    """
    Complete local installation process, used generally when building the docker image for install and configure Drupal.
    The same that run: $ fab dr gcp cp_keys dmk icreate crun dkuh csy dbs si dcf cs es ss dc cb
    """
    execute(delete_root)
    execute(git_clone_profile)
    execute(copy_ssh_keys)
    execute(drush_make)
    execute(docker_create_image)
    execute(docker_run_container)
    execute(docker_update_host)
    execute(create_symlinks)
    execute(data_base_setup)
    execute(site_install)
    execute(drush_config)
    execute(copy_settings)
    execute(edit_settings)
    execute(secure_settings)
    execute(drush_commands)
    execute(behat_config)
    print green('Local setup finished with success!')
