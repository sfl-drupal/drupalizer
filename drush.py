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
from datetime import datetime

from fabric.api import task
from fabric.colors import red

from .core import *
from .git import is_git_dirty


@task
def make(action='install'):
    """
    Build the platform by running the Makefile specified in the local_vars.py
     configuration file.
    """
    if env.get('always_use_pty', True):
        if is_git_dirty():
            if not confirm(red('There are warnings on status of your '
                               'repositories. Do you want to continue and '
                               'reset all changes to remote repositories '
                               'states?'), default=False):
                abort('Aborting "drush {}" since there might be a risk of '
                      'loosing local data.'.format(action))

    drupal = '{}/drupal'.format(env.workspace)
    drush_opts = "--prepare-install " if action != 'update' else ''

    # Update profile codebase
    if env.site_profile_repo and is_custom_profile(env.site_profile):
        update_profile()

    if env.site_languages:
        if not env.get('always_use_pty', True):
            drush_opts += "--translations={} ".format(env.site_languages)
        elif confirm(red('Say [Y] to {} the site at {} with the specified '
                         'translation(s): {}. If you say [n] the site will be '
                         'installed in English only'
                         ''.format(action, env.site_root,
                                   env.site_languages))):
            drush_opts += "--translations= {} ".format(env.site_languages)

    if env.get('always_use_pty', True):
        drush_opts += " --working-copy --no-gitinfofile"
    if not os.path.exists(drupal):
        local("mkdir {}".format(drupal))
    with lcd(drupal):
        dk_run(env.services['php'], user='root',
               cmd='chown -R {}:{} .'.format(env.local_userid,
                                             env.apache_userid))
        local('drush make {} {} -y'.format(drush_opts, env.makefile))
        fix_permissions()


@task
def aliases():
    """
    Copy conf/aliases.drushrc.php in the site environment.
    """
    drush_aliases = env.site_drush_aliases
    workspace = env.workspace

    if not os.path.exists(drush_aliases):
        dk_run(env.services['php'], user='root',
               cmd='mkdir {}'.format(drush_aliases))

    if os.path.exists('{}/aliases.drushrc.php'.format(drush_aliases)):
        dk_run(env.services['php'], user='root',
               cmd='rm {}/aliases.drushrc.php'.format(drush_aliases))
    if os.path.exists('{}/conf/aliases.drushrc.php'.format(workspace)):
        dk_run(env.services['php'], user='root',
               cmd='cp {}/conf/aliases.drushrc.php {}/'.format(workspace,
                                                          drush_aliases))
        print(green('Drush aliases have been copied to {} directory.'
                    ''.format(drush_aliases)))
    else:
        print(green('Drush aliases have not been found'))

@task
def updatedb():
    """
    Run the available database updates. Similar to drush updatedb.
    """
    service = env.services['php']
    dk_run(service, cmd='drush updatedb -y')
    hook_execute(env.hook_post_update, service)


@task
def site_install():
    """
    Run the site installation procedure.
    """

    service = env.services['php']
    profile = env.site_profile
    db_user = env.site_db_user
    db_pass = env.site_db_pass
    db_host = env.site_db_host
    db_name = env.site_db_name
    site_name = env.site_name
    site_admin_name = env.site_admin_user
    site_admin_pass = env.site_admin_pass
    site_subdir = env.site_subdir

    profile_opts = ''
    locale = ''
    if env.site_languages:
        locale = '--locale="{}"'.format(env.site_languages.split(',')[0])
    if env.site_conf and env.site_profile == "config_installer":
        profile_opts += " config_installer " \
                      "config_installer_sync_configure_form.sync_directory=" \
                      "{}".format(env.site_conf)
    dk_run(service, user='root',
           cmd='chown -R {}:{} .'.format(env.apache_userid, env.local_userid))
    if env.drupal_version == 8:
        dk_run(service, cmd='composer install')

    dk_run(
        service,
        cmd="drush site-install {} {} {} --db-url=mysql://{}:{}@{}/{} "
            "--site-name='{}' --account-name={} --account-pass={} "
            "--sites-subdir={} -y"
            "".format(profile, profile_opts, locale, db_user, db_pass,
                      db_host, db_name, site_name, site_admin_name,
                      site_admin_pass, site_subdir)
    )
    fix_permissions()

    print(green('Site installed successfully!'))

    # Import db_dump if it exists.
    if 'db_dump' in env and env.db_dump is not False:
        import_dump(env.db_dump, service=env.services['db_server'])

    hook_execute(env.hook_post_install, service)


