from collections import defaultdict
from functools import partial

PARTIES = {
    'reqrep': {
        'NN_REQ': 'source',
        'NN_REP': 'sink',
        },
    'pipeline': {
        'NN_PUSH': 'source',
        'NN_PULL': 'sink',
        },
    'pubsub': {
        'NN_PUB': 'source',
        'NN_SUB': 'sink',
        },
    'survey': {
        'NN_SURVEYOR': 'source',
        'NN_RESPONDENT': 'sink',
        },
    }



def match_rule(props, node):
    for rule in node.rules:
        for k, v in rule.items():
            if v != props.get(k):
                return False
    else:
        return True


class Topology(object):

    def __init__(self, name, type):
        self.name = name
        self.type = type
        self.party_mapping = PARTIES[type]
        self.rules = defaultdict(list)

    def __repr__(self):
        return '<Topology {!r}>'.format(self.name)

    def resolve(self, role, sock_type, props):
        party = self.party_mapping[sock_type]
        rules = list(filter(partial(match_rule, props),
            self.rules[role]))
        if len(rules) > 1:
            raise AssertionError("Ambiguous node")
        if len(rules) < 1:
            raise AssertionError("No rule for node")
        node = rules[0]
        for conn in node.connections[party]:
            yield from conn.address_for(node, props)

    def add_rule(self, role, rule):
        self.rules[role].append(rule)
