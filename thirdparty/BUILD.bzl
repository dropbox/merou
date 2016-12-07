package(default_visibility = ['//visibility:public'])

#load('//build_tools/bazel/py', 'dbx_py_pypi_piplib')
#load('//build_tools/bazel/py', 'dbx_py_pypi_piplib')

dbx_py_pypi_piplib(
    name = 'annex',
    pip_deps = ['annex==0.3.1'],
)

dbx_py_pypi_piplib(
    name = 'jinja2',
    pip_deps = ['Jinja2==2.7.3'],
    deps = [
        '//pip/setuptools',
    ],
)

dbx_py_pypi_piplib(
    name = 'mysql-python',
    pip_deps = ['MySQL-python==1.2.5'],
)

dbx_py_pypi_piplib(
    name = 'markup-safe',
    pip_deps = ['MarkupSafe==0.23'],
)

dbx_py_pypi_piplib(
    name = 'pyyaml',
    pip_deps = ['PyYAML==3.10'],
)

dbx_py_pypi_piplib(
    name = 'sqlalchemy',
    pip_deps = ['SQLAlchemy==0.9.1'],
    deps = [
        '//pip/setuptools',
    ],
)

dbx_py_pypi_piplib(
    name = 'wtforms',
    pip_deps = ['WTForms==2.0.1'],
)

dbx_py_pypi_piplib(
    name = 'argparse',
    pip_deps = ['argparse==1.2.1'],
)

dbx_py_pypi_piplib(
    name = 'ssl-match-hostname',
    pip_deps = ['backports.ssl-match-hostname==3.4.0.2'],
)

dbx_py_pypi_piplib(
    name = 'enum34',
    pip_deps = ['enum34==1.0.4'],
)

dbx_py_pypi_piplib(
    name = 'expvar',
    pip_deps = ['expvar==0.0.2'],
)

dbx_py_pypi_piplib(
    name = 'networkx',
    pip_deps = ['networkx==1.8.1'],
    # NOTE(herb): this is to get around networkx including tests in its main package
    # which bazel filters by default
    py_excludes = [],
)

dbx_py_pypi_piplib(
    name = 'plop',
    pip_deps = ['plop==0.3.0'],
)

dbx_py_pypi_piplib(
    name = 'pyflamegraph',
    pip_deps = ['pyflamegraph==0.0.2'],
)

dbx_py_pypi_piplib(
    name = 'python-dateutil',
    pip_deps = ['python-dateutil==2.4.2'],
    deps = [
        ':six',
    ],
)

dbx_py_pypi_piplib(
    name = 'pytz',
    pip_deps = ['pytz==2014.2'],
    deps = [
        '//pip/setuptools',
    ],
)

dbx_py_pypi_piplib(
    name = 'six',
    pip_deps = ['six==1.10.0'],
)

dbx_py_pypi_piplib(
    name = 'sshpubkey',
    pip_deps = ['sshpubkey==0.1.2'],
)

dbx_py_pypi_piplib(
    name = 'tornado',
    pip_deps = ['tornado==3.2'],
)

dbx_py_pypi_piplib(
    name = 'wtforms-tornado',
    pip_deps = ['wtforms-tornado==0.0.1'],
)

dbx_py_pypi_piplib(
    name = 'mrproxy',
    pip_deps = ['mrproxy==0.3.2'],
)

dbx_py_pypi_piplib(
    name = 'raven',
    pip_deps = ['raven==5.27.1'],
    deps = [
        '//pip/setuptools',
    ],
)

dbx_py_pypi_piplib(
    name = 'ipython',
    pip_deps = ['ipython==3.2.1'],
    # NOTE(herb): this is to get around ipython including a package called
    # 'testing' (specifically 'testing.skipdoctest' when importing 'embed')
    # which bazel filters by default
    py_excludes = [],
)
