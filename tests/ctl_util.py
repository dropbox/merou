from mock import patch

from grouper.ctl.main import main


def call_main(*args):
    argv = ['grouper-ctl'] + list(args)
    with patch('grouper.ctl.main.load_plugins'):
        return main(sys_argv=argv, start_config_thread=False)
