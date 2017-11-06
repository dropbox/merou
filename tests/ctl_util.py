from mock import patch

from grouper.ctl.main import main


def call_main(*args):
    argv = ['grouper-ctl'] + list(args)
    return main(sys_argv=argv, start_config_thread=False)
