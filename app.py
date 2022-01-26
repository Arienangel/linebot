import json
import re

from flask import Flask, abort, request

import message_db, game
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MemberJoinedEvent, MessageEvent, TextSendMessage

with open('config.json', encoding='utf-8') as f:
    cfg = json.load(f)
line_bot_api = LineBotApi(cfg['channel_access_token'])
handler = WebhookHandler(cfg['channel_secret'])
port = cfg['port']

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
        if event.message.type == 'text':
            text = event.message.text
            if re.match('^\/stat', text):
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
                if len(args)==1: args=1
                else: args=args[1]
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
    finally:
        message_db.save(event, line_bot_api)


@handler.add(MemberJoinedEvent)
def greeting(event: MemberJoinedEvent):
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text='喵~', notification_disabled=True))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, debug=False)
