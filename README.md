# Coin BitRu — полный Telegram-бот + сервер

Полный проект для VPS/Docker: Telegram-бот на aiogram, FastAPI health-server, SQLite, tap-to-earn, 7-дневный вход, задания, рефералы, лидерборд, турнир, профили, лиги, достижения, ежедневные миссии, промокоды, уведомления и Telegram Payments.

## Возможности

- ⚡ Tap-to-earn, уровни тапа и энергия
- 🎁 7-дневная серия ежедневных наград
- ✅ Задания, включая подписку на `https://t.me/Coin_BitRu`
- 👥 Реферальная программа + бонус за 5 приглашённых
- 👑 Лидерборд
- 🏆 Турнир с отображаемым призовым фондом $100; правила и фактические выплаты должны быть прозрачными и подтверждаться администратором
- 👤 Профиль и лиги Bronze/Silver/Gold/Platinum/Diamond
- 🏅 Достижения
- 🎯 Ежедневные миссии
- 🎟 Промокоды (`/promo`, создание админом через `/promo_create`)
- 🔔 Уведомления
- 💳 Пополнение через Telegram Payments
- 💸 Заявки на вывод с ручной обработкой
- 🛡 Защита от повторного зачисления платежа и повторного получения награды за сущности с уникальными ограничениями
- 🌐 FastAPI health endpoint

## 1. Настройка

```bash
cp .env.example .env
```

Заполни `.env`:
- `BOT_TOKEN` — токен бота из @BotFather
- `PAYMENT_PROVIDER_TOKEN` — provider token платежного провайдера
- `ADMIN_IDS` — Telegram ID администраторов через запятую
- `CHANNEL_USERNAME=@Coin_BitRu`

## 2. Запуск Docker

```bash
docker compose up -d --build
docker compose logs -f
```

Health: `http://SERVER_IP:8080/health`

## 3. Локальный запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

## Платежи

Пополнение: invoice → pre_checkout → successful_payment. Баланс пополняется только после подтверждённого платежа. Повторный `telegram_payment_charge_id` не зачисляется дважды.

Перед продакшеном проверь актуальные требования Telegram для выбранного типа цифрового товара и валюты.

## Вывод

Вывод доступен после подтверждённого пополнения минимум на `$2`. Курс: `100 000 COIN = $1`, минимальный вывод — `$1`. Средства на вывод блокируются в COIN и создаётся заявка. Выплата выполняется оператором через выбранный легальный процессор/кошелёк после проверки заявки.

## Дополнительно

### Промокоды
Администратор:
```text
/promo_create CODE 10000 100
```
Пользователь:
```text
/promo CODE
```

### Админка
```text
/admin
/approve_ID
/reject_ID
```

## Безопасность

Не коммить `.env`. Используй HTTPS/reverse proxy перед FastAPI, сильный `WEBHOOK_SECRET`, отдельного администратора и резервные копии `data/`.
