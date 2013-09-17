import yaml
import pprint
import argparse
from urllib.parse import urlparse, parse_qsl

from .builder import TopologyBuilder


class Database(object):

    def __init__(self):
        self.topologies = {}

    def resolve(self, host, appname, topology_url, socktype):
        url = urlparse(topology_url)
        topology = self.topologies[url.netloc]
        params = dict(parse_qsl(url.query))
        params.update(dict(host=host, appname=appname))
        node, party = topology.resolve_node(params['role'], socktype, params)
        for conn in node.connections[party]:
            yield from conn.address_for(node, params)

    def get_group(self, host, appname, topology_url, socktype):
        """Finds a group by parameters, primarily for graph building"""
        url = urlparse(topology_url)
        topology = self.topologies[url.netloc]
        params = dict(parse_qsl(url.query))
        params.update(dict(host=host, appname=appname))
        node, party = topology.resolve_node(params['role'], socktype, params)
        return node.group

    def pretty_print(self):
        for top in self.topologies.values():
            print('--', top.name, '--')
            pprint.pprint(top.__dict__)

    def add_from_file(self, filename):
        with open(filename, 'rt') as f:
            data = yaml.load(f)
        self.groups = data['groups']
        bld = TopologyBuilder(data)
        self.topologies.update(bld.topologies())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+',
        help="Files to read topology from")
    ap.add_argument('--print-db', action='store_true', default=False,
        help="Print whole database and exit")
    ap.add_argument('--query', nargs=4,
        metavar=('HOST', 'APPNAME',  'TOPOLOGY', 'SOCKTYPE'),
        help="Query database and exit")
    options = ap.parse_args()

    db = Database()
    for i in options.files:
        db.add_from_file(i)

    if options.print_db:
        db.pretty_print()
    elif options.query:
        db.resolve(*options.query)



if __name__ == '__main__':
    main()
