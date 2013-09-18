"""
    The command-line interface for static-checking of topology db
"""
import argparse
import sys
import io
import subprocess
import yaml
from urllib.parse import urlparse, parse_qsl
from contextlib import contextmanager
from collections import defaultdict
from itertools import product
from functools import partial

from .db import Database


@contextmanager
def set_stdout(file):
    oldstdout = sys.stdout
    try:
        sys.stdout = file
        yield
    finally:
        sys.stdout = oldstdout

def draw_instance_graph(options, db):
    hosts = defaultdict(partial(defaultdict, dict))
    devices = set()
    conn = defaultdict(list)
    bind = defaultdict(list)
    priorities = set()
    counter = 0
    for fn in options.list_file:
        with open(fn, 'rt') as file:
            for line in file:
                line = line.strip()
                if line.startswith('#'):  # comment
                    continue
                url, nodetype = line.split()
                if nodetype == 'device':
                    socktypes = ('NN_REQ', 'NN_REP')
                u = urlparse(url)
                query = dict(parse_qsl(u.query))
                nname = '{0[hostname]}_{0[role]}_{0[pid]}'.format(query)
                if nodetype == 'device':
                    devices.add(nname)
                group = db.get_group(None, None, url, socktypes[0])
                hosts[group][query['hostname']][nname] = query
                for socktype in socktypes:
                    for addr in db.resolve(None, None, url, socktype):
                        kind, priority, raddr = addr.split(':', 2)
                        if socktype == 'NN_REQ':  # TODO(pc) other types!
                            priority = int(priority)
                            priorities.add(priority)
                        else:
                            priority = None
                        if kind == 'bind':
                            bind[raddr].append((priority, nname))
                        elif kind == 'connect':
                            conn[raddr].append((priority, nname))
                        else:
                            raise AssertionError(
                                "Wrong address {!r}".format(addr))
    priority_styles = ['dotted', 'dashed', 'solid']
    priority_lengths = [0, 0, 1]
    priostyles = {None: 'solid'}
    priolengths = {None: 1}
    for i in sorted(priorities):
        priostyles[i] = priority_styles.pop()
        priolengths[i] = priority_lengths.pop()

    if options.raw:
        stream = sys.stdout
    else:
        fn = 'instance_graph.png'
        print("Writing", fn)
        proc = subprocess.Popen(['dot', '-Tpng', '-o', fn],
            stdin=subprocess.PIPE)
        stream = io.TextIOWrapper(proc.stdin)
    with set_stdout(stream):
        print("digraph topology {")
        print("rankdir=LR")
        print("ranksep=2")

        for group, ghosts in hosts.items():
            print("subgraph cluster_{} {{".format(group))
            print("style=dotted")
            print('label="{}"'.format(group))
            for host, ndict in ghosts.items():
                print("subgraph cluster_{} {{".format(host))
                print('label="{}"'.format(host))
                print('style=solid')
                print('color=gray')
                for name, props in ndict.items():
                    if name in devices:
                        print('{0} [shape=record style=rounded '
                              'label="{{<REP>REP | {1[role]} | <REQ>REQ}}"]'
                            .format(name, props))
                    else:
                        print('{0} [label={1[role]}]'.format(name, props))
                print("}")
            print("}")

        for addr, nlist in bind.items():
            nlist = set(nlist)
            targlist = conn.pop(addr, None)
            if targlist is not None:
                for (pa, a), (pb, b) in product(nlist, targlist):
                    if pa: # priority is in a req socket
                        prio = pa
                        arrowhead = 'none'
                        arrowtail = 'inv'
                    else:
                        prio = pb
                        a, b = b, a
                        arrowhead = 'normal'
                        arrowtail = 'none'
                    if a in devices:
                        a = a + ':REQ'
                    if b in devices:
                        b = b + ':REP'

                    print('{} -> {} [style={} minlen={} arrowhead={} arrowtail={} dir=both]'
                        .format(a, b, priostyles[prio], priolengths[prio],
                            arrowhead, arrowtail))
            else:
                for p, n in nlist:
                    counter += 1
                    if p is None: # priority is in a req socket
                        print('ext_{} [shape=octagon label="{}"]'
                            .format(counter, addr[len('tcp://'):]))
                        print('ext_{} -> {} [style="{}"]'
                            .format(counter, n, priostyles[p]))
                    else:
                        print('ext_{} [shape=octagon label="{}"]'
                            .format(counter, addr[len('tcp://'):]))
                        print('{} -> ext_{} [style="{}" dir=back arrowhead=inv]'
                            .format(n, counter, priostyles[p]))
        print('{rank=same;',
            ' '.join('ext_' + str(i) for i in range(1, counter+1)),
            '}')
        if conn:
            raise ValueError(conn)

        print("}")


def draw_layout_graph(options, lname, layout):
    fn = lname + '_graph.png'
    if options.raw:
        stream = sys.stdout
    else:
        print("Writing", fn)
        proc = subprocess.Popen(['dot', '-Tpng', '-o', fn],
            stdin=subprocess.PIPE)
        stream = io.TextIOWrapper(proc.stdin)
    with set_stdout(stream):
        print('digraph', lname, '{')
        nodes = set()
        for k in layout:
            a, arr, b = k.split()
            if a not in nodes:
                nodes.add(a)
                if a.startswith('_'):
                    print(a, '[shape=octagon]')
            if b not in nodes:
                nodes.add(b)
                if b.startswith('_'):
                    print(b, '[shape=octagon]')
        for k in layout:
            a, arr, b = k.split()
            if arr == '->':
                print(k)
            else:
                print(b, '->', a, '[dir=back arrowtail=inv]')
        print('}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('topology_files', nargs='+',
        help="Files to read topology from")
    ap.add_argument('-l', '--list-file', default=[], action="append",
        help="The text file with list of name requests to run tests against")
    ap.add_argument('-L', '--layout-graph', metavar="LAYOUT",
        help="Draw bare diagram for a single layout from topology file")
    ap.add_argument('-G', '--instance-graph', action="store_true",
        help="Draw diagram of nodes read from --list-file")
    ap.add_argument('-p', '--print-addresses', action="store_true",
        help="Print addresses resolved for each --list-file")
    ap.add_argument('--raw', action="store_true",
        help="Print graph data instead of drawing graph")
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
                    url, nodetype = line.split()
                    if nodetype == 'device':
                        socktypes = ('NN_REQ', 'NN_REP')
                    else:
                        socktypes = (nodetype,)
                    for socktype in socktypes:
                        print(url, socktype)
                        for addr in db.resolve(None, None, url, socktype):
                            print('   ', addr)

    if options.instance_graph:
        draw_instance_graph(options, db)

    if options.layout_graph:
        for i in options.topology_files:
            with open(i, 'rt') as f:
                data = yaml.load(f)
            ldata = data['layouts'].get(options.layout_graph)
            if ldata is not None:
                draw_layout_graph(options, options.layout_graph, ldata)
                break


if __name__ == '__main__':
    main()
