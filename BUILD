package(default_visibility = ['//visibility:public'])

load('/build_tools/bazel/py', 'dbx_py_bin', 'dbx_py_par', 'dbx_py_library')

dbx_py_bin(
    name = 'grouper-fe',
    main = 'bin/grouper-fe',
    deps = [
        ':grouper_lib',
        '//thirdparty:plop',
        '//thirdparty:pyflamegraph',
        '//thirdparty:raven',
    ],
    # NOTE(herb): this is to get around networkx including tests in its main package
    # which bazel filters by default
    py_excludes = [],
)

dbx_py_bin(
    name = 'grouper-api',
    main = 'bin/grouper-api',
    deps = [
        ':grouper_lib',
        '//thirdparty:plop',
        '//thirdparty:pyflamegraph',
        '//thirdparty:raven',
    ],
    # NOTE(herb): this is to get around networkx including tests in its main package
    # which bazel filters by default
    py_excludes = [],
)

dbx_py_par(
    name = 'grouper-ctl',
    main = 'bin/grouper-ctl',
    deps = [
        ':grouper_lib',
        '//thirdparty:ipython',
        '//thirdparty:mrproxy',
    ],
    # NOTE(herb): this is to get around networkx including tests in its main package
    # which bazel filters by default
    py_excludes = [],
)

dbx_py_library(
    name = 'grouper_lib',
    srcs = glob(["grouper/**/*.py"]),
    data = [
        ':template_files',
    ],
    deps = [
        '//thirdparty:annex',
        '//thirdparty:argparse',
        '//thirdparty:enum34',
        '//thirdparty:expvar',
        '//thirdparty:jinja2',
        '//thirdparty:mysql-python',
        '//thirdparty:markup-safe',
        '//thirdparty:networkx',
        '//thirdparty:python-dateutil',
        '//thirdparty:pytz',
        '//thirdparty:pyyaml',
        '//thirdparty:sqlalchemy',
        '//thirdparty:sshpubkey',
        '//thirdparty:ssl-match-hostname',
        '//thirdparty:tornado',
        '//thirdparty:wtforms',
        '//thirdparty:wtforms-tornado',
    ],
)

filegroup(
    name = 'template_files',
    srcs = glob([
        'grouper/fe/templates/**/*.html',
        'grouper/fe/templates/**/*.tmpl',
        'grouper/fe/static/favicon.ico',
        'grouper/fe/static/css/grouper.css',
        'grouper/fe/static/css/ext/**/*.css',
        'grouper/fe/static/js/*.js',
    ]),
)
