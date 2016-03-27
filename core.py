from __future__ import unicode_literals
from fabric.api import lcd, cd, task, roles, env, local, run, runs_once, execute
from fabric.contrib.console import confirm
from fabric.colors import red, green

import helpers as h
import os.path

@task
@roles('docker')
def db_import(filename=env.db_dump, role='docker'):
    """Import and restore the specified database dump.

    $ fab core.db_import:/tmp/db_dump.sql.gz

    :param filename: a full path to a gzipped sql dump.
    """

    if os.path.isfile(filename):
        print green('Database dump {} found.'.format(filename))
        with h.fab_cd(role, env.site_root):
            h.fab_run(role, 'zcat {} | mysql -u{} -p{} -h{} {}'.format(filename, env.site_db_user, env.site_db_pass, env.container_ip, env.site_db_name))
            print(green('Database dump successfully restored.'))
    else:
        print red('Could not find database dump at {}'.format(filename))
