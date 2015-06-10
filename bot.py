import importlib
import inspect
import tornado
import asyncio
import requests
import logging
import websockets
import json
import motorengine as me
from pprint import pprint
from tornado.platform.asyncio import AsyncIOMainLoop
from tornado import gen

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
            yield from self.handle_message(event)

    @asyncio.coroutine
    def handle_message(self, event):
        pass


class SlackUser(object):

    def __init__(self, data, connection):
        self.data = data
        self.id = data['id']
        self.connection = connection
        self.im_channel = connection.find_im_channel(self.id)

    @asyncio.coroutine
    def send_im(self, text):
        if self.im_channel is None:
            raise Exception('Unable to send IM to user %s' % self.data['name'])
        reply = {'type': 'message', 'channel': self.im_channel['id'],
                 'text': text}
        yield from self.connection.send_event(reply)


class SlackRTMConnection(object):

    def __init__(self, bot):
        self.bot = bot
        self.token = bot.config['token']
        self.api_url = 'https://slack.com/api/'
        self.event_loop = bot.event_loop
        self.last_message_id = 1

    def api_connect(self):
        print("getting rtm url")
        params = {'token': self.token}
        log.info('retrieving RTM connection URL')
        resp = requests.get(self.api_url + 'rtm.start', params)
        assert resp.status_code == 200
        data = resp.json()
        self.data = data
        # from pprint import pprint
        # pprint(self.data)
        # pprint(self.data['ims'])
        self.ims = data['ims']
        self.users = [SlackUser(user, self) for user in data['users']]
        self.user_id = data['self']['id']

        return data['url']

    def find_user(self, user_id):
        for u in self.users:
            if u.id == user_id:
                return u
        raise Exception("User %s not found" % user_id)

    def find_im_channel(self, user_id):
        for im in self.ims:
            if im['user'] == user_id:
                return im
        return None

    @asyncio.coroutine
    def receive_event(self):
        data = yield from self.socket.recv()
        return json.loads(data)

    @asyncio.coroutine
    def send_event(self, msg):
        msg = msg.copy()
        msg['id'] = self.last_message_id
        self.last_message_id += 1
        yield from self.socket.send(json.dumps(msg))

    @asyncio.coroutine
    def handle_message(self, msg):
        if msg['user'] == self.data['self']['id']:
            return
        user = self.find_user(msg['user'])
        if msg['channel'][0] == 'D':
            # Direct message
            if msg['text'].strip().lower() == 'ping':
                yield from user.send_im('pong')

    @asyncio.coroutine
    def handle_im_created(self, msg):
        self.ims.append(msg['channel'])

    @asyncio.coroutine
    def connect(self):
        rtm_url = yield from self.event_loop.run_in_executor(None, self.api_connect)
        log.info('connecting to %s' % rtm_url)
        self.socket = yield from websockets.connect(rtm_url)
        hello = yield from self.receive_event()
        assert hello['type'] == 'hello'

    @asyncio.coroutine
    def poll(self):
        while True:
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

class Bot(object):

    def __init__(self, event_loop, config):
        self.config = config
        self.event_loop = event_loop
        self.rtm_connection = SlackRTMConnection(self)

    @asyncio.coroutine
    def run(self):
        yield from self.rtm_connection.connect()

        implants = self.config.get('implants', {})
        self.implants = []
        for im_name, im_info in implants.items():
            if not im_info.get('enabled', False):
                continue
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
            self.implants.append(implant)

        yield from self.rtm_connection.poll()

    @asyncio.coroutine
    def handle_slack_event(self, event):
        for im in self.implants:
            yield from im.handle_slack_event(event)


# class WorkLog(me.Document):
#     username = me.StringField(required=True, unique=True)

# AsyncIOMainLoop().install()
# io_loop = tornado.ioloop.IOLoop.instance()

# me.connection.connect("helbot", io_loop=io_loop)
