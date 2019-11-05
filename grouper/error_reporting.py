from __future__ import print_function

import logging
import signal
import sys
import traceback
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import FrameType


signame_by_signum = {
    v: k for k, v in signal.__dict__.items() if k.startswith("SIG") and not k.startswith("SIG_")
}


def log_and_exit_handler(signum, frame):
    # type: (int, FrameType) -> None
    logging.warning("caught signal {}, exiting".format(signame_by_signum[signum]))
    sys.exit(1)


def dump_thread_handler(signum, frame):
    # type: (int, FrameType) -> None
    for thread_id, thread_frame in sys._current_frames().items():
        print("-- thread id {}:".format(thread_id))
        print("".join(traceback.format_stack(thread_frame)))


def setup_signal_handlers():
    # type: () -> None
    """Setup the handlers for API and FE servers. Specifically we message on
    any signal and we dump thread tracebacks on SIGUSR1."""
    for signum in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(signum, log_and_exit_handler)

    signal.signal(signal.SIGUSR1, dump_thread_handler)
