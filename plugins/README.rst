This directory contains various sample plugins and plugins used by the
test suite.  It will be included in distributions of Grouper, but the test
plugins are not enabled by default in ``dev.yaml``.

Plugins starting with ``test_`` are required by the integration test suite
and hard-code various group names and permission values that are unlikely
to match a production configuration.  They may be useful as examples for
writing one's own plugins, but should not be enabled as-is outside of
tests and local development.

Plugins not starting with ``test_`` enforce some meaningful but optional
policies and are suitable for enabling as-is in a production deployment if
you agree with those policies.
