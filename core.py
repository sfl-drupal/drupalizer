from __future__ import unicode_literals
from fabric.api import task, roles, env
from fabric.colors import red, green

import helpers as h

@task
@roles('docker')
def db_import(filename, role='docker'):
    """Import and restore the specified database dump.

    $ fab core.db_import:/tmp/db_dump.sql.gz

    :param filename: a full path to a gzipped sql dump.
    """

    if h.fab_exists(role, filename):
        print green('Database dump {} found.'.format(filename))
        h.fab_run(role, 'zcat {} | mysql -u{} -p{} {}'.format(filename, env.site_db_user, env.site_db_pass, env.site_db_name))
        print green('Database dump successfully restored.')
    else:
        print red('Could not find database dump at {}'.format(filename))
