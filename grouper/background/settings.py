from ..settings import Settings, settings as base_settings


settings = Settings.from_settings(base_settings, {"sleep_interval": 60})
