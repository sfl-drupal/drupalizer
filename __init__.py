from .deploy import *
import drush
import behat 
import docker
from .environments import e

from fabric.api import lcd, cd, task, roles, env, local, run, runs_once, execute

import helpers as h

@task
def init():
    """
    Complete local installation process, used generally when building the docker image for install and configure Drupal.
    """

    execute(docker.image_create)
    execute(docker.container_start)
    execute(drush.make, 'install')
    execute(drush.site_install)
    execute(drush.aliases)
    execute(behat.init)  



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

    execute(drush.make, 'update')
    execute(drush.updatedb)
    execute(behat.init)
  

@task
def release():

    """
    Generate all artefacts related to a release process or a deployment process.
    """
    
    execute(drush.archive_dump)
