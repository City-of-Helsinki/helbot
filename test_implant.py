import yaml
import asyncio
import sys

from bot import Bot


with open('config.yml', 'r') as yml_file:
    config = yaml.load(yml_file)

event_loop = asyncio.get_event_loop()
bot = Bot(event_loop, config)

for implant in bot.implants:
    if implant.name == sys.argv[1]:
        break
else:
    raise Exception("Implant %s not found" % sys.argv[1])

if not hasattr(implant, 'test'):
    raise Exception("Implant doesn't implement a 'test' method")

implant.test()
