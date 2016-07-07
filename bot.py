import importlib
import inspect
import tornado
import asyncio
import requests
import logging
import websockets
import json
import sys
import motorengine as me
from datetime import datetime, timedelta
from pprint import pprint
from tornado.platform.asyncio import AsyncIOMainLoop


logging.basicConfig(stream=sys.stdout, level=logging.INFO)

log = logging.getLogger(__name__)


class BotImplant(object):

    def __init__(self, bot, config):
        self.config = config
        self.bot = bot
        self.rtm = bot.rtm_connection

    @asyncio.coroutine
    def start(self):
        pass

    @asyncio.coroutine
    def handle_slack_event(self, event):
        if 'type' not in event:
            return
        if event['type'] == 'message':
            user_id = event.get('user')
            # If the event is sent by me, don't handle it.
            if user_id == self.rtm.user_id:
                return
            if event.get('subtype') == 'message_changed':
                yield from self.handle_message_changed(event)
            elif event.get('subtype') == 'message_deleted':
                yield from self.handle_message_deleted(event)
            else:
                yield from self.handle_message(event)

    @asyncio.coroutine
    def handle_message(self, event):
        pass

    @asyncio.coroutine
    def handle_message_changed(self, event):
        pass

    @asyncio.coroutine
    def handle_message_deleted(self, event):
        pass

    @asyncio.coroutine
    def handle_im(self, event):
        pass

    @asyncio.coroutine
    def handle_mention(self, event):
        pass

    def stop(self):
        pass

class SlackUser(object):

    def __init__(self, data, connection):
        self.data = data
        for attr, val in data.items():
            setattr(self, attr, val)
        self.connection = connection
        # This gets populated when channels are initialized.
        self.im_channel = None

    @asyncio.coroutine
    def send_message(self, text):
        if self.im_channel is None:
            raise Exception('Unable to send IM to user %s' % self.data['name'])
        yield from self.im_channel.send_message(text)


class SlackChannel(object):
    user_id = None
    name = None
    id = None

    def __init__(self, data, connection):
        self.data = data
        for attr, val in data.items():
            if attr == 'user':
                attr = 'user_id'
            setattr(self, attr, val)
        self.connection = connection

        if self.get_type() == 'im':
            self.user = self.connection.find_user(self.user_id)
            self.user.im_channel = self

    def get_type(self):
        for type_name in ('im', 'group', 'channel'):
            if getattr(self, 'is_' + type_name, False):
                return type_name
        raise Exception("Invalid type for channel %s" % self.name)

    @asyncio.coroutine
    def send_message(self, text):
        msg = {'type': 'message', 'channel': self.id, 'text': text}
        yield from self.connection.send_event(msg)


class SlackMessage(object):

    def __init__(self, data, connection):
        self.data = data
        self.text = data['text']
        self.user = connection.find_user(data['user'])


class SlackRTMConnection(object):
    data = None
    users = {}
    channels = {}
    user_id = None
    socket = None

    def __init__(self, bot):
        self.bot = bot
        self.token = bot.config['token']
        self.api_url = 'https://slack.com/api/'
        self.event_loop = bot.event_loop
        self.last_message_id = 1
        self.last_connection_attempt = None
        self.alive = False

    def api_connect(self):
        params = {'token': self.token}
        log.info('retrieving RTM connection URL')
        resp = requests.get(self.api_url + 'rtm.start', params)
        assert resp.status_code == 200
        data = resp.json()
        self.data = data
        # pprint(self.data['ims'])
        all_channels = data['channels'] + data['ims'] + data['groups']
        self.users = {user['id']: SlackUser(user, self) for user in data['users']}
        self.channels = {ch['id']: SlackChannel(ch, self) for ch in all_channels}
        self.user_id = data['self']['id']

        return data['url']

    def find_user(self, user_id):
        return self.users.get(user_id)

    def find_user_by_name(self, name):
        for user in self.users.values():
            if user.name == name:
                return user
        return None

    def find_channel_by_name(self, name):
        for ch in self.channels.values():
            if ch.name == name:
                return ch
        return None

    def find_channel(self, channel_id):
        return self.channels.get(channel_id)

    @asyncio.coroutine
    def receive_event(self):
        try:
            data = yield from self.socket.recv()
        except websockets.exceptions.ConnectionClosed:
            return None
        if data is None:
            return None
        return json.loads(data)

    @asyncio.coroutine
    def send_event(self, msg):
        if not self.socket.open:
            return False
        msg = msg.copy()
        msg['id'] = self.last_message_id
        self.last_message_id += 1
        yield from self.socket.send(json.dumps(msg))

    @asyncio.coroutine
    def handle_im_created(self, msg):
        channel = SlackChannel(msg['channel'], self)
        self.channels[channel.id] = channel

    @asyncio.coroutine
    def connect(self):
        if self.last_connection_attempt:
            now = datetime.now()
            if now - self.last_connection_attempt < timedelta(seconds=10):
                print("Sleeping for 10 seconds")
                yield from asyncio.sleep(10)
        self.last_connection_attempt = datetime.now()

        rtm_url = yield from self.event_loop.run_in_executor(None, self.api_connect)
        log.info('connecting to %s' % rtm_url)
        self.socket = yield from websockets.connect(rtm_url)
        hello = yield from self.receive_event()
        assert hello['type'] == 'hello'

        self.alive = True

    @asyncio.coroutine
    def poll(self):
        while self.alive:
            event = yield from self.receive_event()
            if event is None:
                break
            print(event)

            # First handle Slack system events
            event_type = event.get('type')
            if event_type == 'im_created':
                yield from self.handle_im_created(event)

            # Then pass the event to the bot
            yield from self.bot.handle_slack_event(event)

    @asyncio.coroutine
    def close(self):
        yield from self.socket.close()


class Bot(object):

    def __init__(self, event_loop, config):
        self.config = config
        self.event_loop = event_loop
        self.rtm_connection = SlackRTMConnection(self)

        implants = self.config.get('implants', {})
        self.implants = []
        for im_name, im_info in implants.items():
            mod_name = "implants.{}".format(im_name)
            mod = importlib.import_module(mod_name)
            for name, klass in inspect.getmembers(mod):
                if not hasattr(klass, '__bases__'):
                    continue
                if BotImplant in klass.__bases__:
                    break
            else:
                raise Exception("Implant %s did not provide a BotImplant subclass" % im_name)

            implant = klass(self, im_info)
            implant.name = im_name
            self.implants.append(implant)

    def connect_to_mongo(self):
        mongo_config = self.config.get('mongo', {})
        database = mongo_config.get('database', 'helbot')

        AsyncIOMainLoop().install()
        io_loop = tornado.ioloop.IOLoop.instance()
        me.connection.connect(database, io_loop=io_loop)

    @asyncio.coroutine
    def run(self):
        self.connect_to_mongo()
        self.alive = True
        while self.alive:
            yield from self.rtm_connection.connect()
            for im in self.implants:
                yield from im.start()
            yield from self.rtm_connection.poll()

    @asyncio.coroutine
    def handle_slack_event(self, event):
        for im in self.implants:
            yield from im.handle_slack_event(event)

    @asyncio.coroutine
    def stop(self):
        self.alive = False
        for im in self.implants:
            im.stop()
        yield from self.rtm_connection.close()
