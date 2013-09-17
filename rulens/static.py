"""
    The command-line interface for static-checking of topology db
"""
import argparse
import sys
import io
import subprocess
from urllib.parse import urlparse, parse_qsl
from contextlib import contextmanager
from collections import defaultdict
from itertools import product

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
    fn = 'instance_graph.png'
    print("Writing", fn)
    proc = subprocess.Popen(['dot', '-Tpng', '-o', fn],
        stdin=subprocess.PIPE)
    hosts = defaultdict(dict)
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
                for socktype in socktypes:
                    u = urlparse(url)
                    query = dict(parse_qsl(u.query))
                    nname = '{0[hostname]}_{0[role]}_{0[pid]}'.format(query)
                    if nodetype == 'device':
                        devices.add(nname)
                    hosts[query['hostname']][nname] = query
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
    priority_lengths = [0, 0, 2]
    priostyles = {None: 'solid'}
    priolengths = {None: 1}
    for i in sorted(priorities):
        priostyles[i] = priority_styles.pop()
        priolengths[i] = priority_lengths.pop()

    #if True:
    with set_stdout(io.TextIOWrapper(proc.stdin)):
        print("digraph topology {")
        print("rankdir=LR")

        for host, ndict in hosts.items():
            print("subgraph cluster_{} {{".format(host))
            print('label="{}"'.format(host))
            for name, props in ndict.items():
                if name in devices:
                    print('{0} [shape=record style=rounded '
                          'label="{{<REP>REP | {1[role]} | <REQ>REQ}}"]'
                        .format(name, props))
                else:
                    print('{0} [label={1[role]}]'.format(name, props))
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
                            .format(counter, addr))
                        print('ext_{} -> {} [style="{}"]'
                            .format(counter, n, priostyles[p]))
                    else:
                        print('ext_{} [shape=octagon label="{}"]'
                            .format(counter, addr))
                        print('{} -> ext_{} [style="{}" dir=back arrowhead=inv]'
                            .format(n, counter, priostyles[p]))
        if conn:
            raise ValueError(conn)

        print("}")


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
        draw_instance_graph(options, db)


if __name__ == '__main__':
    main()
