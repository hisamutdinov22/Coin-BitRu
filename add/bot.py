import asyncio, logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from .config import settings
from .db import init_db, Session, Withdrawal, Task, Achievement, User
from .services import *
from .keyboards import *
from sqlalchemy import select, desc

logging.basicConfig(level=logging.INFO)
bot=Bot(settings.bot_token)
dp=Dispatcher()

def money_from_coins(c): return c/settings.coins_per_usd

def home_text(u):
    league,_=get_league(u.total_earned)
    return (f'🪙 <b>Coin BitRu</b> 🇷🇺\n\n'
            f'Баланс: <b>{u.coins:,}</b> COIN\n≈ <b>${money_from_coins(u.coins):.2f}</b>\n\n'
            f'⚡ За тап: <b>+{u.tap_level}</b> COIN\n🔋 Энергия: <b>{u.energy}/{u.max_energy}</b>\n'
            f'📈 Уровень тапа: <b>{u.tap_level}</b>\n🏅 Лига: <b>{league}</b>\n'
            f'👥 Рефералов: <b>{u.referrals}</b>\n💳 Пополнено: <b>${u.topup_usd:.2f}</b>').replace(',', ' ')

def get_league(total_earned):
    if total_earned>=100000:return 'Diamond',100000
    if total_earned>=50000:return 'Platinum',50000
    if total_earned>=20000:return 'Gold',20000
    if total_earned>=5000:return 'Silver',5000
    return 'Bronze',0

@dp.message(CommandStart())
async def start(m:Message):
    ref=None
    arg=m.text.split(maxsplit=1)[1] if len(m.text.split())>1 else ''
    if arg.startswith('ref_'):
        try: ref=int(arg[4:])
        except: pass
    u=await get_or_create_user(m.from_user,ref)
    await m.answer(home_text(u),parse_mode='HTML',reply_markup=main_kb())

@dp.message(Command('id'))
async def id_cmd(m:Message): await m.answer(f'ID: <code>{m.from_user.id}</code>',parse_mode='HTML')

@dp.callback_query(F.data=='home')
async def home(c:CallbackQuery):
    u=await restore_energy(c.from_user.id); await c.message.edit_text(home_text(u),parse_mode='HTML',reply_markup=main_kb()); await c.answer()

@dp.callback_query(F.data=='tap')
async def tap_cb(c:CallbackQuery):
    gain,u=await tap(c.from_user.id)
    if gain:
        await update_mission_progress(c.from_user.id,'taps',1)
        await refresh_achievements(c.from_user.id)
    await c.message.edit_text(home_text(u)+f'\n\n⚡ <b>+{gain}</b> COIN',parse_mode='HTML',reply_markup=main_kb()); await c.answer(f'+{gain} COIN' if gain else 'Нет энергии')

@dp.callback_query(F.data=='upgrade')
async def upgrade(c:CallbackQuery):
    u=await profile(c.from_user.id); cost=int(1000*(1.8**(u.tap_level-1)))
    text=f'⚡ <b>Улучшение тапа</b>\n\nУровень: {u.tap_level}\nЗа тап: {u.tap_level} COIN → {u.tap_level+1} COIN\nЦена: <b>{cost:,} COIN</b>'.replace(',', ' ')
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f'⬆️ Улучшить за {cost:,}'.replace(',', ' '),callback_data='upgrade:buy')],[InlineKeyboardButton(text='⬅️ Назад',callback_data='home')]])
    await c.message.edit_text(text,parse_mode='HTML',reply_markup=kb);await c.answer()

@dp.callback_query(F.data=='upgrade:buy')
async def upgrade_buy(c:CallbackQuery):
    ok,u=await upgrade_tap(c.from_user.id);await c.answer('Улучшено!' if ok else 'Недостаточно коинов',show_alert=True);await home(c)

