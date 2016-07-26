from os import path

from fabric.api import task, env, local
from fabric.colors import red, green, yellow
from fabric.api import task, env, execute
from fabric.contrib.console import confirm
from .environments import e

import helpers as h
import time
import re

@task(alias='is_dirty')
def check_status():
    """
    Check workspace's git repositories status.
    """

    if (isGitDirty()):
        print red('Your workspace is not clean.')
    else:
        print green('Your workspace is clean.')

def isGitDirty():
    repos = local('find ' + path.normpath(env.workspace) + ' -name ".git"', capture=True).splitlines()
    nbWarnings = 0
    for repo in repos:
        repoLocalPath = path.normpath(path.join(repo, '..'))
        nbWarnings += _checkRepo(repoLocalPath)

    return (nbWarnings > 0)


    # STEP 2
    # plutot que s'arreter ou continuer betement, on est intelligent et on demande quoi faire:
    # - s'il y a du code non-stage, en faire un commit
    # - si la Branch n'est pas trackee, la pusher
    # - s'il y a des commits non pushes, les pusher
    # - attention aux conflits, faire un pull d'abord et valider la fusion automatique


def _checkRepo(repoLocalPath):
    nbWarnings = 0
    with h.fab_cd('local', repoLocalPath):
        print green('---')
        print green('Verify repo in ' + repoLocalPath)

        remoteName = local('git remote', capture=True)

        filesStatusRawInfo = _getFilesStatusInformation()
        print green('Verify local files status against current HEAD commit...')
        nbWarnings += _checkFilesStatusVsHeadCommit(filesStatusRawInfo, remoteName)

        localBranchesRawInfo = _getLocalBranchesInformation()
        print green('Verify local branches exist on remote "' + remoteName + '"...');
        nbWarnings += _checkLocalBranchesExistOnRemote(localBranchesRawInfo, remoteName)

        print green('Verify branches status against remote...');
        nbWarnings += _checkLocalBranchesStatusVsRemote(localBranchesRawInfo, remoteName)

        return nbWarnings


def _checkFilesStatusVsHeadCommit(filesStatusRawInfo, remoteName):
    nbWarnings = 0
    addableFiles = []
    if (len(filesStatusRawInfo) > 0):
        for fileStatus in filesStatusRawInfo:
            fileStatusData = fileStatus.split()
            # Break loop if filename is "fabfile"
            if fileStatusData[1] == 'fabfile':
                break
            nbWarnings += 1
            addableFiles.append(fileStatusData[1])
            print yellow('File "' + fileStatusData[1] + '" ' + {
                'M': 'has un-commited modifications.',
                'D': 'has been deleted.',
                '??': 'is not indexed.',
            }.get(fileStatusData[0], 'is in an unknown state (' + fileStatusData[0] + ')'))

    return nbWarnings

def _checkLocalBranchesExistOnRemote(localBranchesRawInfo, remoteName):
    nbWarnings = 0
    pushableBranches = []
    for localBranchRawInfo in localBranchesRawInfo:
        localBranchName = _getBranchName(localBranchRawInfo)
        if ((localBranchName is not None) and (not _remoteBranchExists(localBranchName))):
            nbWarnings += 1
            pushableBranches.append(localBranchName)
            print yellow('Local branch "' + localBranchName + '" is not present on "' + remoteName + '" remote.')

    # TO DO : PUSHER LA BRANCHE SUR LE REPO
    # if (nbWarnings > 0):
    #     if (confirm(red('There are many local branches not present on remote. Do you want to sync theses?'), default=False)):
    #         for branchName in pushableBranches:
    #             local('git push ' + remoteName + ' ' + branchNqqqame)
    #         # Do not alert with diff as it has been commited and pushed
    #         nbWarnings = 0

    return nbWarnings

def _checkLocalBranchesStatusVsRemote(localBranchesRawInfo, remoteName):
    nbWarnings = 0
    pattern = re.compile('.*\[.* ahead .*\].*')
    for localBranchRawInfo in localBranchesRawInfo:
        if (pattern.match(localBranchRawInfo)):
            nbWarnings += 1
            print yellow('Local branch "' + _getBranchName(localBranchRawInfo) + '" is ahead of remote branch.');

    # TO DO : PUSHER LA BRANCHE SUR LE REPO

    return nbWarnings

def _getLocalBranchesInformation():
    return local('git branch --list -vv', capture=True).splitlines()

def _getBranchName(branchRawData):
    branchName = branchRawData.replace('*', '').strip()
    if (_isBranchDetached(branchName)):
        return None
    else:
        return branchName.split()[0]

def _isBranchDetached(branchName):
    pattern = re.compile('\(.*\)')
    return pattern.match(branchName)


def _remoteBranchExists(branchName):
    return (len(local('git branch --list --remote "*' + branchName + '"', capture=True).splitlines()) > 0)


def _getFilesStatusInformation():
    return local('git status -s', capture=True).splitlines()
