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

from __future__ import unicode_literals
from fabric.api import task, env, local, run
from fabric.colors import green
from fabric.utils import abort

import helpers as h
import os
import glob


def _set_hosts(environment):
    """
    Set the hosts Fabric environment variable with the target environment.
    :param environment This is the host that will be used to run SSH commands on.
    """
    if environment not in env.aliases:
        abort('Environment {} could not be found in the aliases definition.'.format(environment))

    target = env.aliases.get(environment)
    env.hosts = ['{}@{}'.format(target.get('user'), target.get('host'))]


def _is_aegir_deployment(target):
    """
    Check if the target environment is an Aegir server.
    """
    return False if 'aegir' not in target or target.get('aegir') is False else True


def _aegir_platform_name(target, environment):
    """
    Build the platform needed by Aegir, from the placeholder in configuration file.
    """
    if 'aegir_platform' not in target:
        abort('Aegir needs a unique platform name to function properly. Check your aegir_platform key in your aliases.')
    aegir_platform = target.get('aegir_platform')
    return aegir_platform.format(name=env.project_name, env=environment, build=env.build_number)


def _target_dir(environment):
    """
    Return the target directory to deploy the site.
    :param environment
    """
    target = env.aliases.get(environment)
    if _is_aegir_deployment(target):
        return target.get('root') + _aegir_platform_name(target, environment)
    return target.get('root')


def _set_site_offline(target, environment):
    """
    Helper function to set the site in maintenance.
    :param environment
    """
    run('drush --yes --root={}  vset site_offline 1'.format(target.get('root')))
    print(green('The is in maintenance mode on the target environment {}.'.format(environment)))


def _set_site_online(target, environment):
    """
    Helper function to set the site online.
    :param environment
    """
    run('drush --yes --root={} vset site_offline 0'.format(target.get('root')))
    print(green('The site is online on the target environment {}.'.format(environment)))


def _update_site_database(target, environment):
    """
    Helper function to update site database.
    :param environment
    """
    run('drush --yes --root={} updatedb'.format(target.get('root')))
    print(green('The target environment {} is up-to-date.'.format(environment)))


def _clear_site_cache(target, environment):
    """
    Helper function to clear site cache.
    :param environment
    """

    run('drush --yes --root={} cache-clear all'.format(target.get('root')))
    print(green('The cache have been cleared on the target environment {}.'.format(environment)))


def _get_archive_from_dir(directory):
    """
    List tarball archives in a directory.
    :param directory The directory used to untar the artefact.
    """
    files = glob.glob1(directory, '*.tar.gz')
    if len(files) == 0:
        abort('No tarball found in {}'.format(directory))
    if len(files) > 1:
        abort('More than one tarball has been found in {}. Can not decide which one to deploy.'.format(directory))
    return files[0]


def _rsync_platform(target, target_directory):
    """
    Helper function to rsync platform to server.
    """
    local('rsync -a src/drupal/ {}@{}:{}'.format(target.get('user'), target.get('host'), target_directory))


def _aegir_provision_platform(platform, aegir_path, aegir_destsrv):
    """
    Provision the platform on Aegir
    :param platform The platform name
    :param aegir_path The path to the home of aegir, usually in /var/aegir
    :param aegir_destsrv The destination webserver for the platform.
    """
    run('drush --root="{}/platforms/{}" provision-save "@platform_{}" --context_type="platform" --web_server=@{}'
        .format(aegir_path, platform, platform, aegir_destsrv))
    run('drush @hostmaster hosting-import platform_{}'.format(platform))
    run('drush @hostmaster hosting-dispatch')


def _aegir_migrate_sites(target, environment, platform):
    """
    Helper funtion to migrage sites in aegir after a deployment.
    :param environment
    :param platform The patern name of the platform in wich the sites will be migrated on
    """
    aegir_path = target.get('aegir_path')
    run('{}/migrate-sites {} {}'.format(aegir_path, environment, platform))


def _aegir_remove_platform_without_sites(target, environment, platform):
    """
    Helper funtion to remove platforms without sites in aegir after a deployment.
    :param environment
    :param platform The patern name of the platform in wich the sites will be migrated on
    """
    aegir_path = target.get('aegir_path')
    run('{}/remove-platforms {} {}'.format(aegir_path, environment, platform))


@task
def provision(environment, role='local'):
    """
    Provision a Jenkins deployment.
    This task loads the target environment and extract the archive to deploy.
    :param environment The environment to deploy the site DEV, STAGE, PROD
    :param role Tha fabric role to run the task.
    """
    _set_hosts(environment)

    artefact = _get_archive_from_dir(env.builddir)

    with h.fab_cd(role, '{}/src'.format(env.workspace)):

        # Clear the currently installed platform
        if h.fab_exists(role, env.site_root):
            h.fab_run(role, 'rm -rf {}'.format(env.site_root))
        # Extract the platform to deploy
        h.fab_run(role, 'tar -xzf {}/{}'.format(env.builddir, artefact))

        # Fast-check if the archive looks like a Drupal installation
        if not h.fab_exists(role, '{}/src/drupal'.format(env.workspace)):
            abort('The archive to deploy does not contain a drupal directory.')

        if not os.path.isfile('{}/src/drupal/cron.php'.format(env.workspace)):
            abort('The archive to deploy does not seem to contain a valid Drupal installation.')

        print(green('The platform {} is now ready to be deployed to the target environment {}.'.format(artefact,
                                                                                                       environment)))


@task
def push(environment):
    """
    Push the platform to the target environment.
   :param environment: The target environment. It must match a valid Drush alias.
    """
    target = env.aliases.get(environment)
    target_directory = _target_dir(environment)

    if _is_aegir_deployment(target):
        # Push platform to Aegir Server
        _rsync_platform(target, target_directory)
        platform = _aegir_platform_name(target, environment)
        _aegir_provision_platform(platform, target.get('aegir_path'), target.get('aegir_destsrv'))
    else:
        # Push platform to Web Server
        _set_site_offline(target, environment)
        _rsync_platform(target, target_directory)


@task
def migrate(environment):
    """
    Migrate the Drupal database on the target environment.
    :param environment: The target environment. It must match a valid Drush alias.
    """
    target = env.aliases.get(environment)
    if _is_aegir_deployment(target):
        # Deploy to Aegir server.
        platform = _aegir_platform_name(target, environment)
        if env.get('migrate_sites', "false") == "true":
            _aegir_migrate_sites(target, environment, platform)

        if env.get('remove_platforms', "false") == "true":
            _aegir_remove_platform_without_sites(target, environment, platform)
    else:
        # Deploy to a Web Server
        _update_site_database(target, environment)
        _clear_site_cache(target, environment)
        _set_site_online(target, environment)
