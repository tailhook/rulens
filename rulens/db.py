import sys
import yaml
import pprint

from .builder import TopologyBuilder


class Database(object):

    def __init__(self):
        self.topologies = {}

    def resolve(self, topology_uri, socket_type):
        raise NotImplementedError()

    def pretty_print(self):
        pprint.pprint(self.topologies)

    def add_from_file(self, filename):
        with open(filename, 'rt') as f:
            data = yaml.load(f)
        bld = TopologyBuilder(data)
        self.topologies.update(bld.topologies())


if __name__ == '__main__':
    db = Database()
    for i in sys.argv[1:]:
        db.add_from_file(i)
    db.pretty_print()
