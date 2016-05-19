from __future__ import unicode_literals
from fabric.api import task, roles, env
from fabric.colors import green

import helpers as h

@task
@roles('local')
def build():
    """
    Generate the PatternLab static site
    """
    role = 'local'
    workspace = env.docker_workspace
    host = env.site_hostname
    site_root = env.docker_site_root
    
    with h.fab_cd(role, env.patternlab_dir):
        h.fab_run(role, 'touch public/styleguide/html/styleguide.html')
        h.fab_run(role, 'php core/builder.php -g')

    
