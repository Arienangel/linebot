import json
import os
import random
import re
import string

import numpy as np
from dotenv import load_dotenv

load_dotenv('config.env')

banlist = json.loads(os.getenv("banlist"))
prob_range = json.loads(os.getenv("prob_range"))
fortune_key = json.loads(os.getenv("fortune_key"))
fortune_prob = json.loads(os.getenv("fortune_prob"))


def bancheck(banned: list, check: list):
    for i in banned:
        for j in check:
            if re.search(str(i), str(j), flags=re.IGNORECASE):
                return True
    else:
        return False


def chance(*args, format=True, check=True):
    if check:
        if bancheck(banlist, args):
            return "窩不知道"
    n = len(args)
    prob = np.random.randint(*prob_range, size=n if n else 1)
    if format:
        if n == 0:
            return f"預言家算機率: 大約有{prob[0]}%機率發生"
        else:
            return "預言家算機率，結果為\n" + "\n".join([f"{args[i]}: {prob[i]}%" for i in range(n)])
    else:
        return prob


def fortune(*args, format=True, check=True):
    if check:
        if bancheck(banlist, args):
            return "窩不知道"
    n = len(args)
    rank = np.random.choice(fortune_key, size=n if n else 1, replace=True, p=fortune_prob)
    if format:
        if n == 0:
            return f"占卜師測運勢，結果為: 本日{rank[0]}"
        else:
            return "占卜師測運勢，結果為\n" + "\n".join([f"{args[i]}:{rank[i]}" for i in range(n)])
    else:
        return rank


def randstr(length: int = 8, type: list = [0], n: int = 1, format=True):
    pool = str()
    for i in type:
        try:
            pool += (string.digits, string.ascii_lowercase, string.ascii_uppercase, string.punctuation)[int(i)]
        except IndexError:
            continue
    getstring = lambda: "".join(np.random.choice(tuple(pool), int(length)))
    L = [getstring() for _ in range(int(n))]
    if format:
        return "亂數產生器\n" + "\n".join(L)
    else:
        return L


def pick(*args, format=True, check=True):
    if check:
        if bancheck(banlist, args):
            return "窩不知道"
    if len(args):
        if format:
            return "選項: " + " ".join(args) + "\n機器喵選擇: " + random.choice(args)
        else:
            return random.choice(args)
    else:
        return "窩不知道"


def dice(n, format=True):
    A = np.random.randint(1, 7, int(n))
    if n == 1:
        return str(A[0])
    else:
        if format:
            B = np.arange(1, int(n) + 1, 1)
            return '\n'.join(['{}: {}'.format(*l) for l in np.stack([B, A], axis=-1)])
        else:
            return A
