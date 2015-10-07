package(default_visibility = ['//visibility:public'])

load('/build_tools/bazel/pip', 'py_pip', 'py_pip_bin', 'py_pip_par')

#py_pip_par(
#    name = 'grouper-fe.par',
#    main = 'bin/grouper-fe',
#    deps = [
#        ':grouper_lib',
#    ],
#)

py_pip_par(
    name = 'grouper-ctl',
    main = 'bin/grouper-ctl',
    deps = [
        ':grouper_lib',
        ':mrproxy',
    ],
)

py_library(
    name = 'grouper_lib',
    srcs = glob(["grouper/**/*.py"]),
    data = [
        ':annex',
        ':jinja2',
        ':mysql-python',
        ':markup-safe',
        ':pyyaml',
        ':sqlalchemy',
        ':wtforms',
        ':argparse',
        ':ssl-match-hostname',
        ':bittle',
        ':expvar',
        ':networkx',
        ':python-dateutil',
        ':pytz',
        ':sshpubkey',
        ':tornado',
        ':wsgiref',
        ':wtforms-tornado',
        ':template_files',
    ],
)

py_library(
    name = 'dropbox_lib',
    srcs = glob([
         'dropbox/*.py',
         'dropbox/**/*.py',
    ]),
)

filegroup(
    name = 'template_files',
    srcs = glob([
        'gropuer/fe/templates/*.html',
        'grouper/fe/templates/**/*.html',
        'grouper/fe/static/favicon.ico',
        'grouper/fe/static/css/grouper.css',
        'grouper/fe/static/css/ext/**/*.css',
        'grouper/fe/static/js/*.js',
    ]),
)

py_pip(
    name = 'annex',
    pip_deps = ['annex==0.3.1'],
)

py_pip(
    name = 'jinja2',
    pip_deps = ['Jinja2==2.7.3'],
)

py_pip(
    name = 'mysql-python',
    pip_deps = ['MySQL-python==1.2.5'],
)

py_pip(
    name = 'markup-safe',
    pip_deps = ['MarkupSafe==0.23'],
)

py_pip(
    name = 'pyyaml',
    pip_deps = ['PyYAML==3.10'],
)

py_pip(
    name = 'sqlalchemy',
    pip_deps = ['SQLAlchemy==0.9.1'],
)

py_pip(
    name = 'wtforms',
    pip_deps = ['WTForms==2.0.1'],
)

py_pip(
    name = 'argparse',
    pip_deps = ['argparse==1.2.1'],
)

py_pip(
    name = 'ssl-match-hostname',
    pip_deps = ['backports.ssl-match-hostname==3.4.0.2'],
)

py_pip(
    name = 'bittle',
    pip_deps = ['bittle==0.2.1'],
)

py_pip(
    name = 'expvar',
    pip_deps = ['expvar==0.0.2'],
)

py_pip(
    name = 'networkx',
    pip_deps = ['networkx==1.8.1'],
)

py_pip(
    name = 'plop',
    pip_deps = ['plop==0.3.0'],
)

py_pip(
    name = 'pyflamegraph',
    pip_deps = ['pyflamegraph==0.0.2'],
)

py_pip(
    name = 'python-dateutil',
    pip_deps = ['python-dateutil==2.4.2'],
)

py_pip(
    name = 'pytz',
    pip_deps = ['pytz==2014.2'],
)

py_pip(
    name = 'sshpubkey',
    pip_deps = ['sshpubkey==0.1.2'],
)

py_pip(
    name = 'tornado',
    pip_deps = ['tornado==3.2'],
)

py_pip(
    name = 'wsgiref',
    pip_deps = ['wsgiref==0.1.2'],
)

py_pip(
    name = 'wtforms-tornado',
    pip_deps = ['wtforms-tornado==0.0.1'],
)

py_pip(
    name = 'mrproxy',
    pip_deps = ['mrproxy==0.3.2'],
)
