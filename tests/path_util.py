import os


def src_path(*args):
    root = os.path.join(__file__, "..", "..")
    path = os.path.join(root, *args)
    return os.path.normpath(path)


def db_url(tmpdir):
    db_path = tmpdir.join("grouper.sqlite")
    return "sqlite:///{}".format(db_path)
