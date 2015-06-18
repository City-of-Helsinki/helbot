import asyncio
import motorengine as me
from datetime import datetime
from tornado.platform.asyncio import to_asyncio_future as to_aio

import bot


class WorkLog(me.Document):
    origin_id = me.StringField(required=True, unique=True)
    user_id = me.StringField(required=True)
    username = me.StringField(required=True)
    time = me.DateTimeField(required=True)
    text = me.StringField(required=True)
    deleted = me.BooleanField(default=False)


class WorkLogImplant(bot.BotImplant):
    channel = None

    @asyncio.coroutine
    def start(self):
        self.channel = self.rtm.find_channel_by_name(self.config['channel'])

    @asyncio.coroutine
    def handle_message(self, msg):
        if msg.get('channel') != self.channel.id:
            return

        user = self.rtm.find_user(msg['user'])
        log = WorkLog(origin_id=msg['ts'], user_id=user.id, username=user.name,
                      time=datetime.fromtimestamp(float(msg['ts'])), text=msg['text'])
        yield from to_aio(log.save())

    @asyncio.coroutine
    def handle_message_changed(self, msg):
        if msg.get('channel') != self.channel.id:
            return

        qs = WorkLog.objects.filter(origin_id=msg['message']['ts'])
        log_list = yield from to_aio(qs.find_all())
        if len(log_list) != 1:
            return
        log = log_list[0]
        log.text = msg['message']['text']
        yield from to_aio(log.save())

    @asyncio.coroutine
    def handle_message_deleted(self, msg):
        if msg.get('channel') != self.channel.id:
            return

        ts = msg['deleted_ts']
        qs = WorkLog.objects.filter(origin_id=ts)
        log_list = yield from to_aio(qs.find_all())
        if len(log_list) != 1:
            return
        log = log_list[0]
        log.deleted = True
        yield from to_aio(log.save())
