import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.simplefilter(action='ignore', category=DeprecationWarning)

import os
import sqlite3
import threading

import pandas as pd
from requests.exceptions import ReadTimeout

from linebot import LineBotApi
from linebot.models import MessageEvent


def save(event: MessageEvent, line_bot_api: LineBotApi) -> None:
    # source
    try:
        if event.source.type == "user":
            profile = line_bot_api.get_profile(event.source.user_id, timeout=15)
            id = event.source.user_id
        elif event.source.type == "group":
            group = line_bot_api.get_group_summary(event.source.group_id, timeout=15)
            profile = line_bot_api.get_group_member_profile(event.source.group_id, event.source.user_id, timeout=15)
            id = event.source.group_id
        elif event.source.type == "room":
            profile = line_bot_api.get_room_member_profile(event.source.room_id, event.source.user_i, timeout=15)
            id = event.source.room_id
    except ReadTimeout:
        profile = None
        group = None
    # message content
    time = str(pd.Timestamp(event.timestamp, unit='ms') + pd.Timedelta('08:00:00')).removesuffix('000').replace(':', '')
    if event.message.type == "text":
        content = event.message.text
    elif event.message.type == "sticker":  #https://stickershop.line-scdn.net/stickershop/v1/sticker/{sticker_id}/iPhone/sticker@2x.png
        content = event.message.sticker_id
    else:
        os.makedirs('data/download', exist_ok=True)
        if event.message.type == "image":
            content = f'{time}.png'
        elif event.message.type == "video":
            content = f'{time}.mp4'
        elif event.message.type == "audio":
            content = f'{time}.aac'
        elif event.message.type == "file":
            content = f'{event.message.file_name}'
        else:
            return None

        def download():
            try:
                folder = f'data/download/{id}/{time}'
                os.makedirs(folder, exist_ok=True)
                with open(f'{folder}/{content}', 'wb') as f:
                    for chunk in line_bot_api.get_message_content(event.message.id, timeout=15).iter_content():
                        f.write(chunk)
            except ReadTimeout:
                pass

        threading.Thread(target=download).start()

    # db
    with sqlite3.connect("data/chat.db") as con:
        cur = con.cursor()
        if event.source.type == "user":
            cur.execute(f"CREATE TABLE IF NOT EXISTS {id} (source, time, user_id, user_name, type, message_id, content);")
            cur.execute(f"INSERT INTO {id} (source, time, user_id, user_name, type, message_id, content) VALUES (?, ?, ?, ?, ?, ?, ?);", [
                event.source.type, time, event.source.user_id,
                getattr(profile, "display_name", None), event.message.type, event.message.id, content
            ])
        elif event.source.type == "group":
            cur.execute(f"CREATE TABLE IF NOT EXISTS {id} (source, time, group_id, group_name, user_id, user_name, type, message_id, content);")
            cur.execute(
                f"INSERT INTO {id} (source, time, group_id, group_name, user_id, user_name, type, message_id, content) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
                [
                    event.source.type, time, event.source.group_id,
                    getattr(group, "group_name", None), event.source.user_id,
                    getattr(profile, "display_name", None), event.message.type, event.message.id, content
                ])
        elif event.source.type == "room":
            cur.execute(f"CREATE TABLE IF NOT EXISTS {id} (source, time, room_id, user_id, user_name, type, message_id, content);")
            cur.execute(f"INSERT INTO {id} (source, time, room_id, user_id, user_name, type, message_id, content) VALUES (?, ?, ?, ?, ?, ?, ?, ?);", [
                event.source.type, time, event.source.room_id, event.source.user_id,
                getattr(profile, "display_name", None), event.message.type, event.message.id, content
            ])


def count(id, start, end, delta='D'):
    with sqlite3.connect("data/chat.db") as con:
        df = pd.read_sql(f'SELECT * FROM {id}', con, parse_dates=["time"])[['time', 'user_name']]
    df['time'] = df['time'].dt.to_period(freq=delta).dt.to_timestamp()
    df = df[df["time"] >= pd.Timestamp(start)]
    df = df[df["time"] < pd.Timestamp(end)]
    L = list()
    for time, df in df.groupby("time"):
        s = df["user_name"].value_counts()
        s.name = time
        L.append(s)
    df = pd.concat(L, axis=1).fillna(0).astype(int)
    df = df.rename_axis("Name")
    df.insert(0, "Total", df.sum(axis=1))
    if id[0] != "U":
        df = df.append(df.sum(axis=0).rename("Total"))
        df = df.sort_values("Total", ascending=False)
        df.insert(0, "Rank", range(len(df)))
    return '發言次數統計\n' + df.to_csv(sep=',')
