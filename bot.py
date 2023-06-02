import os
import sys
import logging
import datetime
from base import make_session, Message, Chat, Meal, Topic, start_engine
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler
from validators import validate_period, validate_time_and_meal, validate_meal, format_period, format_time, validate_time


app = Application.builder().token(os.environ['TELEGRAM_TOKEN']).build()


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
start_engine()

log = logging.getLogger(__name__)


async def stop(update, context):
    _id = update.message.chat.id
    with make_session() as session:
        session.query(Chat).filter(Chat.id == _id).delete(synchronize_session='fetch')


app.add_handler(CommandHandler('stop', stop))


async def report(update, context):
    _id = update.message.chat.id
    now = datetime.datetime.utcnow()
    result = ''
    with make_session() as session:
        chat = session.query(Chat).filter(Chat.id == _id).one()
        for meal in chat.meals:
            if meal.time + datetime.timedelta(days=1) > now:
                result += '%d %s\n' % (meal.amount, str(meal.time))
    await update.message.reply_text(result)


app.add_handler(CommandHandler('report', report))


async def stats(update, context):
    _id = update.message.chat.id
    now = datetime.datetime.utcnow()
    maxtime = None
    sm = 0
    cnt = 0

    period_sm = 0
    with make_session() as session:
        chat = session.query(Chat).filter(Chat.id == _id).one()
        for meal in chat.meals:
            if meal.time + chat.period_time() > now:
                period_sm += meal.amount
            if meal.time + datetime.timedelta(days=1) > now:
                sm += meal.amount
                cnt += 1
            if maxtime is None or meal.time > maxtime:
                maxtime = meal.time

    delta = now - maxtime

    hour = datetime.timedelta(hours=1)
    hours = int(delta / hour)

    minute = datetime.timedelta(minutes=1)
    minutes = int((delta - hour * hours) / minute)

    await update.message.reply_text('За день кушали %d раз, суммарно выпили %dмл. За установленный период съели %dмл. Последний раз кушали %d часов %d минут назад' % (cnt, sm, period_sm, hours, minutes))


app.add_handler(CommandHandler('stats', stats))


async def stats_month(update, context):
    _id = update.message.chat.id
    now = datetime.datetime.utcnow()
    maxtime = None
    sm = 0
    cnt = 0

    period_sm = 0
    with make_session() as session:
        chat = session.query(Chat).filter(Chat.id == _id).one()
        result = [0]*31
        for meal in chat.meals:
            day = int((now - meal.time) / datetime.timedelta(days=1))
            if day < 31:
                result[day] += meal.amount
                
    resstr = ""
    for res in result[::-1]:
        resstr += str(res) + "\n"
    await update.message.reply_text(resstr)


app.add_handler(CommandHandler('stats_month', stats_month))


async def start(update, context):
    args = update.message.text.split(' ')[1:]
    if len(args) == 0:
        period = None
    elif len(args) == 1 :
        period = validate_period(args[0])

    with make_session() as session:
        _id = update.message.chat.id
        existing_users = session.query(Chat).filter(Chat.id == _id).all()
        if len(existing_users) > 0:
            existing_users[0].period = period
        else:
            session.add(Chat(id=_id, period=period, state=ChatState().store()))

    if period is not None:
        await update.message.reply_text('записала период кормления в %s' % (format_period(period),))
    else:
        await update.message.reply_text('отключила кормления в этом чате')


app.add_handler(CommandHandler('start', start))


class ChatState:
    INITIAL = 0
    TOPIC_ADD = 1

    def __init__(self, s=''):
        if s == '': # initial state
            self.state = ChatState.INITIAL
            self.topic = None
        else:
            args = s.split(' ', 1)
            self.state = int(args[0])
            self.topic = args[1] if len(args) > 1 else None

    def store(self):
        return str(self)

    def __str__(self):
        return str(self.state) + ('' if self.topic is None else ' ' + self.topic)

    def adding_meals(self):
        return self.state == ChatState.INITIAL

    def set_adding_meals(self):
        self.state = ChatState.INITIAL
        return self

    def new_topic(self):
        return self.topic is None

    def adding_topic(self):
        return self.state == ChatState.TOPIC_ADD

    def set_adding_topic(self, topic=None):
        self.topic = topic
        self.state = ChatState.TOPIC_ADD
        return self



def _topic_callback_data(action, content=''):
    return 'topic ' + action + ' ' + content


def _parse_topic_callback_data(text):
    text = text[len('topic '):]
    return text.split(' ', 1)


async def topic_callback(update, context):
    with make_session() as session:
        message = update.callback_query.message
        chat = query_chat(session, message.chat.id)
        action, content = _parse_topic_callback_data(update.callback_query.data)
        if action == 'new':
            chat.state = ChatState().set_adding_topic().store()
            await message.reply_text('что хотите записать?')
        elif action == 'close':
            for topic in chat.topics:
                if topic.id == content:
                    chat.topics.remove(topic)
                    await app.bot.send_message(chat.id, 'закрыла')
        elif action == 'add':
            chat.state = ChatState().set_adding_topic(content).store()
            await message.reply_text('записываю')
        elif action == 'forward':
            messages = session.query(Message).filter(Message.topic_id == content).filter(Message.chat_id == message.chat.id).all()
            cur_id = chat.id
            for message in messages:
                await app.bot.forward_message(chat.id, message.chat.id, message.telegram_id)
        else:
            chat.state = ChatState().store()


