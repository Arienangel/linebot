import os
import re

import aiofiles
import aiosqlite
import dateutil.parser
import dateutil.relativedelta
import yaml
from flask import Flask, abort, request

import chatgpt
import games
from aiolinebot import AioLineBotApi
from aiolinebot_handler import AsyncWebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MemberJoinedEvent, MessageEvent, TextSendMessage

with open('config/app.yaml', encoding='utf-8') as f:
    conf = yaml.load(f, yaml.SafeLoader)['app']

app = Flask(__name__)
line_bot_api = AioLineBotApi(conf['bot']['channel_access_token'])
handler = AsyncWebhookHandler(conf['bot']['channel_secret'])


@app.route("/", methods=['POST'])
async def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        await handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


@handler.add(MessageEvent)
async def handle_message(event: MessageEvent):

    async def command():
        if re.match('/help', event.message.text):
            await line_bot_api.reply_message_async(event.reply_token, TextSendMessage(text=conf['command']['help']['message']))
        elif re.match('/gpt', event.message.text):
            ctx = event.message.text.split(' ', maxsplit=1)[1]
            gpt, temp = await chatgpt.gpt35(ctx, conf['command']['gpt']['temperature'])
            await line_bot_api.reply_message_async(event.reply_token, TextSendMessage(text=f'{gpt.choices[0].message.content}'))
        elif re.match('/chance', event.message.text):
            ctx = event.message.text.split(' ', maxsplit=1)
            await line_bot_api.reply_message_async(event.reply_token, TextSendMessage(text=f'{ctx[-1] if len(ctx)>1 else "機率"}: {round(games.chance(), 2):.0%}'))
        elif re.match('/dice', event.message.text):
            await line_bot_api.reply_message_async(event.reply_token, TextSendMessage(text=f'{games.pick(list(range(1, 7)))}'))
        elif re.match('/fortune', event.message.text):
            ctx = event.message.text.split(' ', maxsplit=1)
            await line_bot_api.reply_message_async(event.reply_token, TextSendMessage(text=f'{ctx[-1] if len(ctx)>1 else "運勢"}: {games.fortune()}'))
        elif re.match('/pick', event.message.text):
            ctx = event.message.text.split(' ')
            if len(ctx) > 1:
                await line_bot_api.reply_message_async(event.reply_token, TextSendMessage(text=f'選擇: {games.pick(list(ctx[1:]))}'))
        elif re.match('/echo', event.message.text):
            ctx = event.message.text.split(' ', maxsplit=2)[1:]
            async with aiosqlite.connect('data/echo.db') as db:
                await db.execute(f'CREATE TABLE IF NOT EXISTS  `{GID}` ("request" UNIQUE, "response");')
                await db.commit()
                if ctx[0] == 'ls':
                    async with db.execute(f'SELECT * FROM `{GID}`;') as cur:
                        L = [f'{row[0]} -> {row[1]}' async for row in cur]
                    if len(L) > 0: await line_bot_api.reply_message_async(event.reply_token, TextSendMessage(text='echo: \n' + '\n'.join(L)))
                    else: await line_bot_api.reply_message_async(event.reply_token, TextSendMessage(text='echo: None'))
                elif ctx[0] == 'add':
                    req, res = ctx[1].split(' ', maxsplit=1)
                    if req.startswith('/'):
                        await line_bot_api.reply_message_async(event.reply_token, TextSendMessage(text='不可以使用"/"開頭'))
                    else:
                        await db.execute(f'INSERT OR REPLACE INTO `{GID}` VALUES (?, ?);', [req, res])
                        await db.commit()
                elif ctx[0] == 'rm':
                    for x in ctx[1].split(' '):
                        await db.execute(f' DELETE FROM `{GID}` WHERE request=?;', [x])
                    await db.commit()
                elif ctx[0] == 'reset':
                    await db.execute(f' DELETE FROM `{GID}`;')
                    await db.commit()
        elif re.match('/stat', event.message.text):
            start, end, *_ = event.message.text.split(' ', maxsplit=3)[1:]
            start = dateutil.parser.parse(start)
            end = dateutil.parser.parse(end)
            L = list()
            async with aiosqlite.connect(f'data/messages.db') as db:
                async with db.execute(f'SELECT user, COUNT(*) FROM `{GID}` WHERE time>={int(start.timestamp())*1000} and time<{int(end.timestamp())*1000}  GROUP BY user  ORDER BY  2 DESC;') as cur:
                    async for row in cur:
                        try:
                            profile = await get_user_profile(row[0], GID)
                            name = getattr(profile, "display_name", None)
                            if name is None: name = row[0]
                            else: L.append(f'{name}: {row[1]}')
                        except:
                            continue
            text = f'{start.strftime("%Y/%m/%d %H:%M:%S")}~{end.strftime("%Y/%m/%d %H:%M:%S")}\n'
            if L:
                await line_bot_api.reply_message_async(event.reply_token, TextSendMessage(text=text + '\n'.join(L)))
            else:
                await line_bot_api.reply_message_async(event.reply_token, TextSendMessage(text=text + 'None'))

    async def echo():
        async with aiosqlite.connect('data/echo.db') as db:
            await db.execute(f'CREATE TABLE IF NOT EXISTS  `{GID}` ("request" UNIQUE, "response");')
            await db.commit()
            async with db.execute(f'SELECT response FROM `{GID}` WHERE request=?;', [event.message.text]) as cur:
                L = await cur.fetchone()
            if L: await line_bot_api.reply_message_async(event.reply_token, TextSendMessage(text=L[0]))

    async def record_message():
        if event.message.type == 'text': content = event.message.text
        elif event.message.type == 'sticker': content = event.message.sticker_id
        else:
            content = None
            if event.message.content_provider.type == 'line':
                if conf['download']: await download()
        async with aiosqlite.connect(f'data/messages.db') as db:
            await db.execute(f'CREATE TABLE IF NOT EXISTS `{GID}` (id, time, user, type, content);')
            await db.execute(f'INSERT INTO `{GID}` VALUES (?,?,?,?,?);', [event.message.id, event.timestamp, event.source.user_id, event.message.type, content])
            await db.commit()

    async def download():
        try:
            folder = f'data/attachment/{GID}'
            os.makedirs(folder, exist_ok=True)
            data = await line_bot_api.get_message_content_async(event.message.id, timeout=30)
            ext = data.content_type.split('/')[1]
            async with aiofiles.open(f'{folder}/{event.timestamp}.{ext}', mode='wb') as f:
                async for chunk in data.iter_content():
                    await f.write(chunk)
        except:
            pass

    GID = event.source.group_id if event.source.type == 'group' else event.source.room_id if event.source.type == 'room' else event.source.user_id
    await record_message()
    if event.message.type == 'text':
        if event.message.text.startswith('/'): await command()
        else: await echo()


@handler.add(MemberJoinedEvent)
async def greeting(event: MemberJoinedEvent):
    await line_bot_api.reply_message_async(event.reply_token, TextSendMessage(text='喵~', notification_disabled=True))


async def get_user_profile(UID: str, GID: str):
    if GID.startswith('U'): return await line_bot_api.get_profile_async(UID)
    elif GID.startswith('C'): return await line_bot_api.get_group_member_profile_async(GID, UID)
    elif GID.startswith('R'): return await line_bot_api.get_room_member_profile_async(GID, UID)


if __name__ == "__main__":
    # waitress-serve --host 0.0.0.0 --port $PORT app:app
    # debug only
    app.run(host='0.0.0.0', port=conf['bot']['port'], debug=True)
