import docker
from deploy  import *
import drush
import behat
import patternlab
from .environments import e

from fabric.api import task, env, execute

from fabric.colors import red
from fabric.contrib.console import confirm

import git

@task
def init():
    """
    Complete local installation process, used generally when building the docker image for install and configure Drupal.
    """

    execute(docker.image_create)
    execute(docker.container_start)
    execute(drush.make, 'install')
    execute(drush.site_install, host='root@{}'.format(env.container_ip))
    execute(drush.aliases)
    execute(behat.init, host='root@{}'.format(env.container_ip))



@task
def test():
    """
    Setup Behat and run the complete tests suite. Default output formatters: pretty and JUnit.
    The JUnit report file is specified in the Behat configuration file. Default: tests/behat/out/behat.junit.xml.

    :param tag Specific Behat tests tags to run.

    """
    execute(behat.init)
    execute(behat.run)



@task
def install():

    """
    Run the full installation process.
    """

    execute(drush.make, 'install')
    execute(drush.site_install)
    execute(behat.init)



@task
def update():

    """
    Update the full codebase and run the availabe database updates.
    """

    if (git.isGitDirty()):
      if (confirm(red('There are warnings on status of your repositories. '
                      'Do you want to continue and reset all changes to remote repositories'' states?'), default=False)):
        execute(drush.make, 'update')
        execute(drush.updatedb)
        execute(behat.init)


@task
def release():

    """
    Generate all artefacts related to a release process or a deployment process.
    """

    execute(drush.archive_dump)
    execute(drush.gen_doc)


@task
def deploy(environment):
    """Deploy code and run database updates on a target Drupal environment.
    """

    execute(provision, environment)
    execute(push, environment, hosts=env.hosts)
    execute(migrate, environment, hosts=env.hosts)
