import logging
import pytest
import mock

@pytest.fixture(scope="session", autouse=True)
def default_session_fixture(request):
    """
    :type request: _pytest.python.SubRequest
    :return:
    """
    logging.info("Patching core.feature.service")
    patched = mock.patch('grouper.audit.get_auditors_group_name', return_value='auditors')
    patched.__enter__()

    def unpatch():
        patched.__exit__()
        logging.info("Patching complete. Unpatching")

    request.addfinalizer(unpatch)
