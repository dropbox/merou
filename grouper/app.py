import tornado.web


class Application(tornado.web.Application):
    def __init__(self, *args, **kwargs):
        self.my_settings = kwargs.pop("my_settings", {})
        super(Application, self).__init__(*args, **kwargs)