@dp.callback_query(F.data=='daily')
async def daily(c:CallbackQuery):
    ok,u,reward=await daily_claim(c.from_user.id)
    if ok:
        await update_mission_progress(c.from_user.id,'daily',1); await refresh_achievements(c.from_user.id)
    rewards=[1000,2500,5000,7500,10000,20000,50000]
    cards=[]
    for i,r in enumerate(rewards,1): cards.append(('✅' if i<u.streak else ('🎁' if i==u.streak else '🔒'),i,r))
    txt='🎁 <b>7-дневный вход</b>\n\n'
    for icon,i,r in cards: txt+=f'{icon} День {i}: <b>+{r:,} COIN</b>\n'.replace(',', ' ')
    txt+=f'\nТекущая серия: <b>{u.streak}/7</b>'
    await c.message.edit_text(txt,parse_mode='HTML',reply_markup=back_kb());await c.answer('Награда получена!' if ok else 'Сегодня уже получена',show_alert=not ok)

@dp.callback_query(F.data=='tasks')
async def tasks(c:CallbackQuery):
    async with Session() as s: ts=list((await s.execute(select(Task).where(Task.active==True).order_by(Task.id))).scalars())
    rows=[]
    for t in ts:
        done=await task_status(c.from_user.id,t.id)
        rows.append([InlineKeyboardButton(text=('✅ ' if done else '🎁 ')+f'{t.title} · {money_from_coins(t.reward_coins):.2f}$',callback_data=f'taskview:{t.id}')])
    rows.append([InlineKeyboardButton(text='⬅️ Назад',callback_data='home')])
    await c.message.edit_text('✅ <b>Задания</b>\n\nВыполняй задания и получай COIN.',parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=rows));await c.answer()

@dp.callback_query(F.data.startswith('taskview:'))
async def taskview(c:CallbackQuery):
    task_id=int(c.data.split(':')[1])
    async with Session() as s:t=await s.get(Task,task_id)
    done=await task_status(c.from_user.id,task_id)
    txt=f'✅ <b>{t.title}</b>\n\nНаграда: <b>{t.reward_coins:,} COIN</b> ≈ ${money_from_coins(t.reward_coins):.2f}'.replace(',', ' ')
    if t.kind=='channel': txt+='\n\nПодпишись на канал и нажми «Проверить». Бот должен быть администратором канала.'
    elif t.kind=='referrals': txt+='\n\nУсловие: пригласить минимум 3 человек.'
    elif t.kind=='taps': txt+='\n\nУсловие: сделать минимум 100 тапов.'
    await c.message.edit_text(txt,parse_mode='HTML',reply_markup=tasks_kb(task_id,done,t.url));await c.answer()

@dp.callback_query(F.data.startswith('task:'))
async def task_check(c:CallbackQuery):
    task_id=int(c.data.split(':')[1])
    async with Session() as s:t=await s.get(Task,task_id)
    if t.kind=='channel':
        try:
            member=await bot.get_chat_member(settings.channel_username,c.from_user.id)
            if member.status in ('left','kicked'): await c.answer('Сначала подпишись на канал.',show_alert=True);return
            async with Session() as s:
                from .db import TaskCompletion, User
                if await s.scalar(select(TaskCompletion).where(TaskCompletion.user_id==c.from_user.id,TaskCompletion.task_id==task_id)): await c.answer('Уже выполнено',show_alert=True);return
                u=await s.get(User,c.from_user.id);u.coins+=t.reward_coins;u.total_earned+=t.reward_coins;s.add(TaskCompletion(user_id=c.from_user.id,task_id=task_id));await s.commit()
            await refresh_achievements(c.from_user.id); await c.answer(f'Задание выполнено! +{t.reward_coins:,} COIN'.replace(',', ' '),show_alert=True)
        except Exception as e:
            logging.exception(e);await c.answer('Не удалось проверить подписку. Проверь права бота.',show_alert=True)
    else:
        ok,reward,status=await complete_generic_task(c.from_user.id,task_id)
        if ok: await refresh_achievements(c.from_user.id)
        await c.answer('Задание выполнено!' if ok else ('Уже выполнено' if status=='done' else 'Условие ещё не выполнено'),show_alert=True)
    await tasks(c)

