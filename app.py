import asyncio
import re

import sqlite3
import dateutil.parser
import dateutil.relativedelta
import yaml
from flask import Flask, abort, request

import chatgpt
import games
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MemberJoinedEvent, MessageEvent, TextSendMessage

with open('config/app.yaml', encoding='utf-8') as f:
    conf = yaml.load(f, yaml.SafeLoader)['app']

app = Flask(__name__)
line_bot_api = LineBotApi(conf['bot']['channel_access_token'])
handler = WebhookHandler(conf['bot']['channel_secret'])


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)
    return 'OK'


@handler.add(MessageEvent)
def handle_message(event: MessageEvent):
    GID = event.source.group_id if event.source.type == 'group' else event.source.room_id if event.source.type == 'room' else event.source.user_id
    if event.message.type == 'text':
        # command
        try:
            if event.message.text.startswith('/'):
                if re.match('/help', event.message.text):
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=conf['command']['help']['message']))
                elif re.match('/gpt', event.message.text):
                    ctx = event.message.text.split(' ', maxsplit=1)[1]
                    gpt, temp = asyncio.run(chatgpt.gpt35(ctx, conf['command']['gpt']['temperature']))
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f'{gpt.choices[0].message.content}'))
                elif re.match('/chance', event.message.text):
                    ctx = event.message.text.split(' ', maxsplit=1)
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f'{ctx[-1] if len(ctx)>1 else "機率"}: {round(games.chance(), 2):.0%}'))
                elif re.match('/dice', event.message.text):
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f'{games.pick(list(range(1, 7)))}'))
                elif re.match('/fortune', event.message.text):
                    ctx = event.message.text.split(' ', maxsplit=1)
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f'{ctx[-1] if len(ctx)>1 else "運勢"}: {games.fortune()}'))
                elif re.match('/pick', event.message.text):
                    ctx = event.message.text.split(' ')
                    if len(ctx) > 1:
                        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f'選擇: {games.pick(list(ctx[1:]))}'))
                elif re.match('/echo', event.message.text):
                    ctx = event.message.text.split(' ', maxsplit=2)[1:]
                    with sqlite3.connect('data/echo.db') as con:
                        cur = con.cursor()
                        cur.execute(f'CREATE TABLE IF NOT EXISTS  `{GID}` ("request" UNIQUE, "response");')
                        if ctx[0] == 'ls':
                            cur.execute(f'SELECT * FROM `{GID}`;')
                            L = [f'{row[0]} -> {row[1]}' for row in cur]
                            if len(L) > 0: line_bot_api.reply_message(event.reply_token, TextSendMessage(text='echo: \n' + '\n'.join(L)))
                            else: line_bot_api.reply_message(event.reply_token, TextSendMessage(text='echo: None'))
                        elif ctx[0] == 'add':
                            req, res = ctx[1].split(' ', maxsplit=1)
                            if req.startswith('/'):
                                line_bot_api.reply_message(event.reply_token, TextSendMessage(text='不可以使用"/"開頭'))
                            else:
                                cur.execute(f'INSERT OR REPLACE INTO `{GID}` VALUES (?, ?);', [req, res])
                        elif ctx[0] == 'rm':
                            for x in ctx[1].split(' '):
                                cur.execute(f' DELETE FROM `{GID}` WHERE request=?;', [x])
                        elif ctx[0] == 'reset':
                            cur.execute(f' DELETE FROM `{GID}`;')
                elif re.match('/stat', event.message.text):
                    start, end, *_ = event.message.text.split(' ', maxsplit=3)[1:]
                    start = dateutil.parser.parse(start)
                    end = dateutil.parser.parse(end)
                    L = list()
                    with sqlite3.connect(f'data/messages.db') as con:
                        cur = con.cursor()
                        cur.execute(f'SELECT user, COUNT(*) FROM `{GID}` WHERE time>={int(start.timestamp())*1000} and time<{int(end.timestamp())*1000}  GROUP BY user  ORDER BY  2 DESC;')
                        for row in cur:
                            try:
                                name = getattr(get_user_profile(row[0], GID), "display_name", None)
                                if name is None: name = row[0]
                                else: L.append(f'{name}: {row[1]}')
                            except:
                                continue
                    text = f'{start.strftime("%Y/%m/%d %H:%M:%S")}~{end.strftime("%Y/%m/%d %H:%M:%S")}\n'
                    if L:
                        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=text + '\n'.join(L)))
                    else:
                        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=text + 'None'))
        except:
            pass

        # not command
        else:
            # echo message
            try:
                with sqlite3.connect('data/echo.db') as con:
                    cur = con.cursor()
                    cur.execute(f'CREATE TABLE IF NOT EXISTS  `{GID}` ("request" UNIQUE, "response");')
                    cur.execute(f'SELECT response FROM `{GID}` WHERE request=?;', [event.message.text])
                    L = cur.fetchone()
                    if L: line_bot_api.reply_message(event.reply_token, TextSendMessage(text=L[0]))
            except:
                pass

    # record message to sql
    try:
        if event.message.type == 'text': content = event.message.text
        elif event.message.type == 'sticker': content = event.message.sticker_id
        with sqlite3.connect(f'data/messages.db') as con:
            cur = con.cursor()
            cur.execute(f'CREATE TABLE IF NOT EXISTS `{GID}` (id, time, user, type, content);')
            cur.execute(f'INSERT INTO `{GID}` VALUES (?,?,?,?,?);', [event.message.id, event.timestamp, event.source.user_id, event.message.type, content])
    except:
        pass


@handler.add(MemberJoinedEvent)
def greeting(event: MemberJoinedEvent):
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text='喵~', notification_disabled=True))


def get_user_profile(UID: str, GID: str):
    if GID.startswith('U'): return line_bot_api.get_profile(UID)
    elif GID.startswith('C'): return line_bot_api.get_group_member_profile(GID, UID)
    elif GID.startswith('R'): return line_bot_api.get_room_member_profile(GID, UID)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=conf['bot']['port'], debug=True)
