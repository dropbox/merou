import logging

import tornado.ioloop


def start_watchdog(name_thread_list, sentry_client, wake_frequency_ms):
    # type: (List[Tuple[str, Thread]], AsyncSentryClient, int, IOLoop) -> None
    """A IOLoop based watchdog for running threads. Should any one thread no
    longer be running, the watchdog will exit the ioloop.

    Args:
        name_thread_list: list of 2-tuple (name, Thread)
        sentry_client: sentry client, if available, to report failures
        wake_frequency_ms: frequency, in milliseconds, the watchdog should wake
                and check thread health
    """
    logging.info("thread watchdog initialization")

    def watchdog():
        logging.info("thread watchdog wake")
        for thread_name, thread_handle in name_thread_list:
            if not thread_handle.is_alive():
                # log death
                msg = "thread '{}' is dead. exiting.".format(thread_name)
                logging.error(msg)
                if sentry_client:
                    sentry_client.captureMessage(msg)

                # exit
                tornado.ioloop.IOLoop.instance().stop()

        logging.info("thread watchdog sleep")

    doggie = tornado.ioloop.PeriodicCallback(watchdog, wake_frequency_ms)
    doggie.start()
