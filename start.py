import yaml
import asyncio
import logging

from bot import Bot

if __name__ == '__main__':
    with open('config.yml', 'r') as yml_file:
        config = yaml.load(yml_file)

    #logging.basicConfig(level=logging.DEBUG)

    event_loop = asyncio.get_event_loop()
    bot = Bot(event_loop, config)
    event_loop.run_until_complete(bot.run())
