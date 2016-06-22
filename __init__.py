import docker
from deploy  import *
import drush
import behat
import patternlab
from .environments import e

from fabric.api import task, env, execute

import helpers as h
from os import path
from fabric.colors import red, green

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

    verif()
    execute(drush.make, 'update')
    execute(drush.updatedb)
    execute(behat.init)

@task
def verif():
    # STEP 1
    # se mettre a la racine du projet
    h.fab_cd('local', env.workspace)
    # chercher tous les repertoires .git (de maniere recursive)
    repos = local('find ./ -type d -name ".git"', capture=True).splitlines()
    # pour chaque .git trouve, s'y rendre et voir ce qu'il en est
    for repo in repos:
        #repoLocalPath = path.join(env.workspace, repo).replace('/.git', '')
        repoLocalPath = path.normpath(path.join(env.workspace, repo, '..'))
        with h.fab_cd('local', repoLocalPath):
            print green('Verfiy repo in ' + repoLocalPath)
            remoteName = local('git remote', capture=True)
            # - est ce que les branches locales existent sur la remote (git branch -vv)
            remoteBranches = local('git branch -rvv', capture=True).splitlines()
            for (i, remoteBranch) in enumerate(remoteBranches):
                remoteBranches[i] = remoteBranch.replace('* ', '').strip().split(' ').pop(0)
            localBranches = local('git branch -lvv', capture=True).splitlines()
            for (i, localBranch) in enumerate(localBranches):
                localBranches[i] = localBranch.replace('* ', '').strip().split(' ').pop(0)
            for localBranch in localBranches:
                if ((remoteName + '/' + localBranch) not in remoteBranches):
                    print red('Local branch "' + localBranch + '" is not present on "' + remoteName + '" remote.')
                    # to do, la pusher (git push remoteName localBranch)

            # - pour chaque Branch, est ce qu'il y a des commits non-pushes (git branch -vv)
            # - est ce qu'il y a du code non-stage (git status -s)
            # on s'arrete a chaque alerte, et on demande quoi faire...


    # STEP 2
    # plutot que s'arreter ou continuer betement, on est intelligent et on demande quoi faire:
    # - s'il y a du code non-stage, en faire un commit
    # - si la Branch n'est pas trackee, la pusher
    # - s'il y a des commits non pushes, les pusher

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
