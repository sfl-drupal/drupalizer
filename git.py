from os import path

from fabric.api import task, env, local
from fabric.colors import red, green, yellow
from fabric.api import task, env, execute
from .environments import e

import helpers as h
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
        with h.fab_cd('local', repoLocalPath):
            print green('---')
            print green('Verify repo in ' + repoLocalPath)

            remoteName = local('git remote', capture=True)

            localBranchesRawInfo = _getLocalBranchesInformation()
            for localBranchRawInfo in localBranchesRawInfo:
                localBranchName = _getBranchName(localBranchRawInfo)
                if ((localBranchName is not None) and (not _remoteBranchExists(localBranchName))):
                    nbWarnings += 1
                    print yellow('Local branch "' + localBranchName + '" is not present on "' + remoteName + '" remote.')

            print green('Verify branches status against remote...');
            pattern = re.compile('.*\[.* ahead .*\].*')
            for localBranchRawInfo in localBranchesRawInfo:
                if (pattern.match(localBranchRawInfo)):
                    nbWarnings += 1
                    print yellow('Local branch "' + _getBranchName(localBranchRawInfo) + '" is ahead of remote branch.');

            print green('Verify local files status against current HEAD commit...')
            filesStatusRawInfo = _getFilesStatusInformation()
            if (len(filesStatusRawInfo) > 0):
                for fileStatus in filesStatusRawInfo:
                    fileStatusData = fileStatus.split()
                    nbWarnings += 1
                    print yellow('File "' + fileStatusData[1] + '" ' + {
                        'M': 'has un-commited modifications.',
                        '??': 'is not indexed.',
                    }.get(fileStatusData[0], 'is in an unknown state (' + fileStatusData[0] + ')'))

    return (nbWarnings > 0)


    # STEP 2
    # plutot que s'arreter ou continuer betement, on est intelligent et on demande quoi faire:
    # - s'il y a du code non-stage, en faire un commit
    # - si la Branch n'est pas trackee, la pusher
    # - s'il y a des commits non pushes, les pusher

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
