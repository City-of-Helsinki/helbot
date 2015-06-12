import asyncio
import motorengine as me

import bot


class WorkLog(me.Document):
    origin_id = me.StringField(required=True, unique=True)
    username = me.StringField(required=True)
    time = me.DateTimeField(required=True)
    text = me.StringField(required=True)


class WorkLogImplant(bot.BotImplant):

    @asyncio.coroutine
    def handle_message(self, msg):
        pass
