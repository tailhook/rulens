from functools import partial



def match_rule(props, rule):
    for k, v in rule.items():
        if v != props.get(k):
            return False
    else:
        return True


class Topology(object):

    def __init__(self, name):
        self.name = name
        self.rules = []

    def __repr__(self):
        return '<Topology {!r}>'.format(self.name)

    def resolve(self, props):
        rules = list(map(partial(match_rule, props), self.rules))
        print("RULES", rules)

