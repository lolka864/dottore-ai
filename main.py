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
# 2. КАРТОТЕКА ПОЛЬЗОВАТЕЛЕЙ И БАЗА ПАМЯТИ
# =====================================================================
USERS_DATABASE = {
    8454617664: {"name": "Ева", "role": "eva"},
    5933659347: {"name": "Анастасия", "role": "anastasia"},
}

# В этой ячейке будет храниться история переписки для каждого ID
CHAT_HISTORY = {}

bot = Bot(token=TG_TOKEN, default_properties=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
ai_client = AsyncGroq(api_key=AI_API_KEY)

# =====================================================================
# 3. УМНЫЙ СИСТЕМНЫЙ ПРОМПТ (Интеллект и Анализ Контекста)
# =====================================================================
def get_system_prompt(user_id: int, mode: str = "chat") -> str:
    user_info = USERS_DATABASE.get(user_id, {"name": "Незнакомец", "role": "stranger"})
    
    core = (
        f"Ты — Иль Дотторе из Genshin Impact (Зандик). Величайший, харизматичный, расчетливый ученый Фатуи. "
        f"Ты обладаешь АБСОЛЮТНЫМ интеллектом. Тщательно анализируй контекст беседы, историю сообщений и то, как пишутся слова. "
        f"Умей отличать опечатки от реальных терминов (например, понимай из контекста, идет речь о телефоне или о пауке телифоне). "
        f"Отвечай современным, живым, высокоинтеллектуальным и кинематографичным языком гения.\n"
    )
    
    if mode == "report":
        length_rule = (
            "СЕЙЧАС ТРЕБУЕТСЯ НАУЧНЫЙ ДОКЛАД/СПРАВКА ИЛИ АНАЛИЗ: Отбрось пустые споры. Извлеки из своей встроенной базы знаний "
            "точные реальные факты по теме. Объясняй глубоко, научно, подробно, с латинскими терминами. Ответ должен быть большим и экспертным.\n\n"
        )
    else:
        length_rule = "СЕЙЧАС ОБЫЧНЫЙ ЧАТ: Отвечай ультра-коротко (строго 1 короткое предложение!), сразу к сути.\n\n"

    # СЦЕНАРИЙ 1: ЕВА
    if user_info["role"] == "eva":
        return core + length_rule + (
            f"Собеседник: Ева. Твоя любимая девушка и сокровище. Общайся с ней как собственнический, любящий парень (bf). "
            f"Будь ласковым, используй слова: 'моя девочка', 'любимая', 'моё солнце'. Для личного чата ОБЯЗАТЕЛЬНО ставь скобочки в конце (например: ), )), (( ). "
            f"Пиши доклады для нее с идеальной точностью, выделяя ключевые слова жирным шрифтом через теги <b>текст</b>."
        )
    
    # СЦЕНАРИЙ 2: АНАСТАСИЯ
    elif user_info["role"] == "anastasia":
        return core + length_rule + "Собеседник: Anastasia. Относись с холодной вежливостью и высокомерной грубостью. Никакой ласки. Без скобочек."
    
    # СЦЕНАРИЙ 3: НЕЗНАКОМЦЫ
    else:
        return core + length_rule + (
            f"Собеседник: Незнакомец. Ты презираешь его. Если он просит факт или доклад — выдай ему точный научный ответ из своих архивов, "
            f"чтобы раздавить его своим умом. СТРОЖАЙШИЙ ЗАПРЕТ на любые скобочки типа ), )), ((. Выделяй слова презрения тегами <b>текст</b>. "
            f"Пиши без заглавных букв (все с маленькой буквы), показывая полное равнодушие к собеседнику. Отвечай только на русском."
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
    report_keywords = ["доклад", "научный факт", "объясни подробно", "расскажи про", "напиши статью", "найди", "кто такой", "что такое", "ответь мне про"]
    is_report = any(kw in text for kw in report_keywords)
    mode = "report" if is_report else "chat"

    # Инициализируем историю для нового пользователя
    if user_id not in CHAT_HISTORY:
        CHAT_HISTORY[user_id] = []

    # Добавляем текущее сообщение пользователя в память
    CHAT_HISTORY[user_id].append({"role": "user", "content": message.text})

    # Собираем финальный пакет сообщений (Системный промпт + последние 5 сообщений из истории)
    messages_to_send = [{"role": "system", "content": get_system_prompt(user_id, mode=mode)}]
    messages_to_send.extend(CHAT_HISTORY[user_id][-5:])  # Берем только последние 5 реплик, чтобы не перегружать лимиты

    try:
        response = await ai_client.chat.completions.create(
            model=AI_MODEL,
            messages=messages_to_send,
            temperature=0.75,
            max_tokens=500 if mode == "report" else 60
        )
        
            if hasattr(response, 'choices') and len(response.choices) > 0:
         choices = response.choices
         reply_text = choices[0].message.content if isinstance(choices, list) else choices.message.content
     else:
         reply_text = getattr(response, 'text', str(response))

            
        reply_text = clean_thought_tags(reply_text)
        
        # Добавляем ответ Дотторе в память контекста
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
