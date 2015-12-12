from ..settings import Settings, settings as base_settings


settings = Settings.from_settings(base_settings, {
    "debug": False,
    "port": 8990,
    "address": None,
    "refresh_interval": 60,
    "url": "http://127.0.0.1:8888",
})
