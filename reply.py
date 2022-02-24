import json
import sqlite3

path = "data/reply.db"


def add(id, input, output):
    with sqlite3.connect(path) as con:
        cur = con.cursor()
        cur.execute(f'CREATE TABLE IF NOT EXISTS "{id}" ("input" UNIQUE, "output");')
        cur.execute(f'REPLACE INTO {id} (input, output) VALUES (?, ?);', [input, output])


def add_json(id, json_string: str):
    s = json.loads(json_string)
    if type(s) is dict:
        s = [{'input': key, 'output': value} for key, value in s.items()]
    with sqlite3.connect(path) as con:
        cur = con.cursor()
        cur.execute(f'CREATE TABLE IF NOT EXISTS "{id}" ("input" UNIQUE, "output");')
        cur.executemany(f'REPLACE INTO {id} (input, output) VALUES (:input, :output);', s)


def delete(id, input):
    with sqlite3.connect(path) as con:
        cur = con.cursor()
        cur.execute(f'DELETE FROM {id} WHERE input=?;', [input])


def reset(id):
    with sqlite3.connect(path) as con:
        cur = con.cursor()
        cur.execute(f'DROP TABLE {id};')


def help(id):
    with sqlite3.connect(path) as con:
        cur = con.cursor()
        try:
            r = cur.execute(f'SELECT input FROM {id};')
        except:
            return ''
    return '\n'.join([str(i[0]) for i in r.fetchall()])


def reply(id, input):
    with sqlite3.connect(path) as con:
        cur = con.cursor()
        try:
            r = cur.execute(f'SELECT output FROM (SELECT input, output FROM {id} WHERE input=?);', [input]).fetchone()
        except: return None
    if r:
        return str(r[0])
    else:
        return None