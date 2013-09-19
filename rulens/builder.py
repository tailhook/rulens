import random
from collections import defaultdict
from itertools import groupby

from .topology import Topology, ExternTopology


class Connection(object):

    def __init__(self, source, sink, bound, *,
        port=None, priority=8, addr=None, skip_same=None,
        ports=None, match_by=None):
        self.source = source
        self.sink = sink
        self.bound = bound
        self.port = port
        self.ports = ports
        self.match_by = match_by
        self.addr = addr
        self.priority = priority
        self.skip_same = skip_same
        self.addresses = []
        assert not (port and addr), "Either port or addr may only be specified"

    def __repr__(self):
        return '<{} {}>'.format(self.__class__.__name__, self.key())

    @property
    def abstract(self):
        return self.source.startswith('_') or self.sink.startswith('_')

    def instantiate(self, nodes, info=None):
        rawsrc = nodes[self.source]
        rawtgt = nodes[self.sink]

        src = set()
        for n in rawsrc:
            if hasattr(n, 'children'):
                for ch in n.children:
                    for conn in ch.connections['sink']:
                        rawsrc.extend(conn.sources)
                        if conn.info.port is not None:
                            if self.port is not None:
                                assert self.port == conn.info.port, \
                                    (self.port, conn.info.port)
                            else:
                                self.port = conn.info.port
                        if conn.info.ports is not None:  # kinda dirty
                            self.ports = conn.info.ports
                            self.match_by = conn.info.match_by
                        conn.delete()
            else:
                src.add(n)

        tgt = set()
        for n in rawtgt:
            if hasattr(n, 'children'):
                for ch in n.children:
                    for conn in ch.connections['source']:
                        rawtgt.extend(conn.sinks)
                        if conn.info.port is not None:
                            if self.port is not None:
                                assert self.port == conn.info.port, \
                                    (self.port, conn.info.port)
                            else:
                                self.port = conn.info.port
                        if conn.info.ports is not None:  # kinda dirty
                            self.ports = conn.info.ports
                            self.match_by = conn.info.match_by
                        conn.delete()
            else:
                tgt.add(n)

        skip = self.skip_same
        if skip:
            skip_key = lambda n: n.get_property(skip)
            for sprop, snodes in groupby(sorted(src, key=skip_key), key=skip_key):
                snodes = list(snodes)
                tnodes = [n for n in tgt if n.get_property(skip) != sprop]
                ci = ConnectionInstance(self, snodes, tnodes, **(info or {}))
                for n in snodes:
                    n.add_source_connection(ci)
                for n in tnodes:
                    n.add_sink_connection(ci)
        else:
            src = list(src)
            tgt = list(tgt)
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
        #assert info.abstract or sources and sinks, info
        self.sources = sources
        self.sinks = sinks
        self.info = info
        self.match_by = match_by
        self.rules = rules
        self.default = default

    def delete(self):
        for n in self.sources:
            n.connections['source'].remove(self)
        for n in self.sinks:
            n.connections['sink'].remove(self)

    def __repr__(self):
        return ("<{0.__class__.__name__} {0.info.source}->{0.info.sink}>"
            .format(self))

    def _addr(self, nodes, props=None):
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
            if info.ports and props is None:
                for key in self.info.ports:
                    yield self._single_addr(n, {info.match_by: key})
            else:
                yield self._single_addr(n, props)

    def _single_addr(self, node, props):
        ip = None
        for r in node.rules:
            if 'ip' in r:
                ip = r['ip']
        port = self.info.port
        assert ip, node
        if not port:
            assert self.info.ports and self.info.match_by, node
            port = self.info.ports[props[self.info.match_by]]
        return 'tcp://{}:{}'.format(ip, port)

    def address_for(self, node, props):
        info = self.info
        if node in self.sources:
            if info.bound == info.source:
                for a in self._addr([node], props):
                    yield 'bind:{}:{}'.format(info.priority, a)
            else:
                if info.sink.startswith('_'):
                    return
                if self.match_by:
                    sinks = []
                    myval = props[self.match_by]
                    for t in self.sinks:
                        val = t.get_property(self.match_by)
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
                for a in self._addr([node], props):
                    yield 'bind:8:{}'.format(a)
            else:
                if info.source.startswith('_'):
                    return
                if self.match_by:
                    sources = []
                    myval = props[self.match_by]
                    for t in self.sources:
                        val = t.get_property(self.match_by)
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
            raise AssertionError("Wrong node {!r}".format(node))


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

    def __init__(self, name, matched_by_rules=(), group=None):
        self.group = group
        self.name = name
        self.rules = tuple(matched_by_rules)
        self.connections = {
            'source': [],
            'sink': [],
            }
        self.parent = None

    @classmethod
    def supernode(Node, name, nodes):
        self = Node(name, [])
        self.children = nodes
        for n in nodes:
            assert n.parent is None, n
            n.parent = self
        return self

    @property
    def abstract(self):
        return self.name.startswith('_')

    def get_property(self, name, default=None):
        for r in reversed(self.rules):
            if name in r:
                return r[name]
        return default

    def add_source_connection(self, conn):
        self.connections['source'].append(conn)

    def add_sink_connection(self, conn):
        self.connections['sink'].append(conn)

    def __repr__(self):
        if hasattr(self, 'children'):
            return '<SuperNode {!r} {!r}>'.format(self.name, self.children)
        else:
            return '<Node {!r} {!r}>'.format(self.name, self.rules)


