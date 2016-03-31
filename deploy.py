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
from fabric.api import lcd, cd, task, roles, env, local, run, runs_once, execute
from fabric.contrib.project import rsync_project
from fabric.colors import red, green
from fabric.utils import abort

import helpers as h
import os, glob

@task
@roles('local')
def to_aegir(environement, build='0', role='local', migrate_sites=False, delete_old_platforms=False):
    """Deploy the artifact to the aegir server.

    $ fab deploy.to_aegir

    :param environement: the environnement (dev, stage, production)
    :param build: the number of the build in Jenkins
    :param role: the role to run the task in fabric
    :param migrate_sites: if aegir should migrate the sites to the new platform
    :param delete_old_platforms: if aegir should remove old platforms
    """
    aegir_server = env.aegir_server
    aegir_user = env.aegir_user
    aegir_path = env.aegir_path
    aegir_dest_server = env.aegir_dest_server
    build_dir = '{}/build'.format(env.workspace)
    if environement == 'dev' and aegir_server and aegir_user and aegir_path and aegir_dest_server:
        os.chdir(build_dir)
        for artifact in glob.glob("*.tar.gz"):
            # Get platform name
            platform_name = '{}-{}-{}'.format(environement, artifact.split('.')[0], build)

            # Remove old platforms
            if h.fab_exists(role, env.site_root):
                h.fab_run(role, 'rm -rf {}'.format(env.site_root))

            # Untar new platform
            with h.fab_cd(role, '{}/src'.format(env.workspace)):
                h.fab_run(role, 'tar -xvzf {}/build/{}'.format(env.workspace, artifact))

            # Rsync new platform
            with h.fab_cd(role, env.workspace):
                print green('Rsync {} to aegir'.format(platform_name))
                h.fab_run(role, 'rsync -a src/drupal/ {}@{}:{}/platforms/{}'.format(aegir_user, aegir_server,
                                                                                    aegir_path, platform_name))

            # Declare platform in aegir
            print green('Declaring {} in aegir'.format(platform_name))
            h.fab_run(
                role,
                """
                ssh {}@{} "drush --root='{}/platforms/{}' provision-save '@platform_{}' --context_type='platform' --web_server=@{}"
                """.format(aegir_user, aegir_server, aegir_path, platform_name, platform_name, aegir_dest_server)
            )
            h.fab_run(
                role,
                """
                ssh {}@{} "drush @hostmaster hosting-import platform_{}"
                """.format(aegir_user, aegir_server, platform_name)
            )
            h.fab_run(
                role,
                """
                ssh {}@{} "drush @hostmaster hosting-dispatch"
                """.format(aegir_user, aegir_server)
            )
            if migrate_sites == 'true':
                print green("Migrating all websites currently on {} to {}".format(environement, platform_name))
                h.fab_run(
                    role,
                    """
                    ssh {}@{} "./migrateS.drush {} {}"
                    """.format(aegir_user, aegir_server, environement, platform_name))

            # Remove old platforms
            h.fab_run(role, 'rm -rf {}'.format(env.site_root))
            h.fab_run(role, 'rm -rf {}/build/{}'.format(env.workspace, artifact))

        # Delete old platforms in aegir
        if delete_old_platforms == 'true':
            print green("Deleting old platforms on {}".format(environement))
            h.fab_run(
                    role,
                    """
                    ssh {}@{} "./deleteP.drush {} {}"
                    """.format(aegir_user, aegir_server, environement, platform_name))

    else:
        print red('There are not enought information to deploy the platformt')


def set_hosts(environment):
    """
    Set the hosts Fabric environment variable with the target environment.
    This is the host that will be used to run SSH commands on.
    """
    if environment not in env.aliases:
        abort('Environment {} could not be found in the aliases definition.'.format(environment))

    target = env.aliases.get(environment)
    env.hosts = ['{}@{}'.format(target.get('user'), target.get('host'))]


def is_aegir_deployment(target):
  """Check if the target environment is an Aegir server."""
  return False if 'aegir' not in target or target.get('aegir') is False else True


def _aegir_platform_name(target, environment):
  """Build the platform needed by Aegir, from the placeholder in configuration file.
  """
  if 'aegir_platform' not in target:
    abort('Aegir needs a unique platform name to function properly. Check your aegir_platform key in your aliases.')
  aegir_platform = target.get('aegir_platform')
  return aegir_platform.format(name=env.project_name, env=environment, build=env.build_number)


def target_dir(environment):
  target = env.aliases.get(environment)
  return target.get('root') + _aegir_platform_name(target, environment) if is_aegir_deployment(target) else target.get('root')


