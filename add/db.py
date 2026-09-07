from datetime import datetime, timezone
from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncAttrs, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from .config import settings

class Base(AsyncAttrs, DeclarativeBase): pass

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    coins: Mapped[int] = mapped_column(BigInteger, default=0)
    tap_level: Mapped[int] = mapped_column(Integer, default=1)
    energy: Mapped[int] = mapped_column(Integer, default=100)
    max_energy: Mapped[int] = mapped_column(Integer, default=100)
    referrer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=True)
    referrals: Mapped[int] = mapped_column(Integer, default=0)
    referral_paid: Mapped[int] = mapped_column(Integer, default=0)
    topup_usd: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_daily_claim: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    total_taps: Mapped[int] = mapped_column(BigInteger, default=0)
    total_earned: Mapped[int] = mapped_column(BigInteger, default=0)
    total_withdrawn_usd: Mapped[float] = mapped_column(Float, default=0)
    language: Mapped[str] = mapped_column(String(8), default='ru')
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

class Payment(Base):
    __tablename__ = 'payments'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    currency: Mapped[str] = mapped_column(String(8))
    amount_minor: Mapped[int] = mapped_column(Integer)
    telegram_charge_id: Mapped[str] = mapped_column(String(255), unique=True)
    provider_charge_id: Mapped[str] = mapped_column(String(255), default='')
    payload: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class Task(Base):
    __tablename__ = 'tasks'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    reward_coins: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(32), default='internal')
    url: Mapped[str] = mapped_column(String(500), default='')
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class TaskCompletion(Base):
    __tablename__ = 'task_completions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    task_id: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint('user_id', 'task_id', name='uq_task_completion'),)

class Withdrawal(Base):
    __tablename__ = 'withdrawals'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    usd: Mapped[float] = mapped_column(Float)
    coins: Mapped[int] = mapped_column(BigInteger)
    destination: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default='pending')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class Setting(Base):
    __tablename__ = 'settings'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255))

class PromoCode(Base):
    __tablename__ = 'promo_codes'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    reward_coins: Mapped[int] = mapped_column(BigInteger)
    max_uses: Mapped[int] = mapped_column(Integer, default=1)
    uses: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class PromoUse(Base):
    __tablename__ = 'promo_uses'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    promo_id: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint('user_id', 'promo_id', name='uq_promo_use'),)

class Achievement(Base):
    __tablename__ = 'achievements'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(255))
    reward_coins: Mapped[int] = mapped_column(BigInteger, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class UserAchievement(Base):
    __tablename__ = 'user_achievements'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    achievement_id: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint('user_id', 'achievement_id', name='uq_user_achievement'),)

class DailyMission(Base):
    __tablename__ = 'daily_missions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(32))
    target: Mapped[int] = mapped_column(Integer, default=1)
    reward_coins: Mapped[int] = mapped_column(BigInteger, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class UserMission(Base):
    __tablename__ = 'user_missions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    mission_id: Mapped[int] = mapped_column(Integer, index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    claimed: Mapped[bool] = mapped_column(Boolean, default=False)
    day_key: Mapped[str] = mapped_column(String(16), index=True)
    __table_args__ = (UniqueConstraint('user_id', 'mission_id', 'day_key', name='uq_user_mission_day'),)

class Notification(Base):
    __tablename__ = 'notifications'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    title: Mapped[str] = mapped_column(String(128))
    body: Mapped[str] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

engine = create_async_engine(settings.database_url, future=True)
Session = async_sessionmaker(engine, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with Session() as s:
        from sqlalchemy import select
        existing_tasks = {r[0] for r in (await s.execute(select(Task.id))).all()}
        tasks = [
            Task(id=1, title='Подписаться на канал Coin BitRu', reward_coins=50000, kind='channel', url=settings.channel_url),
            Task(id=2, title='Сделать 100 тапов', reward_coins=10000, kind='taps'),
            Task(id=3, title='Пригласить 3 друзей', reward_coins=25000, kind='referrals'),
        ]
        for t in tasks:
            if t.id not in existing_tasks: s.add(t)

        ach_defs = [
            ('first_tap', 'Первый тап', 'Сделай первый тап', 500),
            ('tap_1000', 'Tap Master', 'Сделай 1 000 тапов', 2500),
            ('ref_5', 'Команда из 5', 'Пригласи 5 друзей', 5000),
            ('streak_7', '7 дней подряд', 'Забери все 7 ежедневных наград', 10000),
        ]
        existing_achs = {r[0] for r in (await s.execute(select(Achievement.code))).all()}
        for code, title, desc, reward in ach_defs:
            if code not in existing_achs: s.add(Achievement(code=code, title=title, description=desc, reward_coins=reward))

        mission_defs = [
            ('tap_50', 'Сделай 50 тапов', 'taps', 50, 1500),
            ('tap_200', 'Сделай 200 тапов', 'taps', 200, 4000),
            ('daily_claim', 'Забери ежедневную награду', 'daily', 1, 1000),
        ]
        existing_missions = {r[0] for r in (await s.execute(select(DailyMission.code))).all()}
        for code, title, kind, target, reward in mission_defs:
            if code not in existing_missions: s.add(DailyMission(code=code, title=title, kind=kind, target=target, reward_coins=reward))
        await s.commit()
