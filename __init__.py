import docker
from deploy  import *
import drush
import behat
import patternlab
from .environments import e

from fabric.api import task, env, execute

import helpers as h
import re
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
    h.fab_cd('local', env.workspace)
    repos = local('find ./ -type d -name ".git"', capture=True).splitlines()
    for repo in repos:
        repoLocalPath = path.normpath(path.join(env.workspace, repo, '..'))
        with h.fab_cd('local', repoLocalPath):
            print green('Verify repo in ' + repoLocalPath)

            remoteName = local('git remote', capture=True)

            localBranches = _getLocalBranchNames()
            for localBranch in localBranches:
                if (not _remoteBranchExists(localBranch)):
                    print red('Local branch "' + localBranch + '" is not present on "' + remoteName + '" remote.')
                    # to do, la pusher (git push remoteName localBranch)

            print green('Verify branches status against remote...');
            branches = local('git branch --list -vv', capture=True).splitlines()
            pattern = re.compile('.*\[.* ahead .*\].*')
            for branch in branches:
                if (pattern.match(branch)):
                    print red('Local branch "' + branch.replace('*', '').strip().split()[0] + '" is ahead of remote branch.');
            # - est ce qu'il y a du code non-stage (git status -s)
            # on s'arrete a chaque alerte, et on demande quoi faire...


    # STEP 2
    # plutot que s'arreter ou continuer betement, on est intelligent et on demande quoi faire:
    # - s'il y a du code non-stage, en faire un commit
    # - si la Branch n'est pas trackee, la pusher
    # - s'il y a des commits non pushes, les pusher

def _getLocalBranchNames():
    branches = local('git branch --list', capture=True).splitlines()
    branchNames = []
    for (i, branch) in enumerate(branches):
        branchName = branch.replace('*', '').strip()
        if (not _isBranchDetached(branchName)):
            branchNames.append(branchName)

    return branchNames


def _isBranchDetached(branchName):
    pattern = re.compile('\(.*\)')
    return pattern.match(branchName)


def _remoteBranchExists(branchName):
    return (len(local('git branch --list --remote "*' + branchName + '"', capture=True).splitlines()) > 0)


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