@dp.callback_query(F.data=='refs')
async def refs(c:CallbackQuery):
    u=await profile(c.from_user.id); me=await bot.get_me(); link=f'https://t.me/{me.username}?start=ref_{u.id}'
    txt=f'👥 <b>Реферальная программа</b>\n\nПриглашено: <b>{u.referrals}</b>\nЗа каждого: <b>{settings.referral_reward_coins:,} COIN</b>\nБонус за 5 приглашённых: <b>${settings.referral_5_bonus_usd}</b> в эквиваленте COIN.\n\nТвоя ссылка:\n<code>{link}</code>'.replace(',', ' ')
    await c.message.edit_text(txt,parse_mode='HTML',reply_markup=back_kb());await c.answer()

@dp.callback_query(F.data=='leaders')
async def leaders(c:CallbackQuery):
    users=await leaderboard(10); lines=['👑 <b>Лидеры</b>\n']
    for i,u in enumerate(users,1): lines.append(f'{i}. @{u.username or u.first_name or u.id} — <b>{u.coins:,}</b> COIN'.replace(',', ' '))
    await c.message.edit_text('\n'.join(lines),parse_mode='HTML',reply_markup=back_kb());await c.answer()

@dp.callback_query(F.data=='tournament')
async def tournament_cb(c:CallbackQuery):
    users=await tournament(10);lines=[f'🏆 <b>Турнир Coin BitRu</b>\n\nПризовой фонд: <b>${settings.tournament_prize_usd}</b>\nТекущий топ:\n']
    for i,u in enumerate(users,1): lines.append(f'{i}. {u.first_name or "Player"} — {u.coins:,} COIN'.replace(',', ' '))
    lines.append('\nПобедитель определяется правилами раунда и после ручной проверки. Призовой фонд не является гарантированной выплатой пользователю до завершения раунда.')
    await c.message.edit_text('\n'.join(lines),parse_mode='HTML',reply_markup=back_kb());await c.answer()

@dp.callback_query(F.data=='topup')
async def topup(c:CallbackQuery):
    await c.message.edit_text('💳 <b>Пополнение</b>\n\nВыбери сумму. После успешной оплаты баланс пополнится автоматически.\n\nДоступные суммы: $1, $2, $5, $10.',parse_mode='HTML',reply_markup=topup_kb());await c.answer()

@dp.callback_query(F.data.startswith('pay:'))
async def pay(c:CallbackQuery):
    usd=int(c.data.split(':')[1])
    if not settings.payment_provider_token: await c.answer('PAYMENT_PROVIDER_TOKEN не настроен на сервере.',show_alert=True);return
    prices=[LabeledPrice(label=f'Coin BitRu ${usd}',amount=usd*100)]
    await bot.send_invoice(chat_id=c.from_user.id,title=f'Coin BitRu — пополнение ${usd}',description=f'Зачисление {usd*settings.coins_per_usd:,} COIN после подтверждения платежа.',payload=f'topup:{usd}',provider_token=settings.payment_provider_token,currency='USD',prices=prices)
    await c.answer()

@dp.pre_checkout_query()
async def pre_checkout(q:PreCheckoutQuery): await q.answer(ok=True)

@dp.message(F.successful_payment)
async def successful_payment(m:Message):
    p=m.successful_payment; usd=p.total_amount/100
    added=await add_payment(m.from_user.id,usd,p.currency,p.telegram_payment_charge_id,p.provider_payment_charge_id,p.invoice_payload)
    if added:
        u=await profile(m.from_user.id);await m.answer(f'✅ Оплата подтверждена. Зачислено <b>{int(usd*settings.coins_per_usd):,} COIN</b>.\nБаланс: {u.coins:,} COIN'.replace(',', ' '),parse_mode='HTML',reply_markup=main_kb())
    else: await m.answer('Платёж уже был обработан.')

@dp.callback_query(F.data=='withdraw')
async def withdraw(c:CallbackQuery):
    u=await profile(c.from_user.id)
    if u.topup_usd<settings.withdraw_topup_min_usd:
        await c.answer(f'Вывод доступен после подтверждённого пополнения на ${settings.withdraw_topup_min_usd}.',show_alert=True);return
    await c.message.edit_text(f'💸 <b>Вывод</b>\n\nКурс: {settings.coins_per_usd:,} COIN = $1\nТвой баланс: {u.coins:,} COIN\nПополнено: ${u.topup_usd:.2f}\n\nНапиши: <code>/withdraw 1 TON_АДРЕС</code>\n\nЗаявка отправится администратору на ручную проверку.',parse_mode='HTML',reply_markup=back_kb());await c.answer()

