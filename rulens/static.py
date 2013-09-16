"""
    The command-line interface for static-checking of topology db
"""
import argparse

from .db import Database


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('topology_files', nargs='+',
        help="Files to read topology from")
    ap.add_argument('-l', '--list-file', default=[], action="append",
        help="The text file with list of name requests to run tests against")
    ap.add_argument('-g', '--basic-graph', action="store_true",
        help="Draw bare diagram from topopology file")
    ap.add_argument('-G', '--instance-graph', action="store_true",
        help="Draw diagram of nodes read from --list-file")
    ap.add_argument('-p', '--print-addresses', action="store_true",
        help="Print addresses resolved for each --list-file")
    options = ap.parse_args()


    db = Database()
    for i in options.topology_files:
        db.add_from_file(i)

    if options.print_addresses:
        for fn in options.list_file:
            with open(fn, 'rt') as file:
                for line in file:
                    line = line.strip()
                    if line.startswith('#'):  # comment
                        continue
                    url, socktype = line.split()
                    print(url, socktype)
                    for addr in db.resolve(None, None, url, socktype):
                        print('   ', addr)

    if options.basic_graph:
        pass
    if options.instance_graph:
        pass


if __name__ == '__main__':
    main()
