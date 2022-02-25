import json
import logging
import os
import re
import threading
from distutils.util import strtobool

from dotenv import load_dotenv
from flask import Flask, abort, request

import game
import message_db
import reply
import scoreboard
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MemberJoinedEvent, MessageEvent, TextSendMessage

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

load_dotenv('config.env')

line_bot_api = LineBotApi(os.getenv('channel_access_token'))
port = int(os.getenv('port'))
handler = WebhookHandler(os.getenv('channel_secret'))
banned = json.loads(os.getenv("banned"))
allow_push= json.loads(os.getenv("allow_push"))

app = Flask(__name__)


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
    # save message
    threading.Thread(target=message_db.save, args=[event, line_bot_api]).start()
    # id & chech banned
    try:
        if event.source.type == "user":
            id = event.source.user_id
            if id in banned["user"]: raise PermissionError
        elif event.source.type == "group":
            id = event.source.group_id
            if event.source.user_id in banned["user"]: raise PermissionError
            if id in banned["group"]: raise PermissionError
        elif event.source.type == "room":
            id = event.source.room_id
            if event.source.user_id in banned["user"]: raise PermissionError
            if id in banned["room"]: raise PermissionError
    except PermissionError:
        return 0

    if event.message.type == 'text':
        text: str = event.message.text

        # reply
        def auto_reply(id, text):
            try:
                result = reply.reply(id, text)
                if result:
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=result, notification_disabled=True))
            except Exception as E:
                logger.error('Message "%s" caused error "%s"', text, E)

        # command
        def command(id, text):
            try:
                if re.match('^\/simulate', text):
                    args = text.split(maxsplit=2)
                    id = args[1]
                    text:str = args[2]
                if re.match('^\/(help|\?)', text):
                    result = ("機器喵使用說明\n"
                              "/help : 使用說明\n"
                              "/stat [time_start] [time_end] (interval)\n"
                              "/chance (事項1 事項2 事項3...)\n"
                              "/fortune (事項1 事項2 事項3...)\n"
                              "/dice\n"
                              "/pick [選項1] (選項2 選項3...)\n"
                              "/string (長度) (0:數字,1:小寫,2:大寫,3:符號) (數量) ex: /string 8 012 3\n"
                              "/reply\n"
                              "    add [input] [output]\n"
                              "    del [input1] (input2...)\n"
                              "    reset\n"
                              "/scoreboard or /sb\n"
                              "    (@name) (object) ((+/-/)point)\n"
                              "    del [name] (object)\n"
                              "    reset\n")
                    result += reply.help(id)
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=result, notification_disabled=True))
                elif re.match('^\/push', text):
                    if event.source.user_id in allow_push:
                        args = text.split(maxsplit=2)
                        line_bot_api.push_message(args[1], TextSendMessage(text=args[2], notification_disabled=True))                    
                elif re.match('^\/stat', text):
                    args = text.split()[1:]
                    result = message_db.count(id, *args)
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=result, notification_disabled=True))
                elif re.match('^\/(scoreboard|sb)', text):
                    L = text.split()
                    if len(L) == 1:
                        result = scoreboard.get(id)
                        result = f'List of scoreboards: ' + ', '.join([i[0] for i in result])
                        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=result, notification_disabled=True))
                    elif L[1][0] == '@':
                        name = L[1].removeprefix('@')
                        if len(L) == 2 or len(L) == 3:
                            result = scoreboard.get(id, name, *L[2:])
                            result = f'Scoreboard: {name}\n' + '\n'.join([f'{i}: {j}' for i, j in result])
                            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=result, notification_disabled=True))
                        elif len(L) == 4:
                            if L[3][0] == '+':
                                scoreboard.edit(id, name, L[2], L[3], '+')
                            elif L[3][0] == '-':
                                scoreboard.edit(id, name, L[2], L[3], '-')
                            elif re.match('^\d', L[3]):
                                scoreboard.edit(id, name, L[2], L[3], 'edit')
                    elif L[1] == "del":
                        if L[2][0] == '@': L[2].removeprefix('@')
                        scoreboard.delete(id, *L[2:])
                    elif L[1] == 'reset':
                        scoreboard.reset(id)
                elif re.match('^\/chance', text):
                    args = text.split()[1:]
                    result = game.chance(*args)
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=result, notification_disabled=True))
                elif re.match('^\/fortune', text):
                    args = text.split()[1:]
                    result = game.fortune(*args)
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=result, notification_disabled=True))
                elif re.match('^\/dice', text):
                    result = game.dice(1)
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=result, notification_disabled=True))
                elif re.match('^\/pick', text):
                    args = text.split()[1:]
                    result = game.pick(*args)
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=result, notification_disabled=True))
                elif re.match('^\/string', text):
                    args = text.split()[1:]
                    result = game.randstr(*args)
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=result, notification_disabled=True))
                elif re.match('^\/reply', text):
                    L = text.split()
                    if L[1] == "add":
                        reply.add(id, L[2], L[3])
                    elif L[1] == "del":
                        for i in L[2:]:
                            reply.delete(id, i)
                    elif L[1] == 'reset':
                        reply.reset(id)
                    elif L[1] == 'json':
                        reply.add_json(id, text.removeprefix('/reply json'))
            except Exception as E:
                logger.error('Message "%s" caused error "%s"', text, E)

        threading.Thread(target=auto_reply, args=[id, text]).start()
        threading.Thread(target=command, args=[id, text]).start()


@handler.add(MemberJoinedEvent)
def greeting(event: MemberJoinedEvent):
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text='喵~', notification_disabled=True))


if __name__ == "__main__":
    with_ngrok = strtobool(os.getenv("with_ngrok"))
    if with_ngrok:
        from pyngrok import ngrok
        ngrok.set_auth_token(os.getenv("authtoken"))
        tunnel = ngrok.connect(port, 'http')
        print(tunnel.public_url)
    debug = strtobool(os.getenv("debug"))
    app.run(host='0.0.0.0', port=port, debug=debug)
