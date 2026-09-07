from datetime import datetime, timezone, timedelta
from sqlalchemy import select, desc
from .db import Session, User, Payment, TaskCompletion, Withdrawal, PromoCode, PromoUse, Achievement, UserAchievement, DailyMission, UserMission, Notification
from .config import settings

async def get_or_create_user(tg_user, referrer_id=None):
    async with Session() as s:
        user = await s.get(User, tg_user.id)
        if not user:
            valid_ref = referrer_id if referrer_id and referrer_id != tg_user.id else None
            user = User(id=tg_user.id, username=tg_user.username, first_name=tg_user.first_name, referrer_id=valid_ref)
            s.add(user)
            if valid_ref and await s.get(User, valid_ref):
                ref = await s.get(User, valid_ref)
                ref.referrals += 1
                ref.coins += settings.referral_reward_coins
                ref.total_earned += settings.referral_reward_coins
                if ref.referrals == 5 and ref.referral_paid == 0:
                    ref.referral_paid = 1
                    bonus = settings.referral_5_bonus_usd * settings.coins_per_usd
                    ref.coins += bonus; ref.total_earned += bonus
                    s.add(Notification(user_id=ref.id, title='Реферальный бонус', body='Ты пригласил 5 друзей и получил бонус в COIN.'))
            await s.commit()
        else:
            changed = False
            if user.username != tg_user.username: user.username=tg_user.username; changed=True
            if user.first_name != tg_user.first_name: user.first_name=tg_user.first_name; changed=True
            if changed: await s.commit()
        return user

async def profile(user_id):
    async with Session() as s: return await s.get(User, user_id)

async def tap(user_id):
    async with Session() as s:
        u=await s.get(User,user_id)
        if not u or u.energy<=0: return 0,u
        gain=u.tap_level
        u.energy-=1; u.coins+=gain; u.total_taps+=1; u.total_earned+=gain
        await s.commit()
        return gain,u

async def restore_energy(user_id):
    async with Session() as s:
        u=await s.get(User,user_id)
        if not u: return None
        now=datetime.now(timezone.utc)
        basis=u.created_at
        if u.last_daily_claim and u.last_daily_claim > basis: basis=u.last_daily_claim
        if u.energy < u.max_energy:
            elapsed=max(0,(now-basis).total_seconds())
            u.energy=min(u.max_energy, u.energy + int(elapsed/15))
            u.created_at=now
            await s.commit()
        return u

async def upgrade_tap(user_id):
    async with Session() as s:
        u=await s.get(User,user_id)
        if not u: return False,u
        cost=int(1000*(1.8**(u.tap_level-1)))
        if u.coins<cost: return False,u
        u.coins-=cost; u.tap_level+=1; u.max_energy=min(1000,u.max_energy+10); u.energy=u.max_energy
        await s.commit(); return True,u

async def daily_claim(user_id):
    async with Session() as s:
        u=await s.get(User,user_id)
        now=datetime.now(timezone.utc)
        if u.last_daily_claim and (now-u.last_daily_claim).total_seconds()<20*3600: return False,u,0
        if u.last_daily_claim and (now-u.last_daily_claim).total_seconds()<=48*3600: u.streak=min(7,u.streak+1)
        else: u.streak=1
        rewards=[1000,2500,5000,7500,10000,20000,50000]
        reward=rewards[u.streak-1]
        u.coins+=reward; u.total_earned+=reward; u.last_daily_claim=now
        await s.commit(); return True,u,reward

async def mark_achievement(user_id, code):
    async with Session() as s:
        a=await s.scalar(select(Achievement).where(Achievement.code==code, Achievement.active==True))
        if not a: return False,0
        exists=await s.scalar(select(UserAchievement).where(UserAchievement.user_id==user_id,UserAchievement.achievement_id==a.id))
        if exists:return False,0
        u=await s.get(User,user_id)
        u.coins+=a.reward_coins;u.total_earned+=a.reward_coins
        s.add(UserAchievement(user_id=user_id,achievement_id=a.id)); await s.commit(); return True,a.reward_coins

