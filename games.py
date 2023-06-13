import random, math
import yaml

with open('config/app.yaml', encoding='utf-8') as f:
    conf = yaml.load(f, yaml.SafeLoader)['games']


def chance():
    n = random.random() * (conf['chance'][1] - conf['chance'][0]) + conf['chance'][0]
    return n


def fortune():
    sep = conf['fortune']['sep']
    n = random.random()
    for i, key in enumerate(conf['fortune']['key']):
        if (sep[i] <= n < sep[i + 1]): return key


def pick(items):
    return items[math.floor(random.random() * len(items))]
