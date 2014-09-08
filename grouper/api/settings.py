from ..settings import Settings, settings as base_settings


settings = Settings.from_settings(base_settings, {
    "debug": False,
    "port": 8990,
    "refresh_interval": 60,
})