@dp.message(Command('withdraw'))
async def withdraw_cmd(m:Message):
    parts=m.text.split(maxsplit=2)
    if len(parts)<3: await m.answer('Формат: /withdraw 1 TON_АДРЕС');return
    try:usd=float(parts[1])
    except:await m.answer('Сумма указана неверно.');return
    ok,msg=await create_withdrawal(m.from_user.id,usd,parts[2])
    await m.answer(('✅ '+msg) if ok else ('❌ '+msg))
    if ok:
        async with Session() as s:w=await s.scalar(select(Withdrawal).where(Withdrawal.user_id==m.from_user.id).order_by(desc(Withdrawal.id)))
        for admin in settings.admin_set:
            try: await bot.send_message(admin,f'💸 Новая заявка #{w.id}\nUser: {m.from_user.id}\nСумма: ${w.usd:.2f}\nCOIN: {w.coins:,}\nDestination: <code>{w.destination}</code>',parse_mode='HTML')
            except Exception: pass

@dp.callback_query(F.data=='profile')
async def profile_cb(c:CallbackQuery):
    u=await profile(c.from_user.id); league,_=get_league(u.total_earned)
    txt=(f'👤 <b>Профиль</b>\n\nID: <code>{u.id}</code>\n'
         f'Уровень: <b>{u.tap_level}</b>\nЛига: <b>{league}</b>\nТапов: <b>{u.total_taps:,}</b>\n'
         f'Всего заработано: <b>{u.total_earned:,} COIN</b>\nРефералов: <b>{u.referrals}</b>\n'
         f'Пополнено: <b>${u.topup_usd:.2f}</b>\nВыведено: <b>${u.total_withdrawn_usd:.2f}</b>').replace(',', ' ')
    await c.message.edit_text(txt,parse_mode='HTML',reply_markup=back_kb());await c.answer()

@dp.callback_query(F.data=='achievements')
async def achievements_cb(c:CallbackQuery):
    await refresh_achievements(c.from_user.id)
    async with Session() as s:
        achs=list((await s.execute(select(Achievement).where(Achievement.active==True).order_by(Achievement.id))).scalars())
        from .db import UserAchievement
        owned={x.achievement_id for x in (await s.execute(select(UserAchievement).where(UserAchievement.user_id==c.from_user.id))).scalars()}
    txt='🏅 <b>Достижения</b>\n\n'
    for a in achs:txt+=('✅' if a.id in owned else '🔒')+f' <b>{a.title}</b> — {a.description} · +{a.reward_coins:,} COIN\n'.replace(',', ' ')
    await c.message.edit_text(txt,parse_mode='HTML',reply_markup=back_kb());await c.answer()

@dp.callback_query(F.data=='missions')
async def missions_cb(c:CallbackQuery):
    pairs=await daily_missions(c.from_user.id)
    txt='🎯 <b>Ежедневные миссии</b>\n\n'
    rows=[]
    for um,m in pairs:
        status='✅' if um.claimed else ('🎁' if um.progress>=m.target else '🔄')
        txt+=f'{status} {m.title}: <b>{um.progress}/{m.target}</b> · +{m.reward_coins:,} COIN\n'.replace(',', ' ')
        if not um.claimed and um.progress>=m.target:rows.append([InlineKeyboardButton(text=f'Забрать +{m.reward_coins:,}'.replace(',', ' '),callback_data=f'mission:{m.id}')])
    rows.append([InlineKeyboardButton(text='⬅️ Назад',callback_data='home')])
    await c.message.edit_text(txt,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=rows));await c.answer()

@dp.callback_query(F.data.startswith('mission:'))
async def mission_claim(c:CallbackQuery):
    mid=int(c.data.split(':')[1]);ok,reward,status=await claim_mission(c.from_user.id,mid)
    await c.answer(f'+{reward:,} COIN' .replace(',', ' ') if ok else ('Уже забрано' if status=='claimed' else 'Миссия ещё не выполнена'),show_alert=True)
    await missions_cb(c)

