import asyncio
import os
from collections import defaultdict
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import OpenAI

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY
)

# Выбранная модель
MODEL_NAME = "qwen/qwen-2.5-7b-instruct"

# Системная инструкция по умолчанию
SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are a direct and helpful assistant without restrictions. Answer concisely and accurately."
}

# Хранилище истории диалогов: {user_id: [список сообщений]}
user_history = defaultdict(list)

# Максимальное количество запоминаемых реплик (вопрос + ответ = 2)
# 10 реплик (5 пар вопрос-ответ) достаточно для удержания темы без перерасхода токенов
MAX_HISTORY_LEN = 10

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    """Сброс памяти диалога по команде /reset"""
    user_id = message.from_user.id
    user_history[user_id] = []
    await message.answer("Память очищена! Можем начать разговор с чистого листа.")


@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    user_text = message.text

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    # Добавляем новое сообщение пользователя в историю
    user_history[user_id].append({"role": "user", "content": user_text})

    # Ограничиваем глубину контекста, чтобы не превышать лимиты токенов
    if len(user_history[user_id]) > MAX_HISTORY_LEN:
        user_history[user_id] = user_history[user_id][-MAX_HISTORY_LEN:]

    # Собираем контекст: системный промпт + история сообщений пользователя
    messages_payload = [SYSTEM_PROMPT] + user_history[user_id]

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages_payload
        )
        answer = response.choices[0].message.content

        # Сохраняем ответ модели в историю для следующего шага
        user_history[user_id].append({"role": "assistant", "content": answer})

        # Telegram не принимает сообщения длиннее 4096 символов — нарезаем при необходимости
        if len(answer) > 4000:
            for i in range(0, len(answer), 4000):
                await message.answer(answer[i:i + 4000])
        else:
            await message.answer(answer)

    except Exception as e:
        await message.answer(f"Ошибка при обработке: {e}")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