@task
def fix_permissions():
    """
    Securing file permissions and ownership
    """
    fix_files_owner_and_permissions()


@task
def archive_dump(service=env.services['php']):
    """
    Archive the platform for release or deployment.
    :param service Default 'service' where to run the task
    """
    platform = '{}-{}.tar.gz'.format(env.project_name,
                                     datetime.now().strftime('%Y%m%d_%H%M%S'))
    dk_run(service, user=env.local_userid,
           cmd='rm -f {}/build/*.tar.gz'.format(env.code_workspace))
    print(green('All tar.gz archives found in {}/build have been deleted.'
                ''.format(env.code_workspace)))

    dk_run(
        service,
        user=env.local_userid,
        cmd="drush archive-dump --destination={}/build/{} --tags='sflinux {}' "
            "--generatorversion='3.x' "
            "--generator='Drupalizer::fab drush.archive_dump' "
            "--tar-options='--exclude=.git'"
            "".format(env.code_workspace, platform, env.project_name)
    )


@task
def gen_doc(service=env.services['php']):
    """
    Generate README file
    :param service Default 'service' where to run the task
    """
    if os.path.exists('{}/README.adoc'.format(env.code_workspace)):
        dk_run(service, user=env.local_userid,
               cmd='asciidoctor -d book -b html5 -o {}/README.html '
                   '{}/README.adoc'.format(env.code_workspace,
                                           env.code_workspace))
        print(green('README.html generated in {}'.format(env.code_workspace)))

    if os.path.exists('{}/CHANGELOG.adoc'.format(env.code_workspace)):
        dk_run(service, user=env.local_userid,
               cmd='asciidoctor -d book -b html5 -o {}/CHANGELOG.html '
                   '{}/CHANGELOG.adoc'.format(env.code_workspace,
                                              env.code_workspace))
        print(green('CHANGELOG.html generated in {}'
                    ''.format(env.code_workspace)))


@task
def export_dump():
    """
    Import and restore the specified database dump.
    :param dump: a full path to a gzipped sql dump.
    """
    dump = '{}/build/{}.sql'.format(env.code_workspace, env.project_name)
    if os.path.exists(dump):
        local('rm {}'.format(dump))
    dk_run(env.services['php'], user=env.local_userid,
           cmd='drush sql-dump > {}'.format(dump))
    print(green('Database dump successfully exported.'))


@task
def import_dump(dump=False):
    """
    Import and restore the specified database dump.
    :param dump: name of sql dump inside build/.
    """
    if dump:
        dump = '{}/{}'.format(env.builddir, dump)
    else:
        dump = '{}/{}.sql'.format(env.builddir, env.project_name)
    if os.path.exists(dump):
        dump = '{}/build/{}.sql'.format(env.code_workspace, env.project_name)
        dk_run(env.services['php'], user=env.local_userid,
               cmd="drush sql-cli < {}".format(dump))
        print(green('Database dump successfully restored.'))
    else:
        print(red('Could not find database dump at {}'.format(dump)))


@task(alias='cex')
def config_export():
  """
  Export configurations in a config directory.
  """
  dk_run(env.services['php'], user=env.local_userid,
         cmd="drush config-export -y")
  print(green('Configurations exported.'))


@task(alias='cim')
def config_import():
  """
  Import configurations from a config directory.
  """
  dk_run(env.services['php'], user=env.local_userid,
         cmd="drush config-import -y")
  print(green('Configurations imported.'))