async def refresh_achievements(user_id):
    u=await profile(user_id)
    rewards=[]
    if u:
        if u.total_taps>=1:
            ok,r=await mark_achievement(user_id,'first_tap');
            if ok:rewards.append(r)
        if u.total_taps>=1000:
            ok,r=await mark_achievement(user_id,'tap_1000');
            if ok:rewards.append(r)
        if u.referrals>=5:
            ok,r=await mark_achievement(user_id,'ref_5');
            if ok:rewards.append(r)
        if u.streak>=7:
            ok,r=await mark_achievement(user_id,'streak_7');
            if ok:rewards.append(r)
    return rewards

async def mark_task(user_id, task_id):
    async with Session() as s:
        c=await s.scalar(select(TaskCompletion).where(TaskCompletion.user_id==user_id,TaskCompletion.task_id==task_id))
        if c: return False,0
        from .db import Task
        t=await s.get(Task,task_id)
        if not t or not t.active:return False,0
        if t.kind in ('channel','taps','referrals'): return None,t.reward_coins
        s.add(TaskCompletion(user_id=user_id,task_id=task_id));u=await s.get(User,user_id);u.coins+=t.reward_coins;u.total_earned+=t.reward_coins
        await s.commit();return True,t.reward_coins

async def complete_generic_task(user_id, task_id):
    async with Session() as s:
        from .db import Task
        t=await s.get(Task,task_id)
        if not t:return False,0,'notfound'
        c=await s.scalar(select(TaskCompletion).where(TaskCompletion.user_id==user_id,TaskCompletion.task_id==task_id))
        if c:return False,0,'done'
        u=await s.get(User,user_id)
        if t.kind=='taps' and u.total_taps < 100:return False,t.reward_coins,'condition'
        if t.kind=='referrals' and u.referrals < 3:return False,t.reward_coins,'condition'
        s.add(TaskCompletion(user_id=user_id,task_id=task_id));u.coins+=t.reward_coins;u.total_earned+=t.reward_coins
        await s.commit();return True,t.reward_coins,'ok'

async def task_status(user_id, task_id):
    async with Session() as s:
        c=await s.scalar(select(TaskCompletion).where(TaskCompletion.user_id==user_id,TaskCompletion.task_id==task_id)); return bool(c)

async def add_payment(user_id, amount_usd, currency, tg_charge, provider_charge, payload):
    async with Session() as s:
        exists=await s.scalar(select(Payment).where(Payment.telegram_charge_id==tg_charge))
        if exists:return False
        p=Payment(user_id=user_id,amount_minor=int(round(amount_usd*100)),currency=currency,telegram_charge_id=tg_charge,provider_charge_id=provider_charge,payload=payload)
        s.add(p);u=await s.get(User,user_id);u.topup_usd += amount_usd
        await s.commit();return True

async def create_withdrawal(user_id, usd, destination):
    coins=int(round(usd*settings.coins_per_usd))
    async with Session() as s:
        u=await s.get(User,user_id)
        if not u:return False,'Пользователь не найден'
        if u.topup_usd < settings.withdraw_topup_min_usd:return False,f'Вывод доступен после пополнения на ${settings.withdraw_topup_min_usd:.0f}.'
        if usd < settings.withdraw_min_usd:return False,f'Минимум для вывода ${settings.withdraw_min_usd:.0f}.'
        if u.coins<coins:return False,'Недостаточно коинов.'
        u.coins-=coins;s.add(Withdrawal(user_id=user_id,usd=usd,coins=coins,destination=destination));await s.commit();return True,'Заявка создана.'

async def leaderboard(limit=10):
    async with Session() as s:return list((await s.execute(select(User).order_by(desc(User.coins)).limit(limit))).scalars())

async def tournament(limit=10): return await leaderboard(limit)

