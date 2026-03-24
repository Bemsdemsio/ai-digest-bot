# 🤖 AI Tools Weekly Digest Bot

Щотижневий дайджест нових AI-інструментів у Telegram-канал.
Парсить 4 джерела → фільтрує → генерує AI-резюме через Claude → публікує.

## Як це виглядає у Telegram

```
🤖 AI-інструменти тижня | 17.03–24.03.2026
Відібрано: 15 нових інструментів

━━━━━━━━━━━━━━━━━━━━
1. Runway Gen-4
_Відеогенератор з точним контролем руху камери — ідеально для контент-мейкерів._
Product Hunt 🐱 → посилання

2. Cursor 0.45
_Оновлення AI-редактора: підтримка агентського режиму в командному рядку._
Hacker News 🔶 → посилання
...
```

## Джерела

| Джерело | Метод | Мінімальний score |
|---------|-------|-------------------|
| Product Hunt | RSS (category=AI) | — |
| Hacker News | Algolia API | ≥ 15 points |
| Reddit | JSON API (4 subredits) | ≥ 25 upvotes |
| TechCrunch / VentureBeat / The Verge / Wired | RSS | — |

## Швидкий старт

### 1. Встановити залежності

```bash
pip install -r requirements.txt
```

### 2. Отримати токени

**Telegram Bot Token:**
1. Напиши `/newbot` до @BotFather
2. Скопіюй токен
3. Додай бота адміністратором у свій канал (з правом публікації)

**Anthropic API Key:**
- https://console.anthropic.com → API Keys

**Channel ID:**
- Публічний канал: `@назва_каналу`
- Приватний канал: числовий ID (напр. `-1001234567890`)

### 3. Запустити вручну

```bash
export TELEGRAM_BOT_TOKEN="токен"
export TELEGRAM_CHANNEL_ID="@канал"
export ANTHROPIC_API_KEY="sk-ant-..."

python digest.py
```

---

## Автоматизація через GitHub Actions

1. Залий цей репозиторій на GitHub
2. `Settings → Secrets and variables → Actions → New repository secret`:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHANNEL_ID`
   - `ANTHROPIC_API_KEY`
3. Бот запускатиметься **щопонеділка о 12:00 за Києвом**

Ручний запуск: `Actions → Weekly AI Digest → Run workflow`

---

## Змінні середовища

| Змінна | Обов'язкова | За замовчуванням | Опис |
|--------|-------------|------------------|------|
| `TELEGRAM_BOT_TOKEN` | ✅ | — | Токен бота від @BotFather |
| `TELEGRAM_CHANNEL_ID` | ✅ | — | ID або @username каналу |
| `ANTHROPIC_API_KEY` | ✅ | — | Для генерації AI-резюме |
| `DAYS_BACK` | ❌ | `7` | Глибина пошуку в днях |
| `MAX_TOOLS` | ❌ | `15` | Максимум інструментів у пості |

## Вартість

Claude Haiku для резюме 15 інструментів ≈ **$0.01–0.02 за запуск** (~$0.05–0.10 на місяць).