def get_archive_from_dir(directory):
  """List tarball archives in a directory.
  """
  files = glob.glob1(directory, '*.tar.gz')
  if len(files) == 0:
    abort('No tarball found in {}'.format(directory))
  if len(files) > 1:
    abort('More than one tarball has been found in {}. Can not decide which one to deploy.'.format(directory))
  return files[0]


@task
def provision(environment, role='local'):
    """Provision a Jenkins deployment.

    This task loads the target environment and extract the archive to deploy.
    """
    set_hosts(environment)

    artefact = get_archive_from_dir(env.builddir)

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

        print green('The platform {} is now ready to be deployed to the target environment {}.'.format(artefact, environment))



@task
def push(environment, role='local'):
    """Push the platform to the target environment.

        :param environment: The target environment. It must match a valid Drush alias.
    """
    target = env.aliases.get(environment)
    target_directory = target_dir(environment)

    local('rsync -a src/drupal/ {}@{}:{}'.format(target.get('user'), target.get('host'), target_directory))

    if is_aegir_deployment(target):
        platform = _aegir_platform_name(target, environment)
        _aegir_provision_platform(platform, target.get('aegir_path'), target.get('aegir_destsrv'))


def _aegir_provision_platform(platform, aegir_path, aegir_destsrv):
    # Provision the platform on Aegir
    run('drush --root="{}/platforms/{}" provision-save "@platform_{}" --context_type="platform" --web_server=@{}'.format(aegir_path, platform, platform, aegir_destsrv))
    run('drush @hostmaster hosting-import platform_{}'.format(platform))
    run('drush @hostmaster hosting-dispatch')


def _aegir_migrate_sites(environment, platform):
    run('{}/migrate-sites {} {}'.format(environment, platform))

@task
@roles('local')
def migrate(environment, role='local'):
    """Migrate the Drupal database on the target environment.

        :param environment: The target environment. It must match a valid Drush alias.
    """
    target = env.aliases.get(environment)
    if is_aegir_deployment(target) and env.migrate == "true":
        platform = _aegir_platform_name(target, environment)
        _aegir_migrate_sites(environment, platform)


        # Run the updatedb script
        # with h.fab_cd(role, env.site_root):
        # Run the Drupal update script
#        h.fab_run(
    #        role,
    #        'drush --yes @{} updatedb'
    #          .format(environment)
    #    )
  #      print green('The target environment {} is up-to-date.'.format(environment))
#

        # Clear caches
 #       h.fab_run(
   #       role,
    #      'drush --yes @{} cache-clear all'
    #        .format(environment)
     #   )
   #     print green('The caches have been cleared on the target environment {}.'.format(environment))


@task
@roles('local')
def to_server(environement, role='local'):
    """Deploy the artifact to the aegir server.

        $ fab deploy.to_aegir

        :param environement: the environnement (dev, stage, production)
        :param role: the role to run the task in fabric
    """
    build_dir = '{}/build'.format(env.workspace)
    os.chdir(build_dir)
    for artifact in glob.glob("*.tar.gz"):
        # Remove old platforms
        if h.fab_exists(role, env.site_root):
            h.fab_run(role, 'rm -rf {}'.format(env.site_root))

        # Untar new platform
        print green('Untar new platform')
        with h.fab_cd(role, '{}/src'.format(env.workspace)):
            h.fab_run(role, 'tar -xvzf {}/build/{}'.format(env.workspace, artifact))
            d.aliases()

        with h.fab_cd(role, env.site_root):
            # Set the site in maintenance mode
            print green('Set the site in maitenance mode')
            h.fab_run(
                role,
                'drush --yes @{} vset site_offline 1'
                    .format(environement)
            )
            # rsync
            print green('Rsync the site source code')
            h.fab_run(
                role,
                'drush --yes rsync --exclude=sites/all/files --exclude-files --exclude=.htaccess --delete --verbose @self @{}'
                    .format(environement)
            )
            # update data base
            print green('Update site database')
            h.fab_run(
                role,
                'drush --yes @{} updatedb'
                    .format(environement)
            )
            # Set site online
            print green('Set the site online')
            h.fab_run(
                role,
                'drush --yes @{} vset site_offline 0'
                    .format(environement)
            )
            # clean cache
            print green('Clear site cache')
            h.fab_run(
                role,
                'drush --yes @{} cache-clear all'
                    .format(environement)
            )
        # Remove old platforms
        h.fab_run(role, 'rm -rf {}'.format(env.site_root))
        h.fab_run(role, 'rm -rf {}/build/{}'.format(env.workspace, artifact))
        print green('Deployment in {} finished'.format(environement))
