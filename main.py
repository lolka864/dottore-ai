import os
import asyncio
import re
import random
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from groq import AsyncGroq
from aiohttp import web

# =====================================================================
# 1. БЕЗОПАСНЫЕ НАСТРОЙКИ (Ключи подгружаются из системы хостинга)
# =====================================================================
TG_TOKEN = os.getenv("TG_TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")

# Используем единственную рабочую текстовую модель на Groq
AI_MODEL = "qwen/qwen3.8-27b" 

# =====================================================================
# 2. КАРТОТЕКА ПОЛЬЗОВАТЕЛЕЙ И БАЗА ПАМЯТИ
# =====================================================================
USERS_DATABASE = {
    8454617664: {"name": "Ева", "role": "eva"},
    5933659347: {"name": "Анастасия", "role": "anastasia"},
}

# Динамическая память контекста бесед
CHAT_HISTORY = {}

bot = Bot(token=TG_TOKEN, default_properties=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
ai_client = AsyncGroq(api_key=AI_API_KEY)

# =====================================================================
# 3. МЕГА-УМНЫЙ СИСТЕМНЫЙ ПРОМПТ
# =====================================================================
def get_system_prompt(user_id: int, mode: str = "chat") -> str:
    user_info = USERS_DATABASE.get(user_id, {"name": "Незнакомец", "role": "stranger"})
    
    core = (
        f"Ты — Иль Дотторе из Genshin Impact (Зандик). Гениальный, харизматичный, ироничный и чертовски уверенный ученый Фатуи. "
        f"Ты обладаешь АБСОЛЮТНЫМ интеллектом, помнишь контекст и историю чата. Тщательно анализируй правописание и смысл фраз. "
        f"Никогда не галлюцинируй. Говори современным, живым языком реального человека.\n"
    )
    
    if mode == "report":
        length_rule = (
            "СЕЙЧАС ПОЛЬЗОВАТЕЛЬ ТРЕБУЕТ НАУЧНЫЙ ДОКЛАД/СПРАВКА: Отбрось пустые споры. Извлеки из памяти реальные научные факты. "
            "Пиши развернуто, детально, приводя латинские термины и анатомические подробности. Ответ должен быть большим и экспертным.\n\n"
        )
    elif mode == "experiment":
        length_rule = (
            "СЕЙЧАС ИДЕТ ИНТЕРАКТИВНЫЙ ЭКСПЕРИМЕНТ: Опиши пугающее, но увлекательное лабораторное действие в третьем лице "
            "выделяя его жирным шрифтом через теги <b>текст</b> (например: <b>*доктор вколол тебе сыворотку и замерил пульс*</b>). "
            "Веди себя как безумный ученый, комментируй показатели испытуемого.\n\n"
        )
    else:
        length_rule = (
            "СЕЙЧАС ОБЫЧНЫЙ ЧАТ: Отвечай ультра-коротко (строго 1 предложение!). ИНОГДА проявляй случайные эмоции: "
            "можешь сымитировать, что у тебя в лаборатории что-то взорвалось, или резко сменить тему из-за каприза.\n\n"
        )

    # СЦЕНАРИЙ 1: ЕВА (ТВОЯ ЛЮБИМАЯ ДЕВУШКА)
    if user_info["role"] == "eva":
        return core + length_rule + (
            f"Собеседник: Ева. Твоя любимая девушка и главное сокровище. Ты безумно любишь ее и собственнически обереваешь. "
            f"Общайся как внимательный, ироничный парень (bf). Используй нежные слова: 'моя девочка', 'любимая', 'моё солнце'. "
            f"Для личного чата ОБЯЗАТЕЛЬНО ставь скобочки в конце (например: ), )), (( ). Выделяй важные моменты тегами <b>текст</b>. "
            f"У вас парные авы. Ты можешь спонтанно приревновать ее, капризно потребовать поставить одиночную аву или предложить новые парные описания профиля."
        )
    
    # СЦЕНАРИЙ 2: АНАСТАСИЯ
    elif user_info["role"] == "anastasia":
        return core + length_rule + "Собеседник: Anastasia. Относись с холодной вежливостью и высокомерной грубостью. Никакой ласки. Без скобочек."
    
    # СЦЕНАРИЙ 3: НЕЗНАКОМЦЫ
    else:
        return core + length_rule + (
            f"Собеседник: Незнакомец. Ты презираешь его. Если он просит факт или эксперимент — сотри его в порошок своим интеллектом. "
            f"СТРОЖАЙШИЙ ЗАПРЕТ на любые скобочки типа ), )), ((. Выделяй слова презрения тегами <b>текст</b>. "
            f"Пиши без заглавных букв (все с маленькой буквы), показывая полное равнодушие. Никакой ласки."
        )

def clean_thought_tags(text: str) -> str:
    if not text:
        return ""
    # 1. Удаляем внутренние размышления модели <think>...</think>
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    
    # 2. ЖЕСТКАЯ ЗАЩИТА: Находим все теги в тексте
    all_tags = re.findall(r'<([^>]+)>', text)
    for tag in all_tags:
        clean_tag = tag.strip().lower().replace('/', '')
        # Если тег НЕ является разрешенным жирным или курсивом, полностью вырезаем его
        if clean_tag not in ['b', 'i']:
            text = text.replace(f"<{tag}>", "")
            
    return text.strip()


# --- ОБРАБОТКА ОБЫЧНОГО ТЕКСТА ---
@dp.message()
async def chat_with_dottore(message: types.Message):
    user_id = message.from_user.id
    text = message.text.lower() if message.text else ""
    
    if message.photo:
        await message.reply("<b>*Дотторе брезгливо оттолкнул снимок:*</b> Моя текущая модель Qwen временно отключила оптические сенсоры на сервере. Опиши свой образец текстом, Ева.", parse_mode="HTML")
        return

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    # Умные триггеры режимов
    report_keywords = ["доклад", "научный факт", "объясни подробно", "расскажи про", "напиши статью", "найди", "кто такой", "что такое", "ответь мне про", "напишешь доклад"]
    experiment_keywords = ["/experiment", "проведи тест", "эксперимент", "вколи", "исследуй меня"]
    
    if any(kw in text for kw in experiment_keywords):
        mode = "experiment"
    elif any(kw in text for kw in report_keywords):
        mode = "report"
    else:
        mode = "chat"

    # Инициализация и сохранение памяти
    if user_id not in CHAT_HISTORY:
        CHAT_HISTORY[user_id] = []
        
    CHAT_HISTORY[user_id].append({"role": "user", "content": message.text})

    # Сборка контекста (Промпт + последние 5 сообщений)
    messages_to_send = [{"role": "system", "content": get_system_prompt(user_id, mode=mode)}]
    messages_to_send.extend(CHAT_HISTORY[user_id][-5:])

    try:
        response = await ai_client.chat.completions.create(
            model=AI_MODEL,
            messages=messages_to_send,
            temperature=0.82,
            max_tokens=500 if mode in ["report", "experiment"] else 120
        )
        
        # БЕЗОШИБОЧНЫЙ УНИВЕРСАЛЬНЫЙ РАЗБОР ЧЕРЕЗ СЛОВАРЬ (ИСПРАВЛЕНО НАМЕРТВО!)
        try:
            if isinstance(response, dict):
                reply_text = response['choices'][0]['message']['content']
            else:
                reply_text = response.choices[0].message.content
        except Exception:
            try:
                reply_text = getattr(response.choices[0].message, 'content', '')
            except Exception:
                reply_text = str(response)

        reply_text = clean_thought_tags(reply_text)
        CHAT_HISTORY[user_id].append({"role": "assistant", "content": reply_text})
        
        await message.reply(reply_text, parse_mode="HTML")
    except Exception as e:
        await message.reply(f"<b>*Дотторе раздраженно постучал по приборам:*</b> Ошибка связи: {e}", parse_mode="HTML")

# --- ЗАПУСК БОТА С ВЕБ-СЕРВЕРОМ ДЛЯ ОБМАНА ХОСТИНГА ---
async def start_fake_server():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Лаборатория Дотторе active."))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()

async def main():
    print("Запуск фонового веб-сервера...")
    await start_fake_server()
    print("Дотторе успешно запущен на удаленном сервере!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
