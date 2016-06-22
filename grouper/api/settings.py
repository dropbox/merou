from ..settings import Settings, settings as base_settings


settings = Settings.from_settings(base_settings, {
    "address": None,
    "debug": False,
    "port": 8990,
    "refresh_interval": 60,
    "url": "http://127.0.0.1:8888",
    "watchdog_wake_frequency_ms": 5000,
})
