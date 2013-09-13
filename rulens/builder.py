from collections import defaultdict

from .topology import Topology


class Connection(object):

    def __init__(self, source, sink, bound, *,
        port=None, priority=8, addr=None, skip_ourself=None):
        self.port = port
        self.addr = addr
        self.piority = priority
        self.skip_ourself = skip_ourself
        assert not (port and addr), "Either port or addr may only be specified"


class Layout(object):

    def __init__(self, data):
        self._by_source = defaultdict(list)
        self._by_sink = defaultdict(list)
        self._by_bound = defaultdict(list)
        self._parse_data(data)

    def _parse_data(self, data):
        for connection, properties in data.items():
            try:
                source, sink = connection.split('->')
                bound = source
            except ValueError:
                try:
                    sink, source = connection.split('<-')
                    bound = sink
                except ValueError:
                    raise ValueError("Wrong connection definition {!r}"
                        .format(connection))
            conn = Connection(source, sink, bound, **(properties or {}))
            self._by_source[source].append(conn)
            self._by_sink[sink].append(conn)
            self._by_bound[bound].append(conn)


class LayoutInstance(object):

    def __init__(self, bld, layout, group):
        self._populate(bld, layout, group)

    def _populate(self, builder, layout, group):
        rule = group['rule']
        for i in children:



class TopologyBuilder(object):

    def __init__(self, data):
        self._layouts = {name: Layout(val)
            for name, val in data['layouts'].items()}
        self._groups = data['groups']
        self._topologies = data['topologies']

    def _populate_topology(self, top, layout=None, children=None,
                                 topology=None, slot=None):
        assert not(layout and topology), \
            "Either layout or topology should be specified"
        if layout:
            if children:
                nodes = []
                for i in children:
                    g = self._groups[i]
                    l = self._layouts[g['layout']]
                    nodes.append(LayoutInstance(self, l, g))



    def topologies(self):
        for name, properties in self._topologies.items():
            top = Topology(name)
            self._populate_topology(top, **properties)
            yield name, top
