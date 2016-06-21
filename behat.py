from __future__ import unicode_literals
from fabric.api import task, roles, env
from fabric.colors import green

import helpers as h

@task
@roles('docker')
def init(rewrite=True):
    """
    Check installation and configure Behat.
    :param role Default 'role' where to run the task
    :param rewrite If the behat.yml file should be rewrited or not.
    """
    
    role = 'docker'
    workspace = env.docker_workspace
    host = env.site_hostname
    site_root = env.docker_site_root

    if not h.fab_exists(role, '{}/tests/behat/behat.yml'.format(workspace)) or rewrite:
        with h.fab_cd(role, '{}/tests/behat'.format(workspace)):
            h.fab_run(role, 'cp example.behat.yml behat.yml')
            h.fab_run(role, 'sed -i "s@%DRUPAL_ROOT@{}@g" behat.yml'.format(site_root))
            h.fab_run(role, 'sed -i "s@%URL@http://{}@g" behat.yml'.format(host))
            h.fab_run(role, 'echo "127.0.0.1  {}" >> /etc/hosts'.format(host))
        print green('Behat is now properly configured. The configuration file is {}/tests/behat/behat.yml'.format(workspace))
    else:
      print green('{}/tests/behat/behat.yml is already created.'.format(workspace))


@task()
@roles('docker')
def install():
    """
    Install behat
    """

    role = 'docker'
    workspace = env.docker_workspace

    if not h.fab_exists(role, '/usr/local/bin/behat'):
        with h.fab_cd(role, '{}/tests/behat'.format(workspace)):
            h.fab_run(role, 'curl -s https://getcomposer.org/installer | php')
            h.fab_run(role, 'php composer.phar install')
            h.fab_run(role, 'ln -s bin/behat /usr/local/bin/behat')
        print green('Behat has been properly installed with Composer in /usr/local/bin')
    else:
        print(green('Behat is already installed, no need for a new installation'))


@task
@roles('docker')
def run(tags='~@wip&&~@disabled&&~@test'):
    """
    Execute the complete Behat tests suite.
    :param role Default 'role' where to run the task
    """

    role = 'docker'
    workspace = env.docker_workspace

    h.fab_run(role, 'mkdir -p {}/logs/behat'.format(workspace))
    # In the container behat is installed globaly, so check before install it inside the tests directory
    if not h.fab_exists(role, '/usr/local/bin/behat') or not h.fab_exists(role, '../tests/behat/bin/behat'):
        install()
    # If the configuration file behat.yml doesn't exist, call behat_init before run the test.
    if not h.fab_exists(role, '{}/tests/behat/behat.yml'.format(workspace)):
        init()
    with h.fab_cd(role, '{}/tests/behat'.format(workspace)):
        h.fab_run(role, 'behat --format junit --format pretty --tags "{}" --colors'.format(tags))

