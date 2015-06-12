from datetime import datetime
import requests
import motorengine as me
import asyncio
from tornado.platform.asyncio import to_asyncio_future as to_aio

import bot

import requests_cache

class HackerNewsStory(me.Document):
    id = me.StringField(unique=True)
    time = me.DateTimeField()


class HackerNewsImplant(bot.BotImplant):
    URL_BASE = 'https://hacker-news.firebaseio.com/v0/'

    @asyncio.coroutine
    def async_get_json(self, url):
        resp = yield from self.bot.event_loop.run_in_executor(None, requests.get, url)
        return resp.json()

    @asyncio.coroutine
    def announce_new_story(self, item):
        # Check if we've already announced the item.
        story = HackerNewsStory
        user = self.rtm.find_user_by_name('jey')
        text = '\n'.join([item['title'], item['url']])
        yield from user.send_message(text)

    @asyncio.coroutine
    def run(self):
        nr_top_stories = 30
        sleep_per_story = 5 * 60 / nr_top_stories
        while True:
            url = self.URL_BASE + 'topstories.json'
            top_stories = yield from self.async_get_json(url)
            # Go through the full list every 5 mins
            slept = 0
            for item_nr in top_stories[0:nr_top_stories]:
                item_nr = str(item_nr)
                # If we have already announced the story, do not even
                # bother fetching it.
                count = yield from to_aio(HackerNewsStory.objects.filter(id=item_nr).count())
                if count:
                    continue

                url = self.URL_BASE + 'item/%s.json' % item_nr
                item = yield from self.async_get_json(url)
                if item['score'] < 100:
                    yield from asyncio.sleep(sleep_per_story)
                    slept += 1
                    continue
                yield from self.announce_new_story(item)
                story = HackerNewsStory(id=str(item['id']), time=datetime.fromtimestamp(item['time']))
                yield from to_aio(story.save())

                yield from asyncio.sleep(sleep_per_story)
                slept += 1

            if slept < nr_top_stories:
                yield from asyncio.sleep((nr_top_stories - slept) * sleep_per_story)

    @asyncio.coroutine
    def start(self):
        self.task = self.bot.event_loop.create_task(self.run())
