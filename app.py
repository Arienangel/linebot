import json
import re
import logging

from pyngrok import ngrok
from flask import Flask, abort, request

import message_db, game, reply
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MemberJoinedEvent, MessageEvent, TextSendMessage

with open('config.json', encoding='utf-8') as f:
    cfg = json.load(f)
    debug = cfg["debug"]
with_ngrok = cfg["with_ngrok"]
authtoken = cfg["authtoken"]
line_bot_api = LineBotApi(cfg['channel_access_token'])
port = cfg['port']
handler = WebhookHandler(cfg['channel_secret'])
banned = cfg["banned"]

logging.basicConfig(level=logging.ERROR)
logger=logging.getLogger(__name__)
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
    try:
        # id & chech banned
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
            
        if event.message.type == 'text':
            text: str = event.message.text
            #command
            try:
                if re.match('^\/help', text):
                    result = ("機器喵使用說明\n"
                            "/help : 使用說明\n"
                            "/stat [time_start] [time_end] [interval(D)]\n"
                            "/chance (事項1 事項2 事項3...)\n"
                            "/fortune (事項1 事項2 事項3...)\n"
                            "/dice (次數)\n"
                            "/pick [選項1] (選項2 選項3...)\n"
                            "/string (長度) (0:數字,1:小寫,2:大寫,3:符號) (數量) ex: /string 8 012 3\n"
                            "/reply add [input] [output]\n"
                            "/reply edit [input] [output]\n"
                            "/reply del [input] (input2...)\n"
                            "/reply reset\n")
                    result += reply.help(id)
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=result, notification_disabled=True))
                elif re.match('^\/stat', text):
                    args = text.split()[1:]
                    result = message_db.count(event, *args)
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=result, notification_disabled=True))
                elif re.match('^\/chance', text):
                    args = text.split()[1:]
                    result = game.chance(*args)
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=result, notification_disabled=True))
                elif re.match('^\/fortune', text):
                    args = text.split()[1:]
                    result = game.fortune(*args)
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=result, notification_disabled=True))
                elif re.match('^\/dice', text):
                    args = text.split()
                    if len(args) == 1: args = 1
                    else: args = args[1]
                    result = game.dice(args)
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
                        reply.add(L[2], L[3], id)
                    elif L[1] == "edit":
                        reply.edit(L[2], L[3], id)
                    elif L[1] == "del":
                        for i in L[2:]:
                            reply.delete(i, id)
                    elif L[1] == 'reset':
                        reply.reset(id)
                    elif L[1] == 'json':
                        reply.add_json(text.removeprefix('/reply json'), id)
            except Exception as E:
                logger.error('Message "%s" caused error "%s"', text, E)

            # auto reply
            try:
                result = reply.reply(text, id)
                if result:
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=result, notification_disabled=True))
            except Exception as E:
                logger.error('Message "%s" caused error "%s"', text, E)
                
    except PermissionError:
        pass
    finally:
        message_db.save(event, line_bot_api)


@handler.add(MemberJoinedEvent)
def greeting(event: MemberJoinedEvent):
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text='喵~', notification_disabled=True))


if __name__ == "__main__":
    if with_ngrok:
        ngrok.set_auth_token(authtoken)
        tunnel = ngrok.connect(port, 'http')
        print(tunnel.public_url)
    app.run(host='0.0.0.0', port=port, debug=debug)
