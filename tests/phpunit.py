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

from ..core import *


@task
def init():
    """
    Setting up the PHPUnit config file.
    """
    service = env.services['php']
    db_user = env.site_db_user
    db_pass = env.site_db_pass
    db_host = env.site_db_host
    db_name = env.site_db_name
    base_url = 'localhost'

    dk_run(service, user=env.local_userid,
           cmd='cp core/phpunit.xml.dist core/phpunit.xml')
    dk_run(
        service, user=env.local_userid,
        cmd=r"sed -i 's@<env name=\"SIMPLETEST_BASE_URL\" value=\"\"/>@"
            r"<env name=\"SIMPLETEST_BASE_URL\" value=\"http://{}\"/>@g' "
            r"core/phpunit.xml".format(base_url)
    )
    dk_run(
        service, user=env.local_userid,
        cmd=r"sed -i 's@<env name=\"SIMPLETEST_DB\" value=\"\"/>@"
            r"<env name=\"SIMPLETEST_DB\" value=\"mysql://{}:{}\@{}/{}\"/>@g' "
            r"core/phpunit.xml".format(db_user, db_pass, db_host, db_name)
    )
    dk_run(
        service, user=env.local_userid,
        cmd=r"sed -i 's@<env name=\"BROWSERTEST_OUTPUT_DIRECTORY\" "
            r"value=\"\"/>@<env name=\"BROWSERTEST_OUTPUT_DIRECTORY\" "
            r"value=\"/tmp\"/>@g' core/phpunit.xml"
    )


@task
def install():
    """
    Install phpunit
    """
    service = env.services['php']
    workspace = '{}/{}'.format(env.workspace, env.site_root)

    if not os.path.exists('{}/vendor/bin/phpunit'.format(workspace)):
        if env.drupal_version == 8:
            dk_run(service, cmd='composer install')
            init()
        print(green('PHPUnit has been properly installed with Composer in '
                    '{}/vendor/bin/phpunit'.format(workspace)))
    else:
        dk_run(service, user='root', cmd='chmod +x vendor/bin/phpunit')
        print(green('PHPUnit is already installed!'))


@task
def run(pattern='unit'):
    """
    Execute the complete PHPUnit tests suite.
    :param pattern: Test suite to run.
    """
    service = env.services['php']

    install()
    init()
    dk_run(
        service,
        user=env.local_userid,
        cmd='cd core && ../vendor/bin/phpunit --testsuite={}'.format(pattern)
    )
