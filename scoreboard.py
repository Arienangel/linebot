import sqlite3

path = "data/scoreboard/scoreboard.db"


def get(id, name=None, object=None):
    with sqlite3.connect(path) as con:
        cur = con.cursor()
        if object:
            r = cur.execute(f'SELECT object, points FROM (SELECT * FROM {id} WHERE (name=? and object=?));', [name, object])
            return r.fetchone()
        elif name:
            r = cur.execute(f'SELECT object, points FROM (SELECT * FROM {id} WHERE name=?);', [name])
            return r.fetchall()
        else:
            r = cur.execute(f'SELECT DISTINCT name FROM {id};')
            return r.fetchall()


def edit(id, name, object, point, mode='edit'):
    with sqlite3.connect(path) as con:
        cur = con.cursor()
        cur.execute(f'CREATE TABLE IF NOT EXISTS "{id}" ("name", "object", "points" INTEGER);')
        p = cur.execute(f'SELECT points FROM (SELECT * FROM {id} WHERE (name=? and object=?));', [name, object]).fetchone()
        if p:
            if mode == '+' or mode == '-':
                point = int(p[0]) + int(point)
            cur.execute(f'UPDATE {id} SET points=? WHERE  (name=? and object=?);', [int(point), name, object])
        else:
            cur.execute(f'INSERT INTO {id} (name, object, points) VALUES (?, ?, ?);', [name, object, int(point)])


def delete(id, name, object=None):
    with sqlite3.connect(path) as con:
        cur = con.cursor()
        if object:
            cur.execute(f'DELETE FROM {id} WHERE object=?;', [object])
        else:
            cur.execute(f'DELETE FROM {id} WHERE name=?;', [name])


def reset(id):
    with sqlite3.connect(path) as con:
        cur = con.cursor()
        cur.execute(f'DROP TABLE {id};')