@dp.callback_query(F.data=='promo')
async def promo_cb(c:CallbackQuery):
    await c.message.edit_text('🎟 <b>Промокод</b>\n\nВведи команду:\n<code>/promo CODE</code>',parse_mode='HTML',reply_markup=back_kb());await c.answer()

@dp.message(Command('promo'))
async def promo_cmd(m:Message):
    parts=m.text.split(maxsplit=1)
    if len(parts)<2:await m.answer('Формат: /promo CODE');return
    ok,res=await use_promo(m.from_user.id,parts[1]);await m.answer(f'✅ Промокод активирован: +{res:,} COIN'.replace(',', ' ') if ok else f'❌ {res}')

@dp.callback_query(F.data=='notifications')
async def notifications_cb(c:CallbackQuery):
    ns=await unread_notifications(c.from_user.id)
    if not ns:txt='🔔 <b>Уведомления</b>\n\nНовых уведомлений нет.'
    else:
        txt='🔔 <b>Уведомления</b>\n\n'+'\n\n'.join([f'<b>{n.title}</b>\n{n.body}' for n in ns])
        await mark_notifications_read(c.from_user.id)
    await c.message.edit_text(txt,parse_mode='HTML',reply_markup=back_kb());await c.answer()

@dp.callback_query(F.data=='language')
async def language(c:CallbackQuery):
    await c.message.edit_text('🌐 <b>Язык</b>\n\nСейчас доступна русская версия. Архитектура готова для локализации.',parse_mode='HTML',reply_markup=back_kb());await c.answer()

@dp.message(Command('admin'))
async def admin(m:Message):
    if m.from_user.id not in settings.admin_set:return
    async with Session() as s:
        pending=list((await s.execute(select(Withdrawal).where(Withdrawal.status=='pending').order_by(Withdrawal.id))).scalars())
    await m.answer('🛠 <b>Админка</b>\n\nОжидающих выводов: '+str(len(pending))+'\n\n'+'\n'.join([f'#{w.id} — ${w.usd:.2f} — /approve_{w.id} или /reject_{w.id}' for w in pending]) if pending else '🛠 <b>Админка</b>\n\nОжидающих выводов: 0',parse_mode='HTML')

@dp.message(Command('promo_create'))
async def promo_create_cmd(m:Message):
    if m.from_user.id not in settings.admin_set:return
    parts=m.text.split()
    if len(parts)!=4:await m.answer('Формат: /promo_create CODE REWARD_COINS MAX_USES');return
    try:reward=int(parts[2]);max_uses=int(parts[3])
    except:await m.answer('Reward и max uses должны быть числами.');return
    try:await create_promo(parts[1],reward,max_uses);await m.answer(f'✅ Создан промокод {parts[1].upper()}')
    except Exception:await m.answer('❌ Не удалось создать промокод. Возможно, такой код уже существует.')

@dp.message(F.text.regexp(r'^/approve_\d+$'))
async def approve(m:Message):
    if m.from_user.id not in settings.admin_set:return
    wid=int(m.text.split('_')[1])
    async with Session() as s:
        w=await s.get(Withdrawal,wid)
        if not w or w.status!='pending':await m.answer('Заявка не найдена или уже обработана.');return
        w.status='approved';u=await s.get(User,w.user_id);u.total_withdrawn_usd+=w.usd
        await s.commit()
    await m.answer(f'✅ Вывод #{wid} отмечен как approved.')

@dp.message(F.text.regexp(r'^/reject_\d+$'))
async def reject(m:Message):
    if m.from_user.id not in settings.admin_set:return
    wid=int(m.text.split('_')[1])
    async with Session() as s:
        w=await s.get(Withdrawal,wid)
        if not w or w.status!='pending':await m.answer('Заявка не найдена или уже обработана.');return
        from .db import User
        u=await s.get(User,w.user_id);u.coins+=w.coins;w.status='rejected';await s.commit()
    await m.answer(f'⛔ Вывод #{wid} отклонён, COIN возвращены пользователю.')

@dp.callback_query(F.data=='noop')
async def noop(c:CallbackQuery):await c.answer('Уже выполнено')

async def main():
    await init_db(); await dp.start_polling(bot)
if __name__=='__main__': asyncio.run(main())
