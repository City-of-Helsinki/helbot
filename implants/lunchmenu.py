import asyncio
import bot
import requests
import datetime
from collections import OrderedDict as odict
from bs4 import BeautifulSoup

URL = "http://www.hel.fi/wps/portal/!ut/p/b1/04_Sj9CPykssy0xPLMnMz0vMAfGjzOItLAMMfQ3NzMycTA2dDDxDTN1CjF29jQwsDIEKIoEKDHAARwNC-sP1o8BKDNwNHH38jFxCXQy8Df0d_UMCjKFmoCjwdDF0MfD08PEw8HQ2QFOA2w1-Hvm5qfoFuREGmQHpigAlFdsk/dl4/d5/L2dBISEvZ0FBIS9nQSEh/pw/Z7_U8VOVTAQ2R9RD0A06UA92804P4/act/id=0/p=spf_ActionName=spf_ActionListener/p=spf_strutsAction=QCB2fmenu.do/295201690613/-/#Z7_U8VOVTAQ2R9RD0A06UA92804P4"
payload = {'type':'1', 'id':'48', 'submit': 'Hae'}

def get_weekly_menu():
    r = requests.post(URL, data=payload)
    soup = BeautifulSoup(r.text)
    titles = soup.find_all('div', class_='title')
    menu_table = soup.find_all('table', class_='menu_table')
    children = list(titles[0].children)
    def clean(t):
        return t.strip(' -')
    structure = odict([
        ('restaurant', clean(children[0].text)),
        ('period', clean(children[1])),
        ('menu', odict())])

    menu = structure.get('menu')
    for tr in menu_table[0].find_all('tr'):
        for td in tr.find_all('td'):
            classes = td.attrs.get('class')
            if classes is None:
                continue
            if 'day' in classes:
                day_name = td.h4.text
                day = []
                menu[day_name] = day
            if 'meal' in classes:
                meal = {'name': clean(td.text)}
                day.append(meal)
            if 'price' in classes:
                price = td.text
                if price and len(price):
                    meal['price'] = price + "€"
                else:
                    meal['price'] = None
    return structure

class LunchMenuImplant(bot.BotImplant):
    @asyncio.coroutine
    def handle_message(self, msg):
        if msg['text'] == 'lounas':
            structure = yield from self.bot.event_loop.run_in_executor(None, get_weekly_menu)
            weekday = datetime.datetime.now().weekday()
            weekdays = list(structure.get('menu').values())
            text = "{title} {period}\n{dishes}".format(
                title=structure.get('restaurant'),
                period=structure.get('period'),
                dishes=weekdays[weekday]
            )
            yield from self.rtm.send_event({
                'type': 'message',
                'channel': msg['channel'],
                'text': text
            })

if __name__ == '__main__':
    import pprint
    pprint.pprint(get_weekly_menu())
