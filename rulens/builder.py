import random
from collections import defaultdict

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

    def instantiate(self, nodes, info=None):
        src = nodes[self.source]
        tgt = nodes[self.sink]
        ci = ConnectionInstance(self, src, tgt, **(info or {}))
        for n in src:
            n.add_source_connection(ci)
        for n in tgt:
            n.add_sink_connection(ci)

    def key(self):
        if self.bound == self.source:
            return "{} -> {}".format(self.source, self.sink)
        else:
            return "{} <- {}".format(self.sink, self.source)

    @staticmethod
    def canonical_key(key):
        a, arr, b = key.split()
        assert arr in ('<-', '->'), arr
        return '{} {} {}'.format(a, arr, b)



class ConnectionInstance(object):

    def __init__(self, info, sources, sinks, *,
        match_by=None, rules=(), default='all'):
        self.sources = sources
        self.sinks = sinks
        self.info = info
        self.match_by = match_by
        self.rules = rules
        self.default = default

    def _addr(self, nodes=None):
        info = self.info
        if info.addr:
            yield info.addr
            return
        if nodes is None:
            if info.bound == info.source:
                nodes = self.sources
            else:
                nodes = self.sinks
        for n in nodes:
            yield self._single_addr(n)

    def _single_addr(self, node):
        ip = None
        for r in node.rules:
            if 'ip' in r:
                ip = r['ip']
        port = self.info.port
        assert port, port
        return 'tcp://{}:{}'.format(ip, port)

    def address_for(self, node, props):
        info = self.info
        if node in self.sources:
            if info.bound == info.source:
                for a in self._addr([node]):
                    yield 'bind:{}:{}'.format(info.priority, a)
            else:
                if self.match_by:
                    sinks = []
                    myval = props[self.match_by]
                    for t in self.sinks:
                        for r in reversed(t.rules):
                            val = r.get(self.match_by)
                            if val is not None:
                                conn = '{} -> {}'.format(val, myval)
                                if conn in self.rules:
                                    sinks.append(t)
                                break
                    if not sinks:
                        if self.default == 'all':
                            sinks = self.sinks
                        else:
                            sinks = [random.choice(self.sinks)]
                else:
                    sinks = self.sinks
                for a in self._addr(sinks):
                    yield 'connect:{}:{}'.format(info.priority, a)
        elif node in self.sinks:
            if info.bound == info.sink:
                for a in self._addr([node]):
                    yield 'bind:8:{}'.format(a)
            else:
                if self.match_by:
                    sources = []
                    myval = props[self.match_by]
                    for t in self.sources:
                        for r in reversed(t.rules):
                            val = r.get(self.match_by)
                            if val is not None:
                                conn = '{} -> {}'.format(val, myval)
                                if conn in self.rules:
                                    sources.append(t)
                                break
                    if not sources:
                        if self.default == 'all':
                            sources = self.sources
                        else:
                            sources = [random.choice(self.sources)]
                else:
                    sources = self.sources
                for a in self._addr(sources):
                    yield 'connect:8:{}'.format(a)
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
        return '<Node {!r} {!r}>'.format(self.name, self.rules)


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
                cinfo = {Connection.canonical_key(k): v
                    for k, v in g.get('connections', {}).items()}
                for conn in l._connections:
                    conn.instantiate(groupnodes, cinfo.get(conn.key()))
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