app.add_handler(CallbackQueryHandler(topic_callback, '^topic.*'))


async def topic(update, context):
    with make_session() as session:
        chat = query_chat(session, update.message.chat.id)

        specials = [[InlineKeyboardButton('новая тема', callback_data=_topic_callback_data('new'))]]

        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(topic.name,
                                                               callback_data=_topic_callback_data('add', topic.id))]
                                          for topic in chat.topics] + specials)
        await update.message.reply_text('в какую тему хотите написать?', reply_markup=keyboard)


app.add_handler(CommandHandler('topic', topic))


async def close_topic(update, context):
    with make_session() as session:
        chat = query_chat(session, update.message.chat.id)

        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(topic.name,
                                                       callback_data=_topic_callback_data('close', topic.id))]
                                  for topic in chat.topics])

        await update.message.reply_text('какую тему хотите закрыть?', reply_markup=keyboard)


app.add_handler(CommandHandler('close', close_topic))


async def forward_topic(update, context):
    with make_session() as session:
        chat = query_chat(session, update.message.chat.id)

        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(topic.name,
                                                       callback_data=_topic_callback_data('forward', topic.id))]
                                  for topic in chat.topics])

        await update.message.reply_text('какую тему хотите посмотреть?', reply_markup=keyboard)


app.add_handler(CommandHandler('forward', forward_topic))
app.add_handler(CommandHandler('view', forward_topic))


class ChatNotFound(Exception):
    pass


def query_chat(session, _id):
    chats = session.query(Chat).filter(Chat.id == _id).all()
    if len(chats) > 0:
        return chats[0]
    else:
        app.bot.send_message(_id, 'незарегистрированный чат #%d' % (_id,))
        raise ChatNotFound()


async def reset(update, content):
    _id = update.message.chat.id
    with make_session() as session:
        chat = query_chat(session, _id)
        chat.state = ChatState().store()
    await update.message.reply_text('готово!')


app.add_handler(CommandHandler('reset', reset))


def new_topic_id():
    import uuid
    return str(uuid.uuid4())


async def callback(update, context):
    _id = update.message.chat.id
    _text = update.message.text
    _date = update.message.date

    if _text == '.':
        await reset(update, context)
        return
    
    meal_date = _date
    meal_amount = validate_meal(_text)

    if meal_amount is None:
        meal_date, meal_amount = validate_time_and_meal(meal_date, _text)

    _period = validate_period(_text)
    _time = validate_time(_text)

    _notify = None

    with make_session() as session:
        chat = query_chat(session, _id)

        state = ChatState(chat.state)
        print('cur state = ', state)
        if state.adding_meals():
            if meal_amount is not None:
                session.add(Meal(chat_id=_id, amount=meal_amount, time=meal_date))
            _notify = 'записала кормление %d мл %s' % (meal_amount, format_time(meal_date))
        elif state.adding_topic():
            print('adding topic')
            if state.new_topic():
                print('adding new topic')
                _topic_id = new_topic_id()
                
                session.add(Topic(id=_topic_id, chat_id=_id, name=_text))
                print(_topic_id)
                chat.state = state.set_adding_topic(_topic_id).store()
                print('state', state)
                _notify = 'записываю'
            else:
                print('topic id', str(state.topic), type(state.topic))
                session.add(Message(telegram_id=update.message.message_id, chat_id=_id, topic_id=state.topic, content=_text, time=_date))

    if _notify is not None:
        await update.message.reply_text(_notify)

app.add_handler(MessageHandler(None, callback))

_muted_chats = {}

log.debug('starting polling')


async def checker(_):
    print('checking chats', file=sys.stderr)
    notifies = {}
    now = datetime.datetime.utcnow()
    with make_session() as session:
        chats = session.query(Chat)
        for chat in chats:
            if chat.period is not None:
                try:
                    print(chat, file=sys.stderr)
                    maxtime = None
                    for meal in chat.meals:
                        if maxtime is None or meal.time > maxtime:
                            maxtime = meal.time

                    if maxtime is not None and maxtime + chat.period_time() < now:
                        if chat.id in _muted_chats and _muted_chats[chat.id] > now:
                            continue
                        delta = now - meal.time
                        ratio = int(delta / datetime.timedelta(seconds=chat.period))
                        notifies[chat.id] = 'Пора кормить ребенка! Прошло больше %d периодов кормления!' % (ratio,)
                        _muted_chats[chat.id] = now + datetime.timedelta(minutes=10)
                except Exception as e:
                    print(e, file=sys.stderr)

    for key, value in notifies.items():
        print(key, value, file=sys.stderr)
        await app.bot.send_message(key, value)

app.job_queue.run_repeating(checker, 60)

app.run_polling()
