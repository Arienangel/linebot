import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.simplefilter(action='ignore', category=DeprecationWarning)

import sqlite3
import pandas as pd
from linebot import LineBotApi
from linebot.models import MessageEvent



def save(event: MessageEvent, line_bot_api: LineBotApi) -> None:
    try:
        if event.source.type == "group":
            con = sqlite3.connect("db/group.db")
            cur = con.cursor()
            group = line_bot_api.get_group_summary(event.source.group_id)
            profile = line_bot_api.get_group_member_profile(event.source.group_id, event.source.user_id)
            dbid = group.group_id
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS {dbid} (time, group_id, group_name, user_id, user_name, type, message_id, text, filename, sticker_id);")
            cur.execute(
                f"INSERT INTO {dbid} (time, group_id ,group_name ,user_id ,user_name, type, message_id) VALUES (? ,?, ?, ?, ?, ?, ?);",
                [event.timestamp, group.group_id, group.group_name, profile.user_id, profile.display_name, event.message.type, event.message.id])
        elif event.source.type == "user":
            con = sqlite3.connect("db/user.db")
            cur = con.cursor()
            profile = line_bot_api.get_profile(event.source.user_id)
            dbid = profile.user_id
            cur.execute(f"CREATE TABLE IF NOT EXISTS {dbid} (time, user_id, user_name, type, message_id, text, filename, sticker_id);")
            cur.execute(f"INSERT INTO {dbid} (time, user_id, user_name, type, message_id) VALUES (?, ?, ?, ?, ?);",
                        [event.timestamp, profile.user_id, profile.display_name, event.message.type, event.message.id])
        else:
            return None
        if event.message.type == "text":
            cur.execute(f"UPDATE {dbid} SET text=? WHERE message_id=?;", [event.message.text, event.message.id])
        elif event.message.type == "sticker":  #https://stickershop.line-scdn.net/stickershop/v1/sticker/{sticker_id}/iPhone/sticker@2x.png
            cur.execute(f"UPDATE {dbid} SET sticker_id=? WHERE message_id=?;", [event.message.sticker_id, event.message.package_id, event.message.id])
        else:
            if event.message.type == "image":
                filename = f'{event.timestamp}.png'
            elif event.message.type == "video":
                filename = f'{event.timestamp}.mp4'
            elif event.message.type == "audio":
                filename = f'{event.timestamp}.aac'
            elif event.message.type == "file":
                filename = f'{event.timestamp}_{event.message.file_name}'
            else:
                return None
            try:
                content = line_bot_api.get_message_content(event.message.id, timeout=30)
                with open(f'data/{filename}', 'wb') as f:
                    for chunk in content.iter_content():
                        f.write(chunk)
            except:
                cur.execute(f"UPDATE {dbid} SET WHERE message_id=?;", [event.message.id])
            else:
                cur.execute(f"UPDATE {dbid} SET filename=? WHERE message_id=?;", [filename, event.message.id])
    finally:
        con.commit()
        con.close()


def count(db, table, start=None, end=None, delta='D'):
    with sqlite3.connect(db) as con:
        df = pd.read_sql(f'SELECT * FROM {table}', con, parse_dates={"time": {"unit": 'ms'}})[['time', 'user_name']]
        df['time'] += pd.Timedelta('08:00:00')
        df['time'] = df['time'].dt.to_period(freq=delta).dt.to_timestamp()
        if start:
            start = pd.Timestamp(start)
            df = df[df["time"] >= start]
        if end:
            end = pd.Timestamp(end)
            df = df[df["time"] < end]
        G = df.groupby("time")
        L = list()
        for time, df in G:
            s = df["user_name"].value_counts()
            s.name = time
            L.append(s)
        df = pd.concat(L, axis=1).fillna(0).astype(int)
        df = df.rename_axis("Name")
        df.insert(0, "Total", df.sum(axis=1))
        if 'group' in db:
            df = df.append(df.sum(axis=0).rename("Total"))
            df = df.sort_values("Total", ascending=False)
            df.insert(0, "Rank", range(len(df)))
        return df.to_csv(sep=',')