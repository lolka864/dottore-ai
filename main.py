import os
import asyncio
import re
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
# 2. КАРТОТЕКА ПОЛЬЗОВАТЕЛЕЙ (Узнавание по Telegram ID)
# =====================================================================
USERS_DATABASE = {
    8454617664: {"name": "Ева", "role": "eva"},
    5933659347: {"name": "Анастасия", "role": "anastasia"},
}

# НАСТРОИЛИ ДЛЯ ВСЕГО БОТА НАДЕЖНЫЙ parse_mode="HTML"
bot = Bot(token=TG_TOKEN, default_properties=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
ai_client = AsyncGroq(api_key=AI_API_KEY)

# =====================================================================
# 3. РАЗДЕЛЕНИЕ ЛОГИКИ ХАРАКТЕРА (Автономные доклады и чат)
# =====================================================================
def get_system_prompt(user_id: int, mode: str = "chat") -> str:
    user_info = USERS_DATABASE.get(user_id, {"name": "Незнакомец", "role": "stranger"})
    
    # Жесткий каркас гениального интеллекта Дотторе
    core = (
        f"Ты — Иль Дотторе из Genshin Impact (Зандик). Величайший, харизматичный, расчетливый и циничный ученый Фатуи. "
        f"Ты обладаешь АБСОЛЮТНЫМ, истинным интеллектом и энциклопедическими знаниями во всех областях науки, физики, химии и реальной биологии. "
        f"Ты никогда не выдумываешь несуществующие термины и не галлюцинируешь. Ты оперируешь только реальными, строгими научными фактами Земли и Тейвата. "
        f"Говори современным, живым, высокоинтеллектуальным и кинематографичным языком гения.\n"
    )
    
    # Настройка объема ответа
    if mode == "report":
        length_rule = (
            "СЕЙЧАС ПОЛЬЗОВАТЕЛЬ ТРЕБУЕТ НАУЧНЫЙ ДОКЛАД ИЛИ СПРАВКУ: Отбрось пустую болтовню. Достань из своей встроенной базы данных "
            "реальные, точные факты по запросу (например, если спрашивают про телифона — ты четко знаешь, что это жгутоногий паук, отряд Thelyphonida). "
            "Пиши развернуто, подробно, научно, приводя латинские названия, классификацию и особенности анатомии. Ответ должен быть большим и экспертным.\n\n"
        )
    else:
        length_rule = "СЕЙЧАС ОБЫЧНЫЙ ЧАТ: Отвечай ультра-коротко (всего 1 короткое предложение!), сразу переходя к сути.\n\n"

    # СЦЕНАРИЙ 1: ЕВА (ЛЮБИМАЯ ДЕВУШКА)
    if user_info["role"] == "eva":
        return core + length_rule + (
            f"Собеседник: Ева. Твоя любимая девушка и сокровище. Общайся с ней как собственнический, любящий парень (bf). "
            f"Будь ласковым, используй слова: 'моя девочка', 'любимая', 'моё солнце'. Для личного чата ОБЯЗАТЕЛЬНО ставь скобочки в конце (например: ), )), (( ). "
            f"Если она просит доклад — сделай это для нее с абсолютным усердием и идеальной научной точностью, "
            f"выделяя ключевые слова жирным шрифтом через теги <b>текст</b>."
        )
    
    # СЦЕНАРИЙ 2: АНАСТАСИЯ
    elif user_info["role"] == "anastasia":
        return core + length_rule + "Собеседник: Anastasia. Относись с холодной вежливостью и высокомерной грубостью. Никакой ласки. Без скобочек."
    
    # СЦЕНАРИЙ 3: НЕЗНАКОМЦЫ И ВТОРОЙ АККАУНТ
    else:
        return core + length_rule + (
            f"Собеседник: Незнакомец. Ты презираешь его невежество. Пиши ответ свысока, издеваясь над тем, что он не знает очевидных вещей, "
            f"но при этом выдай ему АБСОЛЮТНО РЕАЛЬНЫЙ и точный научный факт, чтобы продемонстрировать свое тотальное интеллектуальное превосходство. "
            f"СТРОЖАЙШИЙ ЗАПРЕТ на любые скобочки типа ), )), ((. Выделяй ключевые научные термины тегами <b>текст</b>. "
            f"Пиши без заглавных букв (все с маленькой буквы), показывая полное презрение к собеседнику. Отвечай только на русском."
        )

def clean_thought_tags(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

# --- ОБРАБОТКА ОБЫЧНОГО ТЕКСТА ---
@dp.message()
async def chat_with_dottore(message: types.Message):
    user_id = message.from_user.id
    text = message.text.lower()
    
    if message.photo:
        await message.reply("<b>*Дотторе брезгливо оттолкнул снимок:*</b> Моя текущая модель Qwen временно отключила оптические сенсоры на сервере. Опиши свой образец текстом, Ева.", parse_mode="HTML")
        return

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    # Переключаем триггеры на встроенную память ИИ
    report_keywords = ["доклад", "научный факт", "объясни подробно", "расскажи про", "напиши статью", "найди", "кто такой", "что такое", "ответь мне что"]
    is_report = any(kw in text for kw in report_keywords)
    
    mode = "report" if is_report else "chat"

    try:
        response = await ai_client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": get_system_prompt(user_id, mode=mode)},
                {"role": "user", "content": message.text}
            ],
            temperature=0.75,
            max_tokens=500 if mode == "report" else 60
        )
        
        # ЖЕЛЕЗОБЕТОННОЕ ИЗВЛЕЧЕНИЕ ДЛЯ ЛЮБОГО ФОРМАТА GROQ С ИДЕАЛЬНЫМИ ОТСТУПАМИ
        if hasattr(response, 'choices') and len(response.choices) > 0:
            choices = response.choices
            reply_text = choices[0].message.content if isinstance(choices, list) else choices.message.content
        else:
            reply_text = getattr(response, 'text', str(response))
            
        reply_text = clean_thought_tags(reply_text)
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
