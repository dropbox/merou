package(default_visibility = ['//visibility:public'])

#load('//build_tools/bazel/py', 'dbx_py_pypi_piplib')
#load('//build_tools/bazel/py', 'dbx_py_pypi_piplib')

dbx_py_pypi_piplib(
    name = 'annex',
    pip_req = 'annex==0.3.1',
)

dbx_py_pypi_piplib(
    name = 'jinja2',
    pip_req = 'Jinja2==2.7.3',
    deps = [
        '//pip/setuptools',
    ],
)

dbx_py_pypi_piplib(
    name = 'mysql-python',
    deps = [
        '//dpkg:libmysqlclient',
        '//dpkg:usr/bin/mysql_config',
    ],
    pip_req = 'MySQL-python==1.2.5',
    env = {
        'MYSQL_CONFIG': '$(ROOT)/$(location //dpkg:usr/bin/mysql_config)',
    },
)

dbx_py_pypi_piplib(
    name = 'markup-safe',
    pip_req = 'MarkupSafe==0.23',
)

dbx_py_pypi_piplib(
    name = 'pyyaml',
    pip_req = 'PyYAML==3.10',
)

dbx_py_pypi_piplib(
    name = 'sqlalchemy',
    pip_req = 'SQLAlchemy==0.9.1',
    deps = [
        '//pip/setuptools',
    ],
)

dbx_py_pypi_piplib(
    name = 'wtforms',
    pip_req = 'WTForms==2.0.1',
)

dbx_py_pypi_piplib(
    name = 'argparse',
    pip_req = 'argparse==1.2.1',
)

dbx_py_pypi_piplib(
    name = 'backports.ssl_match_hostname',
    pip_req = 'backports.ssl_match_hostname==3.4.0.2',
)

dbx_py_pypi_piplib(
    name = 'enum34',
    pip_req = 'enum34==1.0.4',
)

dbx_py_pypi_piplib(
    name = 'expvar',
    pip_req = 'expvar==0.0.2',
)

dbx_py_pypi_piplib(
    name = 'networkx',
    pip_req = 'networkx==1.8.1',
    # NOTE(herb): this is to get around networkx including tests in its main package
    # which bazel filters by default
    py_excludes = [],
)

dbx_py_pypi_piplib(
    name = 'plop',
    pip_req = 'plop==0.3.0',
)

dbx_py_pypi_piplib(
    name = 'pyflamegraph',
    pip_req = 'pyflamegraph==0.0.2',
)

dbx_py_pypi_piplib(
    name = 'python-dateutil',
    pip_req = 'python-dateutil==2.4.2',
    deps = [
        ':six',
    ],
)

dbx_py_pypi_piplib(
    name = 'pytz',
    pip_req = 'pytz==2014.2',
    deps = [
        '//pip/setuptools',
    ],
)

dbx_py_pypi_piplib(
    name = 'six',
    pip_req = 'six==1.10.0',
)

dbx_py_pypi_piplib(
    name = 'tornado',
    pip_req = 'tornado==3.2',
)

dbx_py_pypi_piplib(
    name = 'wtforms-tornado',
    pip_req = 'wtforms-tornado==0.0.1',
)

dbx_py_pypi_piplib(
    name = 'mrproxy',
    pip_req = 'mrproxy==0.3.2',
)

dbx_py_pypi_piplib(
    name = 'raven',
    pip_req = 'raven==5.27.1',
    deps = [
        '//pip/setuptools',
    ],
)

dbx_py_pypi_piplib(
    name = 'Crypto',
    pip_req = 'pycrypto==2.6.1',
)

dbx_py_pypi_piplib(
    name = 'ecdsa',
    pip_req = 'ecdsa==0.13',
    deps = [':six'],
)

dbx_py_pypi_piplib(
  deps = ['//pip/setuptools'],
  name = 'typing',
  pip_req = 'typing==3.5.2.2',
)

dbx_py_pypi_piplib(
    name = 'sshpubkeys',
    pip_req = 'sshpubkeys==2.2.0',
    deps = [':Crypto', ':ecdsa'],
)

dbx_py_pypi_piplib(
    name = 'ipython',
    pip_req = 'ipython==3.2.1',
    # NOTE(herb): this is to get around ipython including a package called
    # 'testing' (specifically 'testing.skipdoctest' when importing 'embed')
    # which bazel filters by default
    py_excludes = [],
)
