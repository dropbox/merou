from unittest import mock
from unittest.mock import patch

from grouper.initialization import create_graph_usecase_factory


@patch("grouper.settings.Settings")
@patch("grouper.plugin.proxy.PluginProxy")
@patch("sqlalchemy.orm.Session")
def test_session_closing_successful(session, plugin_proxy, settings):
    with mock.patch.object(session, "close") as session_closed:
        with create_graph_usecase_factory(settings, plugin_proxy) as use_case_factory:
            # swap with mocked session
            use_case_factory.service_factory.repository_factory._session = session

        session_closed.assert_called()


@patch("grouper.settings.Settings")
@patch("grouper.plugin.proxy.PluginProxy")
@patch("sqlalchemy.orm.Session")
def test_session_closing_failed(session, plugin_proxy, settings):
    with mock.patch.object(session, "close") as session_closed:
        with create_graph_usecase_factory(settings, plugin_proxy) as use_case_factory:
            # null out dependency, force exception, graceful handling expected
            use_case_factory.service_factory.repository_factory = None

        session_closed.assert_not_called()


@patch("grouper.plugin.proxy.PluginProxy")
def test_same_db_url_same_engine_used(plugin_proxy):
    with mock.patch("grouper.settings.Settings") as settings:
        settings.database = "some db url"
        with mock.patch("grouper.models.base.session.get_db_engine"):
            old_use_case_factory = create_graph_usecase_factory(settings, plugin_proxy)
            old_engine_id = id(
                old_use_case_factory.service_factory.repository_factory.session.bind
            )

        with mock.patch("grouper.models.base.session.get_db_engine"):
            new_use_case_factory = create_graph_usecase_factory(settings, plugin_proxy)
            new_engine_id = id(
                new_use_case_factory.service_factory.repository_factory.session.bind
            )

    assert old_engine_id == new_engine_id


@patch("grouper.plugin.proxy.PluginProxy")
def test_diff_db_url_diff_engine_used(plugin_proxy):
    with mock.patch("grouper.settings.Settings") as settings:
        settings.database = "some db url"
        with mock.patch("grouper.models.base.session.get_db_engine"):
            old_use_case_factory = create_graph_usecase_factory(settings, plugin_proxy)
            old_engine_id = id(
                old_use_case_factory.service_factory.repository_factory.session.bind
            )

    with mock.patch("grouper.settings.Settings") as settings:
        settings.database = "some other db url"
        with mock.patch("grouper.models.base.session.get_db_engine"):
            new_use_case_factory = create_graph_usecase_factory(settings, plugin_proxy)
            new_engine_id = id(
                new_use_case_factory.service_factory.repository_factory.session.bind
            )

    assert old_engine_id != new_engine_id
