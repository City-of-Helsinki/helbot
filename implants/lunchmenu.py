import asyncio
import bot
import datetime
from implants import lunch_lib

class LunchMenuImplant(bot.BotImplant):
    @asyncio.coroutine
    def handle_message(self, msg):
        if msg['text'] == 'lounas':
            structure = yield from self.bot.event_loop.run_in_executor(None, lunch_lib.get_weekly_menu)
            weekday = datetime.datetime.now().weekday()
            weekdays = list(structure.get('menu').values())
            text = "{title} {period}\n\n{dishes}".format(
                title=structure.get('restaurant'),
                period=structure.get('period'),
                dishes=lunch_lib.format_message(weekdays[weekday])
            )
            yield from self.rtm.send_event({
                'type': 'message',
                'channel': msg['channel'],
                'text': text
            })