class TopologyBuilder(object):

    def __init__(self, data):
        self._layouts = {name: Layout(val)
            for name, val in data['layouts'].items()}
        self._groups = data['groups']
        self._topologies = data['topologies']

    def _add_matching_groups(self, top, nodes):
        for groupname, g in self._groups.items():
            if g.get('match_topology') != top.name:
                continue
            l = self._layouts[g['layout']]
            groupnodes = self._process_group(groupname, g, l)
            for conn in l._connections:
                conn.instantiate(groupnodes)
            for role, nlist in groupnodes.items():
                if role.startswith('_'):
                    name = role[1:]
                    nodes[name].append(Node.supernode(name, nlist))
                else:
                    for node in nlist:
                        top.add_rule(role, node)

    def _populate_for_layout(self, top, layout, children):
        nodes = defaultdict(list)

        for i in children:
            g = self._groups[i]
            l = self._layouts[g['layout']]
            groupnodes = self._process_group(i, g, l)
            self._add_matching_groups(top, groupnodes)
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
        for ep in l._roles:
            if not ep in nodes:
                node = Node(ep)
                nodes[node.name].append(node)
        for conn in l._connections:
            conn.instantiate(nodes)
        for role, nlist in nodes.items():
            for node in nlist:
                top.add_rule(role, node)

    def _populate_from(self, top, source, slot):
        for node in source.rules[slot]:
            top.add_rule(None, node)

    def _process_group(self, groupname, group, layout):
        global_rule = group['rule']
        by_role = defaultdict(list)
        for role, rules in group.get('children', {}).items():
            for rule in rules:
                node = Node(role, [global_rule, rule], group=groupname)
                by_role[node.name].append(node)

        for ep in layout._roles:
            if not ep in by_role:
                node = Node(ep, [global_rule], group=groupname)
                by_role[node.name].append(node)
        return by_role


    def topologies(self):
        topologies = {}
        # First made topologies having layout
        for name, properties in self._topologies.items():
            if 'layout' not in properties:
                continue
            top = Topology(name, properties.pop('type'))
            self._populate_for_layout(top, **properties)
            topologies[name] = top
            yield name, top
        # The process extern topologies
        for name, properties in self._topologies.items():
            if 'topology' not in properties:
                continue
            top = ExternTopology(name, properties.pop('type'))
            self._populate_from(top,
                topologies[properties.pop('topology')],
                **properties)
            yield name, top
