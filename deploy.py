from __future__ import unicode_literals
from fabric.api import lcd, cd, task, roles, env, local, run, runs_once, execute
from fabric.contrib.project import rsync_project
from fabric.colors import red, green

import helpers as h
import drush as d
import os, glob

@task
@roles('local')
def to_aegir(environement, build='0', role='local', migrate_sites=False, delete_old_platforms=False):
    """Import and restore the specified database dump.

    $ fab core.db_import:/tmp/db_dump.sql.gz

    :param filename: a full path to a gzipped sql dump.
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


@task
@roles('local')
def to_server(environement, role='local'):
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

