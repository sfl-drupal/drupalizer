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
from fabric.decorators import task

from fabfile.core import *


@task
def init(rw=True):
    """
    Check installation and configure Behat.
    :param rw If the behat.yml file should be rewrited or not.
    """
    service = env.services['php']
    workspace = env.code_workspace
    host = env.services['web_server']
    site_root = env.code_site_root

    if not os.path.exists('{}/tests/behat/behat.yml'.format(workspace)) or rw:
        dk_run(service, cmd='cd {}/tests/behat && cp example.behat.yml '
                            'behat.yml'.format(workspace))
        dk_run(service, cmd="cd {}/tests/behat && sed -i 's@%DRUPAL_ROOT@{"
                            "}@g' behat.yml".format(workspace, site_root))
        dk_run(service, cmd="cd {}/tests/behat && sed -i 's@%URL@http://{"
                            "}@g' behat.yml".format(workspace, host))
        print(green('Behat is now properly configured. The configuration '
                    'file is {}/tests/behat/behat.yml'.format(workspace)))
    else:
        print(green('{}/tests/behat/behat.yml is already created.'
                    ''.format(workspace)))


@task
def install():
    """
    Install behat
    """
    service = env.services['php']
    workspace = env.code_workspace

    if not os.path.exists('{}/tests/behat/bin/behat'.format(env.workspace)):
        dk_run(service, user='root',
               cmd='chown -R {}:{} ../../tests'.format(env.apache_userid,
                                                       env.local_userid))
        dk_run(
            service,
            cmd='cd {}/tests/behat && composer install'.format(workspace))
        print(green('Behat has been properly installed with Composer in '
                    '{}/tests/behat/bin/behat'.format(workspace)))
    else:
        print(green('Behat is already installed!'))


@task
def run(pattern='~@wip&&~@disabled&&~@test'):
    """
    Execute the complete Behat tests suite.
    :param pattern: The tags to filter the tests
    """
    service = env.services['php']
    workspace = env.code_workspace

    dk_run(service, 'mkdir -p {}/logs/behat'.format(workspace))
    if not os.path.exists('../tests/behat/bin/behat'):
        install()
    if not os.path.exists('{}/tests/behat/behat.yml'.format(workspace)):
        init()
    dk_run(
        service,
        r'cd {}/tests/behat && bin/behat --format junit --format pretty '
        r'--tags \"{}\" --colors'.format(workspace, pattern)
    )
