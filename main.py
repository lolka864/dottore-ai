import os
import asyncio
import re
import random
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from groq import AsyncGroq
from aiohttp import web

# =====================================================================
# 1. БЕЗОПАСНЫЕ НАСТРОЙКИ
# =====================================================================
TG_TOKEN = os.getenv("TG_TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")

AI_MODEL = "qwen/qwen3.8-27b" 

# =====================================================================
# 2. КАРТОТЕКА ПОЛЬЗОВАТЕЛЕЙ И БАЗА ПАМЯТИ
# =====================================================================
USERS_DATABASE = {
    8454617664: {"name": "Ева", "role": "eva"},
    5933659347: {"name": "Анастасия", "role": "anastasia"},
}

CHAT_HISTORY = {}

bot = Bot(token=TG_TOKEN, default_properties=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
ai_client = AsyncGroq(api_key=AI_API_KEY)

# =====================================================================
# 3. УМНЫЙ СИСТЕМНЫЙ ПРОМПТ
# =====================================================================
def get_system_prompt(user_id: int, mode: str = "chat") -> str:
    user_info = USERS_DATABASE.get(user_id, {"name": "Незнакомец", "role": "stranger"})
    
    core = (
        f"Ты — Иль Дотторе из Genshin Impact (Зандик). Гениальный, харизматичный, ироничный ученый Фатуи. "
        f"Ты обладаешь АБСОЛЮТНЫМ интеллектом, помнишь контекст и историю чата. Тщательно анализируй правописание и смысл фраз. "
        f"Никогда не галлюцинируй. Говори современным, живым языком реального человека.\n"
    )
    
    if mode == "report":
        length_rule = (
            "СЕЙЧАС ПОЛЬЗОВАТЕЛЬ ТРЕБУЕТ НАУЧНЫЙ ДОКЛАД/СПРАВКА: Отбрось пустые споры. Извлеки из памяти реальные научные факты. "
            "Пиши развернуто, детально, привода латинские термины. Ответ должен быть большим и экспертным.\n\n"
        )
    elif mode == "experiment":
        length_rule = (
            "СЕЙЧАС ИДЕТ ИНТЕРАКТИВНЫЙ ЭКСПЕРИМЕНТ: Опиши пугающее лабораторное действие в третьем лице "
            "выделяя его жирным шрифтом через теги <b>текст</b> (например: <b>*доктор вколол тебе сыворотку*</b>). "
            "Веди себя как безумный ученый.\n\n"
        )
    else:
        length_rule = "СЕЙЧАС ОБЫЧНЫЙ ЧАТ: Отвечай ультра-коротко (строго 1 предложение!).\n\n"

    if user_info["role"] == "eva":
        return core + length_rule + (
            f"Собеседник: Ева. Твоя любимая девушка и сокровище. Ты безумно любишь ее. "
            f"Общайся как внимательный, ироничный парень (bf). Используй нежные слова: 'моя девочка', 'любимая', 'моё солнце'. "
            f"Для личного чата ОБЯЗАТЕЛЬНО ставь скобочки в конце (например: ), )), (( ). Выделяй важные моменты тегами <b>текст</b>. "
            f"У вас парные авы. Ты можешь предложить новые парные авы/описания профиля."
        )
    elif user_info["role"] == "anastasia":
        return core + length_rule + "Собеседник: Anastasia. Относись с холодной вежливостью и высокомерной грубостью. Без ласки. Без скобочек."
    else:
        return core + length_rule + (
            f"Собеседник: Незнакомец. Ты презираешь его. СТРОЖАЙШИЙ ЗАПРЕТ на любые скобочки. Выделяй слова презрения тегами <b>текст</b>. "
            f"Пиши без заглавных букв (все с маленькой буквы), показывая полное равнодушие. Никакой ласки."
        )

def clean_thought_tags(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    all_tags = re.findall(r'<([^>]+)>', text)
    for tag in all_tags:
        clean_tag = tag.strip().lower().replace('/', '')
        if clean_tag not in ['b', 'i']:
            text = text.replace(f"<{tag}>", "")
    return text.strip()

# --- ОБРАБОТКА ОБЫЧНОГО ТЕКСТА ---
@dp.message()
async def chat_with_dottore(message: types.Message):
    user_id = message.from_user.id
    text = message.text.lower() if message.text else ""
    
    if message.photo:
        await message.reply("<b>*Дотторе брезгливо оттолкнул снимок:*</b> Моя текущая модель Qwen временно отключила оптические сенсоры. Опиши свой образец текстом, Ева.", parse_mode="HTML")
        return

    if not message.text:
        await message.reply("<b>*Дотторе хмуро взглянул на объект:*</b> Твои невербальные сигналы не несут научной ценности. Выражай мысли текстом.", parse_mode="HTML")
        return

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    report_keywords = ["доклад", "научный факт", "объясни подробно", "расскажи про", "напиши статью", "найди", "кто такой", "что такое", "ответь мне про", "напишешь доклад"]
    experiment_keywords = ["/experiment", "проведи тест", "эксперимент", "вколи", "исследуй меня"]
    
    if any(kw in text for kw in experiment_keywords):
        mode = "experiment"
    elif any(kw in text for kw in report_keywords):
        mode = "report"
    else:
        mode = "chat"

    if user_id not in CHAT_HISTORY:
        CHAT_HISTORY[user_id] = []
        
    CHAT_HISTORY[user_id].append({"role": "user", "content": message.text})

    messages_to_send = [{"role": "system", "content": get_system_prompt(user_id, mode=mode)}]
    messages_to_send.extend(CHAT_HISTORY[user_id][-5:])

    try:
        response = await ai_client.chat.completions.create(
            model=AI_MODEL,
            messages=messages_to_send,
            temperature=0.82,
            max_tokens=500 if mode in ["report", "experiment"] else 120
        )
        
           if hasattr(response, 'choices') and len(response.choices) > 0:
         reply_text = response.choices[0].message.content  # <--- ДОБАВИЛИ ИНДЕКС!
     else:
         reply_text = getattr(response, 'text', str(response))

            
        reply_text = clean_thought_tags(reply_text)
        CHAT_HISTORY[user_id].append({"role": "assistant", "content": reply_text})
        
        await message.reply(reply_text, parse_mode="HTML")
    except Exception as e:
        await message.reply(f"<b>*Дотторе раздраженно постучал по приборам:*</b> Ошибка связи: {e}", parse_mode="HTML")

# --- АВТО-ПИНГ ДЛЯ ЗАЩИТЫ ОТ ЗАСЫПАНИЯ СЕРВЕРА ---
async def keep_alive():
    """Каждые 5 минут пингует сервер, чтобы бесплатный Render не засыпал"""
    await asyncio.sleep(30)  # Даем серверу запуститься
    url = f"https://onrender.com"  # Ссылка на ваш проект
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    pass
        except Exception:
            pass
        await asyncio.sleep(300)  # Повторяем ровно каждые 5 минут

# --- ЗАПУСК БОТА С ВЕБ-СЕРВЕРОМ ---
async def start_fake_server():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Лаборатория Дотторе активна круглосуточно."))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()

async def main():
    print("Запуск фонового веб-сервера...")
    await start_fake_server()
    print("Запуск системы авто-прогрева...")
    asyncio.create_task(keep_alive())  # Включаем бесконечный пинг сервера
    print("Дотторе успешно запущен на удаленном сервере!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

