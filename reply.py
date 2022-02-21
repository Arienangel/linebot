import json, os
from collections import defaultdict


def load():
    global D
    D=defaultdict(dict)
    for id in os.listdir("data/reply"):
        id = id.removesuffix(".json")
        with open(f'data/reply/{id}.json', encoding='utf-8') as f:
            D.update({id: json.load(f)})


def add(input, output, id):
    if input not in D[id]:
        D[id].update({input: output})
        with open(f'data/reply/{id}.json', mode='wt', encoding='utf-8') as f:
            json.dump(D[id], f, ensure_ascii=False)

def add_json(s: str, id):
    d=json.loads(s)
    if type(d) is dict:
        D[id].update(d)
        with open(f'data/reply/{id}.json', mode='wt', encoding='utf-8') as f:
            json.dump(D[id], f, ensure_ascii=False)

def edit(input, output, id):
    if input in D[id]:
        D[id][input] = output
        with open(f'data/reply/{id}.json', mode='wt', encoding='utf-8') as f:
            json.dump(D[id], f, ensure_ascii=False)


def delete(input, id):
    if input in D[id]:
        D[id].pop(input)
        with open(f'data/reply/{id}.json', mode='wt', encoding='utf-8') as f:
            json.dump(D[id], f, ensure_ascii=False)


def reset(id):
    if id in D:
        D.pop(id)
    if os.path.exists(f"data/reply/{id}.json"):
        os.remove(f"data/reply/{id}.json")


def help(id):
    if id in D:
        text='\n'.join(D[id].keys())
        return text
    else:
        return ''


def reply(input, id):
    if input in D[id]:
        return str(D[id][input])
    else:
        return False

load()