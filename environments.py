from importlib import import_module

from fabric.utils import abort

def e(name):
    """
    Set your environment before running other commands
    """
    try:
        import_module('.settings.%s' % name, 'fabfile')
    except ImportError:
        abort('Environment settings not found for "%s", you must create a file at `settings/%s.py` and add your environment settings to it to use it' % (name, name))
