import json
import re

from flask import Flask, abort, request

import message_db
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (JoinEvent, MemberJoinedEvent, MessageEvent, TextSendMessage)

with open('config.json') as f:
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
        if event.message.type=='text':
            text=event.message.text
            if re.match('^\/stat', text):
                L=text.split()[1:]
                if event.source.type == "group":
                    db="db/group.db"
                    dbid = event.source.group_id
                elif event.source.type == "user":
                    db="db/user.db"
                    dbid = event.source.user_id
                result=message_db.count(db, dbid, *L)
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=result, notification_disabled=True))
            elif re.match('^(\/喵|\/meow)' ,text):
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text='喵~', notification_disabled=True))
            elif re.match('^(\/help)' ,text):
                text='''\
                    /help
                    /meow
                    /stat [time_start] [time_end] [interval(D)]'''
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=text, notification_disabled=True))
    finally:
        message_db.save(event, line_bot_api)


@handler.add(MemberJoinedEvent)
def greeting(event: MemberJoinedEvent):
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text='喵~', notification_disabled=True))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, debug=False)
