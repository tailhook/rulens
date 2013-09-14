from collections import defaultdict
import pprint

from .topology import Topology


class Connection(object):

    def __init__(self, source, sink, bound, *,
        port=None, priority=8, addr=None, skip_ourself=None):
        self.source = source
        self.sink = sink
        self.bound = bound
        self.port = port
        self.addr = addr
        self.priority = priority
        self.skip_ourself = skip_ourself
        self.addresses = []
        assert not (port and addr), "Either port or addr may only be specified"

    def instantiate(self, nodes):
        src = nodes[self.source]
        tgt = nodes[self.sink]
        ci = ConnectionInstance(self, src, tgt)
        for n in src:
            n.add_source_connection(ci)
        for n in tgt:
            n.add_sink_connection(ci)


class ConnectionInstance(object):

    def __init__(self, info, sources, sinks):
        self.sources = sources
        self.sinks = sinks
        self.info = info

    def _addr(self, node=None):
        info = self.info
        if info.addr:
            return info.addr
        if node is None:
            if info.bound == info.source:
                nn = self.sources
            else:
                nn = self.sinks
            assert len(nn) == 1, nn
            node = nn[0]
        ip = None
        for r in node.rules:
            if 'ip' in r:
                ip = r['ip']
        port = info.port
        assert port, port
        return 'tcp://{}:{}'.format(ip, port)

    def address_for(self, node):
        info = self.info
        if node in self.sources:
            if info.bound == info.source:
                return 'bind:{}:{}'.format(info.priority, self._addr(node))
            else:
                return 'connect:{}:{}'.format(info.priority, self._addr())
        elif node in self.sinks:
            if info.bound == info.sink:
                return 'bind:8:{}'.format(self._addr(node))
            else:
                return 'connect:8:{}'.format(self._addr())
        else:
            raise RuntimeError("Wrong node")


class Layout(object):

    def __init__(self, data):
        self._by_source = defaultdict(list)
        self._by_sink = defaultdict(list)
        self._by_bind = defaultdict(list)
        self._roles = set()
        self._connections = []
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
            source = source.strip()
            sink = sink.strip()
            bound = bound.strip()
            conn = Connection(source, sink, bound, **(properties or {}))
            self._by_source[source].append(conn)
            self._by_sink[sink].append(conn)
            self._by_bind[bound].append(conn)
            self._roles.add(source)
            self._roles.add(sink)
            self._connections.append(conn)


class BindAddress(object):

    def __init__(self, conn, rule):
        self.conn = conn
        self.rule = rule
        self.ip = self.rule.get('ip', '?')
        self.port = conn.port or '?'

    def __repr__(self):
        return '<BindAddress {}:{}>'.format(self.ip, self.port)


class ConnectAddress(object):

    def __init__(self, conn, rule):
        pass


class Node(object):

    def __init__(self, name, matched_by_rules=()):
        self.name = name
        self.rules = tuple(matched_by_rules)
        self.connections = {
            'source': [],
            'sink': [],
            }

    @classmethod
    def supernode(Node, name, nodes):
        self = Node(name, [])
        return self

    def add_source_connection(self, conn):
        self.connections['source'].append(conn)

    def add_sink_connection(self, conn):
        self.connections['sink'].append(conn)

    def __repr__(self):
        return '<Node {}>'.format(self.rules)


class TopologyBuilder(object):

    def __init__(self, data):
        self._layouts = {name: Layout(val)
            for name, val in data['layouts'].items()}
        self._groups = data['groups']
        self._topologies = data['topologies']

    def _populate_topology(self, top, layout=None, children=None,
                                 topology=None, slot=None):
        assert bool(layout) != bool(topology), \
            "Either layout or topology should be specified"

        if layout:
            assert children
            nodes = defaultdict(list)
            for i in children:
                g = self._groups[i]
                l = self._layouts[g['layout']]
                groupnodes = self._process_group(g, l)
                for conn in l._connections:
                    conn.instantiate(groupnodes)
                for role, nlist in groupnodes.items():
                    if role.startswith('_'):
                        name = role[1:]
                        nodes[name].append(Node.supernode(name, nlist))
                    else:
                        nodes[role].extend(nlist)
            l = self._layouts[layout]
            for conn in l._connections:
                conn.instantiate(nodes)
            for role, nlist in nodes.items():
                for node in nlist:
                    top.add_rule(role, node)

        if topology:
            pass



    def _process_group(self, group, layout):
        global_rule = group['rule']
        by_role = defaultdict(list)
        for role, rules in group['children'].items():
            for rule in rules:
                node = Node(role, [global_rule, rule])
                by_role[node.name].append(node)

        for ep in layout._roles:
            if not ep in by_role:
                node = Node(ep, [global_rule])
                by_role[node.name].append(node)
        return by_role


    def topologies(self):
        for name, properties in self._topologies.items():
            top = Topology(name, properties.pop('type'))
            self._populate_topology(top, **properties)
            yield name, top
