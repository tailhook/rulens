import argparse
from functools import partial

from . import nanomsg
from .db import Database


def serve_request(req, *, verbose=False, db):
    if verbose:
        print("rulens: Got request:", repr(req))
    _req, host, appname, topology, socktype = req.decode('ascii').split()
    assert _req == 'REQUEST', _req
    assert topology.startswith('topology://'), topology
    result = list(db.resolve(host, appname, topology, socktype))
    if verbose:
        print("rulens: Result:", ';'.join(result))
    return '\n'.join(result).encode('ascii')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+',
        help="Files to read topology from")
    ap.add_argument('-v', '--verbose',
        help='The file name to get topology from',
        default=False, action='store_true')
    ap.add_argument('-b', '--bind',
        help='The nanomsg address to bind to for name requests',
        required=True)

    options = ap.parse_args()

    db = Database()
    for i in options.files:
        db.add_from_file(i)
    nanomsg.reply_service(options.bind,
        partial(serve_request, verbose=options.verbose, db=db))


if __name__ == '__main__':
    main()

