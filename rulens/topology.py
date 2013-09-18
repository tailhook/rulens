from collections import defaultdict

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
    if hasattr(node, 'children'):
        for n in node.children:
            for rule in n.rules:
                for k, v in rule.items():
                    if v != props.get(k):
                        return False
    return True



class Topology(object):

    def __init__(self, name, type):
        self.name = name
        self.type = type
        self.party_mapping = PARTIES[type]
        self.rules = defaultdict(list)

    def __repr__(self):
        return '<{} {} {!r}>'.format(
            self.__class__.__name__, self.type, self.name)

    def resolve_node(self, role, props):
        for node in self.rules[role]:
            if match_rule(props, node):
                break
        else:
            raise AssertionError("No rule for node")
        return node

    def add_rule(self, role, rule):
        self.rules[role].append(rule)


class ExternTopology(Topology):

    def resolve_node(self, role, props):
        return super().resolve_node(None, props)

