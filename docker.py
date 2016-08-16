from __future__ import unicode_literals
from fabric.api import task, roles, env, local, run
from fabric.colors import red, green

import helpers as h

###########################################################
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


@task
@roles('local')
def connect(role='local'):
    """
    Connect to a docker container using "docker -it exec <name> bash".
    This is a better way to connect to the container than using ssh'
    :param role Default 'role' where to run the task
    """
    with h.fab_cd(role, env.workspace):
        if docker_isrunning('{}_container'.format(env.project_name)):
            h.fab_run(role, 'docker exec -it {}_container bash'.format(env.project_name))
        else:
            print(red('Docker container {}_container is not running, it should be running to be able to connect.'))


@task
@roles('local')
def image_create(role='local'):

    """
    Create docker images
    :param role Default 'role' where to run the task
    """

    with h.fab_cd(role, env.workspace):
        if '{}/drupal'.format(env.project_name) in docker_images():
            print(red('Docker image {}/drupal was found, you has already build this image'.format(env.project_name)))
        else:
            h.copy_public_ssh_keys(role)
            h.fab_run(role, 'docker build -t {}/drupal .'.format(env.project_name))
            print(green('Docker image {}/drupal was build successful'.format(env.project_name)))


@task
@roles('local')
def container_start(role='local'):
    """
    Run docker containers
    :param role Default 'role' where to run the task
    """
    with h.fab_cd(role, env.workspace):
        if '{}/drupal'.format(env.project_name) in docker_images():
            if docker_tryrun('{}/drupal'.format(env.project_name),
                             '{}_container'.format(env.project_name),
                             '-d -p {}:80'.format(env.bind_port),
                             mounts=[(env.workspace, env.docker_workspace, True)]):
                # If container was successful build, get the IP address and show it to the user.
                env.container_ip = h.fab_run(role, 'docker inspect -f "{{{{.NetworkSettings.IPAddress}}}}" '
                                             '{}_container'.format(env.project_name), capture=True)
                if env.get('always_use_pty', True):
                    h.fab_update_hosts(env.container_ip, env.site_hostname)

                    print(green('Docker container {}_container was build successful. '
                                'To visit the Website open a web browser in http://{} or '
                                'http://localhost:{}.'.format(env.project_name, env.site_hostname, env.bind_port)))

                h.fab_update_container_ip(env.container_ip)

        else:
            print(red('Docker image {}/drupal not found and is a requirement to run the {}_container.'
                      'Please, run first "fab create" in order to build the {}/drupal '
                      'image'.format(env.project_name, env.project_name, env.project_name)))


@task
@roles('local')
def container_stop(role='local'):
    """
    Stop docker containers
    :param role Default 'role' where to run the task
    """
    with h.fab_cd(role, env.workspace):
        if '{}_container'.format(env.project_name) in docker_ps():
            if env.get('always_use_pty', True):
                h.fab_remove_from_hosts(env.site_hostname)
            h.fab_run(role, 'docker stop {}_container'.format(env.project_name))
            print(green('Docker container {}_container was successful stopped'.format(env.project_name)))
        else:
            print(red('Docker container {}_container was not running or paused'.format(env.project_name)))


@task
@roles('local')
def container_remove(role='local'):
    """
    Stop docker containers
    :param role Default 'role' where to run the task
    """
    with h.fab_cd(role, env.workspace):
        if '{}_container'.format(env.project_name) in docker_ps():

            if env.get('always_use_pty', True):
                h.fab_remove_from_hosts(env.site_hostname)
            
            h.fab_run(role, 'docker rm -f {}_container'.format(env.project_name))
            print(green('Docker container {}_container was successful removed'.format(env.project_name)))
        else:
            print(red('Docker container {}_container was already removed'.format(env.project_name)))


@task()
@roles('local')
def image_remove(role='local'):
    """
    Remove docker container and images
    :param role Default 'role' where to run the task
    """
    with h.fab_cd(role, env.workspace):
        if docker_isrunning('{}_container'.format(env.project_name)):
            print(red('Docker container {}_container is running, '
                      'you should stopped it after remove the image {}/drupal'.format(env.project_name,
                                                                                      env.project_name)))
        if '{}/drupal'.format(env.project_name) in docker_images():
            h.fab_run(role, 'docker rmi -f {}/drupal'.format(env.project_name))
            # Remove dangling docker images to free space.
            if '<none>' in docker_images():
                h.fab_run(role, 'docker images --filter="dangling=true" -q | xargs docker rmi -f')
            print(green('Docker image {}/drupal was successful removed'.format(env.project_name)))
        else:
            print(red('Docker image {}/drupal was not found'.format(env.project_name)))


@task
@roles('docker')
def update_host():
    """
    Update hostname resolution in the container.
    """

    site_hostname = run("hostname")
    run("sed  '/{}/c\{} {}  localhost.domainlocal' "
        "/etc/hosts > /root/hosts.backup".format(env.container_ip, env.container_ip, site_hostname))
    run("cat /root/hosts.backup > /etc/hosts")

    h.fab_update_container_ip()
