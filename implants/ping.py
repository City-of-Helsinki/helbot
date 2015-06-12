import asyncio
import bot


class PingImplant(bot.BotImplant):

    @asyncio.coroutine
    def handle_message(self, msg):
        if 'user' not in msg:
            return False
        if msg['user'] == self.rtm.user_id:
            return False
        user = self.rtm.find_user(msg['user'])
        if msg['channel'][0] == 'D':
            # Direct message
            if msg['text'].strip().lower() == 'ping':
                yield from user.send_message('pong')
                return True
        else:
            # Mentions me?
            mention_text = '<@{}>'.format(self.rtm.user_id)
            if not msg['text'].startswith(mention_text):
                return False
            text = msg['text'].replace(mention_text, '', 1)
            if text.strip().lower() == 'jou':
                reply = {'text': '<@{}> jou jou'.format(msg['user']),
                         'type': 'message', 'channel': msg['channel']}
                yield from self.rtm.send_event(reply)
                return True
