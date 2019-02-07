import tornado.web
from tornado.log import access_log


class Application(tornado.web.Application):
    def __init__(self, *args, **kwargs):
        self.my_settings = kwargs.pop("my_settings", {})
        self.sentry_client = kwargs.pop("sentry_client", None)
        super(Application, self).__init__(*args, **kwargs)

    def log_request(self, handler):
        if handler.get_status() < 400:
            log_method = access_log.info
        elif handler.get_status() < 500:
            log_method = access_log.warning
        else:
            log_method = access_log.error

        # we want to reduce priority of health check request
        if handler.request.uri == "/debug/stats":
            log_method = access_log.debug

        user = handler.get_current_user()
        if user:
            username = user.username
        else:
            username = "-"

        request_time = 1000.0 * handler.request.request_time()

        log_method(
            "{} {} {} {:.2f}ms".format(
                username, handler.get_status(), handler._request_summary(), request_time
            )
        )
