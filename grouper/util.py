import logging

_TRUTHY = set([
    "true", "yes", "1", ""
])


def qp_to_bool(arg):
    return arg.lower() in _TRUTHY


def get_loglevel(args):
    verbose = args.verbose * 10
    quiet = args.quiet * 10
    return logging.getLogger().level - verbose + quiet


def try_update(dct, update):
    if set(update.keys()).intersection(set(dct.keys())):
        raise Exception("Updating {} with {} would clobber keys!".format(dct, update))
    dct.update(update)
