import tornado
import asyncio
import requests
import logging
import websockets
import json
import yaml
import motorengine as me
from pprint import pprint
from tornado.platform.asyncio import AsyncIOMainLoop
from tornado import gen

log = logging.getLogger(__name__)

with open('config.yml', 'r') as yml_file:
    config = yaml.load(yml_file)


class WorkLog(me.Document):
    username = me.StringField(required=True, unique=True)

AsyncIOMainLoop().install()
io_loop = tornado.ioloop.IOLoop.instance()

me.connection.connect("helbot", io_loop=io_loop)


class SlackUser(object):

    def __init__(self, data, connection):
        self.data = data
        self.id = data['id']
        self.connection = connection
        self.im_channel = connection.find_im_channel(self.id)

    @asyncio.coroutine
    def send_im(self, text):
        if self.im_channel is None:
            raise Exception('Unable to send IM to user %s' % self['name'])
        reply = {'type': 'message', 'channel': self.im_channel['id'],
                 'text': text}
        yield from self.connection.send_message(reply)


class SlackRTMConnection(object):
    def __init__(self, event_loop):
        self.token = config['token']
        self.api_url = 'https://slack.com/api/'
        self.event_loop = event_loop
        self.last_message_id = 1

    def api_connect(self):
        print("getting rtl url")
        params = {'token': self.token}
        log.info('retrieving RTM connection URL')
        resp = requests.get(self.api_url + 'rtm.start', params)
        assert resp.status_code == 200
        data = resp.json()
        self.data = data
        #from pprint import pprint
        #pprint(self.data)
        pprint(self.data['ims'])
        self.users = [SlackUser(user, self) for user in data['users']]

        return data['url']

    def find_user(self, user_id):
        for u in self.users:
            if u.id == user_id:
                return u
        raise Exception("User %s not found" % user_id)

    def find_im_channel(self, user_id):
        for im in self.data['ims']:
            if im['user'] == user_id:
                return im
        return None

    @asyncio.coroutine
    def receive_message(self):
        data = yield from self.socket.recv()
        return json.loads(data)

    @asyncio.coroutine
    def send_message(self, msg):
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
    def connect(self):
        rtm_url = yield from self.event_loop.run_in_executor(None, self.api_connect)
        log.info('connecting to %s' % rtm_url)
        self.socket = yield from websockets.connect(rtm_url)
        hello = yield from self.receive_message()
        assert hello['type'] == 'hello'
        while True:
            msg = yield from self.receive_message()
            if msg is None:
                break
            print(msg)
            if 'type' not in msg:
                continue
            if msg['type'] == 'message':
                yield from self.handle_message(msg)

if __name__ == '__main__':
    event_loop = asyncio.get_event_loop()
    rtm_connection = SlackRTMConnection(event_loop)
    #event_loop.create_task(rtm_connection.connect())
    event_loop.run_until_complete(rtm_connection.connect())
