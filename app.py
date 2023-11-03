import os
import re

import aiofiles
import aiosqlite
import aiohttp
import dateutil.parser
import dateutil.relativedelta
import urllib.parse
import yaml
from flask import Flask, abort, request
from pyquery import PyQuery as pq

import chatgpt
import games
from aiolinebot_handler import AsyncWebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import AsyncApiClient, AsyncMessagingApi, AsyncMessagingApiBlob, Configuration, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, MemberJoinedEvent

with open('config/app.yaml', encoding='utf-8') as f:
    conf = yaml.load(f, yaml.SafeLoader)['app']

app = Flask(__name__)
configuration = Configuration(access_token=conf['bot']['channel_access_token'])
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
        # check forbidden words
        for kw in conf['command']['blacklist']:
            if kw in event.message.text: break

        # check disabled commands
        cmd = event.message.text.split(' ', maxsplit=1)[0]
        if cmd in conf['command']['disabled']: return

        match cmd:
            case '/help':
                await line_bot_api.reply_message(ReplyMessageRequest(replyToken=event.reply_token, messages=[TextMessage(text=conf['command']['help']['message'])]))

            case '/gpt':
                ctx = event.message.text.split(' ', maxsplit=1)[1]
                gpt, temp = await chatgpt.gpt35(ctx, conf['command']['gpt']['temperature'])
                await line_bot_api.reply_message(ReplyMessageRequest(replyToken=event.reply_token, messages=[TextMessage(text=f'{gpt.choices[0].message.content}')]))

            case '/chance':
                ctx = event.message.text.split(' ', maxsplit=1)
                await line_bot_api.reply_message(ReplyMessageRequest(replyToken=event.reply_token, messages=[TextMessage(text=f'{ctx[-1] if len(ctx)>1 else "機率"}: {round(games.chance(), 2):.0%}')]))

            case '/dice':
                n = re.search(r'\d+', event.message.text)
                if (n is None) and (event.message.text == '/dice'): n = 6
                else:
                    n = int(n.group(0))
                    if n <= 1: return
                await line_bot_api.reply_message(ReplyMessageRequest(replyToken=event.reply_token, messages=[TextMessage(text=f'{games.dice(n)}')]))

            case '/fortune':
                ctx = event.message.text.split(' ', maxsplit=1)
                await line_bot_api.reply_message(ReplyMessageRequest(replyToken=event.reply_token, messages=[TextMessage(text=f'{ctx[-1] if len(ctx)>1 else "運勢"}: {games.fortune()}')]))

            case '/pick':
                ctx = event.message.text.split(' ')
                if len(ctx) > 1:
                    await line_bot_api.reply_message(ReplyMessageRequest(replyToken=event.reply_token, messages=[TextMessage(text=f'選擇: {games.pick(list(ctx[1:]))}')]))

            case '/fbid':
                async with aiohttp.ClientSession() as session:
                    ctx = event.message.text.split(' ', maxsplit=1)[1]
                    async with session.get(f'https://www.facebook.com/plugins/post.php?href={urllib.parse.quote_plus(ctx)}') as response:
                        s = pq(await response.text())
                        url = s('a._39g5').attr('href')
                        if not url:
                            url = s('a._2q21').attr('href')
                        if url:
                            if 'permalink.php?story_fbid=' in url:
                                post, page = re.search(r'/permalink.php\?story_fbid=(\d+)&id=(\d+)', url).group(1, 2)
                                await line_bot_api.reply_message(ReplyMessageRequest(replyToken=event.reply_token, messages=[TextMessage(text=f"https://www.facebook.com/{page}/posts/{post}")]))
                            else:
                                await line_bot_api.reply_message(ReplyMessageRequest(replyToken=event.reply_token, messages=[TextMessage(text=f"https://www.facebook.com{url.split('?')[0]}")]))
                        else:
                            await line_bot_api.reply_message(ReplyMessageRequest(replyToken=event.reply_token, messages=[TextMessage(text="Not found")]))

            case '/echo':
                ctx = event.message.text.split(' ', maxsplit=2)[1:]
                async with aiosqlite.connect('data/echo.db') as db:
                    await db.execute(f'CREATE TABLE IF NOT EXISTS  `{GID}` ("request" UNIQUE, "response");')
                    await db.commit()
                    subcmd = event.message.text.split(' ', maxsplit=2)[1]
                    match subcmd:
                        case 'ls':
                            async with db.execute(f'SELECT * FROM `{GID}`;') as cur:
                                L = [f'{row[0]} -> {row[1]}' async for row in cur]
                            if len(L) > 0: await line_bot_api.reply_message(ReplyMessageRequest(replyToken=event.reply_token, messages=[TextMessage(text='echo: \n' + '\n'.join(L))]))
                            else: await line_bot_api.reply_message(ReplyMessageRequest(replyToken=event.reply_token, messages=[TextMessage(text='echo: None')]))

                        case 'add':
                            _, _, req, res = event.message.text.split(' ', maxsplit=3)
                            if req.startswith('/'):
                                await line_bot_api.reply_message(ReplyMessageRequest(replyToken=event.reply_token, messages=[TextMessage(text='不可以使用"/"開頭')]))
                            else:
                                await db.execute(f'INSERT OR REPLACE INTO `{GID}` VALUES (?, ?);', [req, res])
                                await db.commit()

                        case 'rm':
                            for x in event.message.text.split(' ')[2:]:
                                await db.execute(f' DELETE FROM `{GID}` WHERE request=?;', [x])
                            await db.commit()

                        case 'reset':
                            await db.execute(f' DELETE FROM `{GID}`;')
                            await db.commit()

            case '/stat':
                _, start, end, *_ = event.message.text.split(' ', maxsplit=3)
                start = dateutil.parser.parse(start)
                end = dateutil.parser.parse(end)
                L = list()
                async with aiosqlite.connect(f'data/messages.db') as db:
                    async with db.execute(f'SELECT user, COUNT(*) FROM `{GID}` WHERE time>={int(start.timestamp())*1000} and time<{int(end.timestamp())*1000}  GROUP BY user  ORDER BY  2 DESC;') as cur:
                        i = 1
                        async for row in cur:
                            try:
                                profile = await get_user_profile(row[0], GID)
                                name = getattr(profile, "display_name", row[0])
                                L.append(f'({i}) {name}: {row[1]}')
                                i += 1
                            except:
                                continue
                text = f'Start: {start.strftime("%Y/%m/%d %H:%M:%S")}' + '\n' + f'End: {end.strftime("%Y/%m/%d %H:%M:%S")}\n'
                if L:
                    await line_bot_api.reply_message(ReplyMessageRequest(replyToken=event.reply_token, messages=[TextMessage(text=text + '\n'.join(L))]))
                else:
                    await line_bot_api.reply_message(ReplyMessageRequest(replyToken=event.reply_token, messages=[TextMessage(text=text + 'None')]))

    async def echo():
        async with aiosqlite.connect('data/echo.db') as db:
            await db.execute(f'CREATE TABLE IF NOT EXISTS  `{GID}` ("request" UNIQUE, "response");')
            await db.commit()
            async with db.execute(f'SELECT response FROM `{GID}` WHERE request=?;', [event.message.text]) as cur:
                L = await cur.fetchone()
            if L: await line_bot_api.reply_message(ReplyMessageRequest(replyToken=event.reply_token, messages=[TextMessage(text=L[0])]))

    async def record_message():

        async def download():
            folder = f'data/attachment/{GID}'
            os.makedirs(folder, exist_ok=True)
            try:
                api_blob = AsyncMessagingApiBlob(client)
                data = await api_blob.get_message_content_with_http_info(event.message.id)
                if hasattr(event.message, 'file_name'):
                    ext = '.' + event.message.file_name.rsplit('.', maxsplit=1)[-1]
                elif data.headers['Content-Type']:
                    ext = '.' + data.headers['Content-Type'].split('/')[1]
                else:
                    ext = ''
                async with aiofiles.open(f'{folder}/{event.message.id}{ext}', mode='wb') as f:
                    await f.write(data.data)
            except Exception as E:
                pass

        content = None
        if event.message.type == 'text':
            if conf['record_message']['text']: content = event.message.text
        elif event.message.type == 'sticker': content = event.message.sticker_id
        elif event.message.type in ['image', 'video', 'audio']:
            if event.message.content_provider.type == 'line':
                if conf['record_message']['download']: await download()
        elif event.message.type == 'file':
            if conf['record_message']['download']: await download()
        async with aiosqlite.connect(f'data/messages.db') as db:
            await db.execute(f'CREATE TABLE IF NOT EXISTS `{GID}` (id, time, user, type, content);')
            await db.execute(f'INSERT INTO `{GID}` VALUES (?,?,?,?,?);', [event.message.id, event.timestamp, event.source.user_id, event.message.type, content])
            await db.commit()

    async with AsyncApiClient(configuration) as client:
        line_bot_api = AsyncMessagingApi(client)
        GID = event.source.group_id if event.source.type == 'group' else event.source.room_id if event.source.type == 'room' else event.source.user_id
        await record_message()
        if event.message.type == 'text':
            if event.message.text.startswith('/'):  # command
                await command()
            else:
                await echo()


@handler.add(MemberJoinedEvent)
async def greeting(event: MemberJoinedEvent):
    async with AsyncApiClient(configuration) as client:
        line_bot_api = AsyncMessagingApi(client)
        await line_bot_api.reply_message(ReplyMessageRequest(replyToken=event.reply_token, messages=[TextMessage(text='喵~', notification_disabled=True)]))


async def get_user_profile(UID: str, GID: str):
    async with AsyncApiClient(configuration) as client:
        line_bot_api = AsyncMessagingApi(client)
        if GID.startswith('U'): return await line_bot_api.get_profile(UID)
        elif GID.startswith('C'): return await line_bot_api.get_group_member_profile(GID, UID)
        elif GID.startswith('R'): return await line_bot_api.get_room_member_profile(GID, UID)


if __name__ == "__main__":
    # waitress-serve --host 0.0.0.0 --port $PORT app:app
    # debug only
    app.run(host='0.0.0.0', port=conf['bot']['port'], debug=True)