async def league_for_user(user_id):
    u=await profile(user_id)
    if not u:return 'Bronze',1
    ranges=[(100_000,'Diamond'),(50_000,'Platinum'),(20_000,'Gold'),(5_000,'Silver')]
    for threshold,name in ranges:
        if u.total_earned>=threshold:return name,threshold
    return 'Bronze',0

async def use_promo(user_id, raw_code):
    code=raw_code.strip().upper()
    async with Session() as s:
        p=await s.scalar(select(PromoCode).where(PromoCode.code==code, PromoCode.active==True))
        if not p:return False,'Промокод не найден.'
        if p.uses>=p.max_uses:return False,'Промокод уже исчерпан.'
        used=await s.scalar(select(PromoUse).where(PromoUse.user_id==user_id,PromoUse.promo_id==p.id))
        if used:return False,'Ты уже использовал этот промокод.'
        u=await s.get(User,user_id);u.coins+=p.reward_coins;u.total_earned+=p.reward_coins;p.uses+=1
        s.add(PromoUse(user_id=user_id,promo_id=p.id));await s.commit();return True,p.reward_coins

async def create_promo(code,reward,max_uses):
    async with Session() as s:
        code=code.strip().upper(); p=PromoCode(code=code,reward_coins=reward,max_uses=max_uses)
        s.add(p);await s.commit();return p

async def unread_notifications(user_id):
    async with Session() as s:return list((await s.execute(select(Notification).where(Notification.user_id==user_id,Notification.read==False).order_by(desc(Notification.id)).limit(20))).scalars())

async def mark_notifications_read(user_id):
    async with Session() as s:
        rows=list((await s.execute(select(Notification).where(Notification.user_id==user_id,Notification.read==False))).scalars())
        for n in rows:n.read=True
        await s.commit()

async def seed_daily_missions(user_id):
    day=datetime.now(timezone.utc).date().isoformat()
    async with Session() as s:
        missions=list((await s.execute(select(DailyMission).where(DailyMission.active==True))).scalars())
        for m in missions:
            ex=await s.scalar(select(UserMission).where(UserMission.user_id==user_id,UserMission.mission_id==m.id,UserMission.day_key==day))
            if not ex:s.add(UserMission(user_id=user_id,mission_id=m.id,progress=0,day_key=day))
        await s.commit()

async def daily_missions(user_id):
    await seed_daily_missions(user_id)
    day=datetime.now(timezone.utc).date().isoformat()
    async with Session() as s:
        rows=list((await s.execute(select(UserMission,DailyMission).join(DailyMission,DailyMission.id==UserMission.mission_id).where(UserMission.user_id==user_id,UserMission.day_key==day))).all())
        return [(um,m) for um,m in rows]

async def update_mission_progress(user_id, kind, delta=1):
    pairs=await daily_missions(user_id)
    async with Session() as s:
        changed=[]
        day=datetime.now(timezone.utc).date().isoformat()
        for um,_ in pairs:
            m=await s.get(DailyMission,um.mission_id)
            if m.kind!=kind or um.claimed:continue
            obj=await s.get(UserMission,um.id);obj.progress=min(m.target,obj.progress+delta);changed.append((m.title,m.reward_coins,obj.progress,m.target))
        await s.commit();return changed

async def claim_mission(user_id, mission_id):
    day=datetime.now(timezone.utc).date().isoformat()
    async with Session() as s:
        um=await s.scalar(select(UserMission).where(UserMission.user_id==user_id,UserMission.mission_id==mission_id,UserMission.day_key==day))
        if not um:return False,0,'notfound'
        m=await s.get(DailyMission,mission_id)
        if um.claimed:return False,m.reward_coins,'claimed'
        if um.progress<m.target:return False,m.reward_coins,'condition'
        u=await s.get(User,user_id);u.coins+=m.reward_coins;u.total_earned+=m.reward_coins;um.claimed=True
        await s.commit();return True,m.reward_coins,'ok'
