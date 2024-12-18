import telebot
from telebot import types
import sqlite3
import matplotlib.pyplot as plt
from io import BytesIO

bot = telebot.TeleBot('///')

def init_db():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    # Drop existing tables to recreate with correct schema
    c.execute('DROP TABLE IF EXISTS tasks')
    c.execute('DROP TABLE IF EXISTS stages')
    
    c.execute('''CREATE TABLE tasks 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  task_name TEXT,
                  progress INTEGER DEFAULT 0,
                  completed INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE stages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_id INTEGER,
                  stage_name TEXT,
                  completed INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

@bot.message_handler(func=lambda message: message.text == '📋 Мои этапы')
def show_all_stages(message):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('''
        SELECT t.task_name, s.stage_name, s.completed 
        FROM stages s 
        JOIN tasks t ON s.task_id = t.id 
        WHERE t.user_id = ?
    ''', (message.from_user.id,))
    stages = c.fetchall()
    conn.close()

    if not stages:
        bot.reply_to(message, "У вас пока нет этапов в задачах")
        return

    text = "Ваши этапы:\n\n"
    for task_name, stage_name, completed in stages:
        status = "✅" if completed else "⭕"
        text += f"{status} {task_name}: {stage_name}\n"

    bot.reply_to(message, text)

def process_task_name(message):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('INSERT INTO tasks (user_id, task_name) VALUES (?, ?)',
              (message.from_user.id, message.text))
    task_id = c.lastrowid
    conn.commit()
    conn.close()

    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("Добавить этап", callback_data=f"add_stage_{task_id}"),
        types.InlineKeyboardButton("Пропустить этапы", callback_data="skip_stages")
    )
    bot.reply_to(message, "Задача добавлена! Выберите действие:", reply_markup=keyboard)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    text = """👋 Привет! Я План-бот для управления задачами.

Доступные команды:
/start - Начать работу
/help - Показать это сообщение

Используйте кнопки меню для:
- Просмотра статистики задач
- Добавления новых задач
- Удаления задач
- Управления этапами задач
- Просмотра созданных задач"""
    
    show_main_menu(message.chat.id)
    bot.reply_to(message, text)

def show_main_menu(chat_id):
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        '📊 Статистика', 
        '➕ Добавить задачу', 
        '❌ Удалить задачу',
        '📝 Управление задачами',
        '📋 Мои этапы'
    ]
    keyboard.add(*[types.KeyboardButton(text) for text in buttons])
    bot.send_message(chat_id, "Выберите действие:", reply_markup=keyboard)

def show_task_stages(chat_id, task_id):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('SELECT id, stage_name, completed FROM stages WHERE task_id = ?', (task_id,))
    stages = c.fetchall()
    conn.close()

    if not stages:
        bot.send_message(chat_id, "У этой задачи нет этапов")
        return

    keyboard = types.InlineKeyboardMarkup()
    for stage_id, stage_name, completed in stages:
        status = "✅" if completed else "⭕"
        keyboard.add(types.InlineKeyboardButton(
            f"{status} {stage_name}", 
            callback_data=f"toggle_stage_{stage_id}"
        ))
    
    bot.send_message(chat_id, "Выберите этап для отметки:", reply_markup=keyboard)

    keyboard.add(types.InlineKeyboardButton("✅ Отметить задачу выполненной", callback_data=f"complete_task_{task_id}"))
    
    if stages:
        for stage_id, stage_name, completed in stages:
            status = "✅" if completed else "⭕"
            keyboard.add(types.InlineKeyboardButton(
                f"{status} {stage_name}", 
                callback_data=f"toggle_stage_{stage_id}"
            ))
    
    c.execute('SELECT task_name FROM tasks WHERE id = ?', (task_id,))
    task_name = c.fetchone()[0]
    conn.close()
    
    bot.send_message(chat_id, f"Задача: {task_name}\nВыберите действие:", reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text == '📝 Управление задачами')
def handle_stages(message):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('SELECT id, task_name, completed FROM tasks WHERE user_id = ?', (message.from_user.id,))
    tasks = c.fetchall()
    conn.close()

    if not tasks:
        bot.reply_to(message, "У вас нет активных задач")
        return

    keyboard = types.InlineKeyboardMarkup()
    for task_id, task_name, completed in tasks:
        status = "✅" if completed else "⭕"
        keyboard.add(types.InlineKeyboardButton(
            f"{status} {task_name}", 
            callback_data=f"confirm_complete_{task_id}"
        ))
    
    bot.reply_to(message, "Выберите задачу для выполнения:", reply_markup=keyboard)
@bot.message_handler(func=lambda message: message.text == '➕ Добавить задачу')
def add_task_start(message):
    msg = bot.reply_to(message, "Введите название задачи:")
    bot.register_next_step_handler(msg, process_task_name)

@bot.message_handler(func=lambda message: message.text == '❌ Удалить задачу')
def delete_task_start(message):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('SELECT id, task_name FROM tasks WHERE user_id = ?', (message.from_user.id,))
    tasks = c.fetchall()
    conn.close()

    if not tasks:
        bot.reply_to(message, "У вас нет задач для удаления")
        return

    keyboard = types.InlineKeyboardMarkup()
    for task_id, task_name in tasks:
        keyboard.add(types.InlineKeyboardButton(task_name, callback_data=f"delete_{task_id}"))
    
    bot.reply_to(message, "Выберите задачу для удаления:", reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text == '📊 Статистика')
def handle_statistics(message):
    show_statistics(message)


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data.startswith('toggle_task_'):
        task_id = int(call.data.split('_')[2])
        conn = sqlite3.connect('tasks.db')
        c = conn.cursor()
        c.execute('UPDATE tasks SET completed = 1 - completed, progress = CASE WHEN completed = 0 THEN 100 ELSE 0 END WHERE id = ?', (task_id,))
        conn.commit()
        conn.close()
        handle_stages(call.message)

    if call.data.startswith('confirm_complete_'):
        task_id = int(call.data.split('_')[2])
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton("✅ Да", callback_data=f"complete_task_{task_id}"),
            types.InlineKeyboardButton("❌ Нет", callback_data="cancel_complete")
        )
        bot.edit_message_text(
            "Отметить задачу как полностью выполненную?",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )
    if call.data.startswith('add_stage_'):
        task_id = int(call.data.split('_')[2])
        msg = bot.send_message(call.message.chat.id, "Введите название этапа:")
        bot.register_next_step_handler(msg, process_stage_name, task_id)
    
    if call.data.startswith('show_stages_'):
        task_id = int(call.data.split('_')[2])
        show_task_stages(call.message.chat.id, task_id)
        
    if call.data.startswith('confirm_complete_'):
        task_id = int(call.data.split('_')[2])
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton("✅ Да", callback_data=f"complete_task_{task_id}"),
            types.InlineKeyboardButton("❌ Нет", callback_data="cancel_complete")
        )
        bot.edit_message_text(
            "Отметить задачу как полностью выполненную?",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )
    
    elif call.data.startswith('complete_task_'):
        task_id = int(call.data.split('_')[2])
        conn = sqlite3.connect('tasks.db')
        c = conn.cursor()
        c.execute('UPDATE tasks SET progress = 100, completed = 1 WHERE id = ?', (task_id,))
        conn.commit()
        conn.close()
        bot.edit_message_text(
            "✅ Задача отмечена как выполненная!",
            call.message.chat.id,
            call.message.message_id
        )
        handle_stages(call.message)
    
    elif call.data == "cancel_complete":
        handle_stages(call.message)

    elif call.data.startswith('toggle_stage_'):
        stage_id = int(call.data.split('_')[2])
        conn = sqlite3.connect('tasks.db')
        c = conn.cursor()
        c.execute('SELECT task_id FROM stages WHERE id = ?', (stage_id,))
        result = c.fetchone()
        
        if result:
            task_id = result[0]
            c.execute('''SELECT COUNT(*) FROM stages WHERE task_id = ?''', (task_id,))
            total_stages = c.fetchone()[0]
            
            c.execute('UPDATE stages SET completed = 1 - completed WHERE id = ?', (stage_id,))
            if total_stages > 0:
                progress_per_stage = 100 / total_stages
                c.execute('UPDATE tasks SET progress = progress + ? WHERE id = ?', 
                         (progress_per_stage, task_id))
            conn.commit()
            show_task_stages(call.message.chat.id, task_id)
        conn.close()

    elif call.data == "skip_stages":
        bot.answer_callback_query(call.id, "Этапы пропущены")
        show_main_menu(call.message.chat.id)
        
    elif call.data.startswith('delete_'):
        task_id = int(call.data.split('_')[1])
        conn = sqlite3.connect('tasks.db')
        c = conn.cursor()
        c.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        c.execute('DELETE FROM stages WHERE task_id = ?', (task_id,))
        conn.commit()
        conn.close()
        
        bot.edit_message_text("Задача удалена!", 
                            call.message.chat.id,
                            call.message.message_id)
    
    
        
    elif call.data.startswith('complete_stage_'):
        stage_id = int(call.data.split('_')[2])
        conn = sqlite3.connect('tasks.db')
        c = conn.cursor()
        c.execute('''SELECT task_id, 
                    (SELECT COUNT(*) FROM stages WHERE task_id = s.task_id) as total_stages 
                    FROM stages s WHERE id = ?''', (stage_id,))
        task_id, total_stages = c.fetchone()
        
        c.execute('UPDATE stages SET completed = 1 WHERE id = ?', (stage_id,))
        progress_per_stage = 100 / total_stages
        c.execute('UPDATE tasks SET progress = progress + ? WHERE id = ?', 
                 (progress_per_stage, task_id))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "Этап выполнен!")

def process_stage_name(message, task_id):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('INSERT INTO stages (task_id, stage_name) VALUES (?, ?)',
              (task_id, message.text))
    conn.commit()
    conn.close()

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("Добавить ещё этап", callback_data=f"add_stage_{task_id}"),
        types.InlineKeyboardButton("Завершить", callback_data="skip_stages")
    )
    bot.reply_to(message, "Этап добавлен! Хотите добавить ещё?", reply_markup=keyboard)


def show_statistics(message):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('SELECT task_name, progress FROM tasks WHERE user_id = ?', 
              (message.from_user.id,))
    tasks = c.fetchall()
    conn.close()

    if not tasks:
        bot.reply_to(message, "У вас пока нет активных задач")
        return

    plt.figure(figsize=(10, 6))
    names = [task[0] for task in tasks]
    progress = [max(0, min(100, task[1])) for task in tasks]
    plt.bar(names, progress)
    plt.title('Прогресс по задачам')
    plt.xlabel('Задачи')
    plt.ylabel('Прогресс (%)')
    plt.ylim(0, 100)
    plt.xticks(rotation=45)

    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close()

    bot.send_photo(message.chat.id, buf)

if __name__ == '__main__':
    init_db()
    bot.polling(none_stop=True)
