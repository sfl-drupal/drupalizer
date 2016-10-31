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
from importlib import import_module
from fabric.api import task, execute

from fabfile.core import *


@task
def init(rw=True):
    """
    Initialize tests engines.
    :param rw If the config file should be rewrited or not.
    """
    modules = map(__import__, env.test_engines)
    for test_mod in modules:
        execute(test_mod.init, rw=rw)


@task
def install():
    """
    Install tests engines
    """
    modules = map(__import__, env.test_engines)
    for test_mod in modules:
        execute(test_mod.install)


@task
def run(pattern=''):
    """
    Execute the complete tests suite.
    :param pattern: Filter the tests using this pattern.
    """
    modules = map(import_module, env.test_engines)
    for test_mod in modules:
        if pattern:
            execute(test_mod.run, pattern=pattern)
        else:
            execute(test_mod.run)
