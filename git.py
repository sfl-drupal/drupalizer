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
from fabric.colors import red, yellow
from fabric.decorators import task

from fabfile.core import *


@task()
def check_status():
    """
    Check workspace's git repositories status.
    """
    if is_git_dirty():
        print(red('Your workspace is not clean.'))
    else:
        print(green('Your workspace is clean.'))


def is_git_dirty():
    repos = local(
        'find {} -path */docker-runtime/* -prune -o -name ".git" -print'
        ''.format(os.path.normpath(env.workspace)),
        capture=True
    ).splitlines()

    nb_warnings = 0
    for repo in repos:
        rep_local_path = os.path.normpath(os.path.join(repo, '..'))
        nb_warnings += _check_repo(rep_local_path)

    return nb_warnings > 0
    # STEP 2
    # Rather than to stop or continue foolishly, it is intelligent and asked
    #  what to do:
    # - If the not-placement code, make a commit
    # - If the Branch is not tracked, then push it
    # - If there are commits to push then push its
    # - Attention to conflicts, make a pull first and validate
    # automatically merging


def _check_repo(repo_local_path):
    """
    Private helper function to check a git repo
    :type repo_local_path: str
    """
    nb_warnings = 0
    with lcd(repo_local_path):
        print(green('---'))
        print(green('Verify repo in ' + repo_local_path))

        remote_name = local('git remote', capture=True)

        f_status_raw_info = _get_files_status_information()
        print(green('Verify local files status against current HEAD commit..'))
        nb_warnings += _check_files_status_vs_head_commit(f_status_raw_info)

        branchs_raw_info = _get_local_branchs_information()
        print(green('Verify local branches exist on remote "{}"'
                    ''.format(remote_name)))
        nb_warnings += _check_local_branchs_exist_on_remote(branchs_raw_info,
                                                            remote_name)
        print(green('Verify branches status against remote...'))
        nb_warnings += _check_local_branchs_status_vs_remote(branchs_raw_info,
                                                             remote_name)
        return nb_warnings


def _check_files_status_vs_head_commit(files_status_raw_info):
    """
    Private helper function to check the status of files vs head in the repo
    :type files_status_raw_info: list
    """
    nb_warnings = 0
    addable_files = []
    if len(files_status_raw_info) > 0:
        status = {
            'M': 'has un-commited modifications.',
            'D': 'has been deleted.',
            '??': 'is not indexed.',
        }
        for file_status in files_status_raw_info:
            file_status_data = file_status.split()
            # Break loop if filename is "fabfile"
            if file_status_data[1] == 'fabfile':
                break
            nb_warnings += 1
            addable_files.append(file_status_data[1])
            print(yellow(
                'File "{}" '.format(file_status_data[1]) +
                status.get(
                    file_status_data[0],
                    'is in an unknown state ({})'.format(file_status_data[0])
                ))
            )
    return nb_warnings


def _check_local_branchs_exist_on_remote(local_branchs_raw_info, remote_name):
    """
    Helper private function to check if a local branch exist on remote
    :type local_branchs_raw_info: str
    :type remote_name: str
    """
    nb_warnings = 0
    pushable_branchs = []
    for local_branch_raw_info in local_branchs_raw_info:
        local_branch_name = _get_branch_name(local_branch_raw_info)
        remote_branch_exists = _remote_branch_exists(local_branch_name)
        if local_branch_name is not None and not remote_branch_exists:
            nb_warnings += 1
            pushable_branchs.append(local_branch_name)
            print(yellow('Local branch "{}" is not present on "{}" '
                         'remote.'.format(local_branch_name,
                                          remote_name)))

    # Suggest to push the branch(s) that are local only
    if nb_warnings > 0:
        if confirm(
                red('There are many local branches not present on remote. '
                    'Do you want to sync theses?'), default=False):
            for branch_name in pushable_branchs:
                local('git push --set-upstream {} {}'.format(remote_name,
                                                             branch_name))
            # Do not alert with diff as local branches are now pushed
            nb_warnings = 0

    return nb_warnings


def _check_local_branchs_status_vs_remote(branchs_raw_infos, remote_name):
    """
    Private helper function to check local branchs vs remotes branchs
    :param branchs_raw_infos: list
    :param remote_name: string
    :return:
    """
    nb_warnings = 0
    pushable_branchs = []
    # git in FR and EN compatible, find out a proper way to support other
    # languages
    pattern = re.compile('.*\[.* (ahead|en avance de) .*\].*')
    for local_branch_raw_info in branchs_raw_infos:
        if pattern.match(local_branch_raw_info):
            local_branch_name = _get_branch_name(local_branch_raw_info)
            nb_warnings += 1
            pushable_branchs.append(local_branch_name)
            print(yellow('Local branch "{}" is ahead of remote branch.'
                         ''.format(local_branch_name)))

    # Suggest to push the branch(s) that are local only
    if nb_warnings > 0:
        if confirm(
                red('There are many local branches which are ahead of remote '
                    'branch. Do you want to sync theses?'), default=False):
            for branch_name in pushable_branchs:
                local('git push {} {}'.format(remote_name, branch_name))
            # Do not alert with diff as local branches are now pushed
            nb_warnings = 0

    # TODO : Push the branch into the repo.
    return nb_warnings


def _get_local_branchs_information():
    """
    Helper private function to get local branchs information
    :return:
    """
    return local('git branch --list -vv', capture=True).splitlines()


def _get_branch_name(branch_raw_data):
    """
    Helper private function to return the name of a branch
    :param branch_raw_data:
    :return:
    """
    branch_name = branch_raw_data.replace('*', '').strip()
    if _is_branch_detached(branch_name):
        return None
    else:
        return branch_name.split()[0]


def _is_branch_detached(branch_name):
    """
    Private helper function to check if a branch is detached
    :param branch_name:
    :return:
    """
    pattern = re.compile(r'\(.*\)')
    return pattern.match(branch_name)


def _remote_branch_exists(branch_name):
    """
    Private helper function to check if a remote branch exists
    :param branch_name:
    :return:
    """
    return len(local('git branch --list --remote "*{}"'.format(branch_name),
                     capture=True).splitlines()) > 0


def _get_files_status_information():
    """
    Private helper function to return a list of modified files
    :return: list
    """
    return local('git status -s', capture=True).splitlines()
