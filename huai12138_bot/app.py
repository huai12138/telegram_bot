import logging
import asyncio
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from block import BlockManager
from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 从环境变量获取配置
TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = os.getenv('ADMIN_ID')

# 验证必要的环境变量
if not TOKEN or not ADMIN_ID:
    raise ValueError("请在.env文件中设置 BOT_TOKEN 和 ADMIN_ID")

# 替换 BANNED_USERS 集合
block_manager = BlockManager()

# 存储需要验证的用户和验证开始时间
pending_verification = {}  # 格式: {user_id: start_time}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /start 命令"""
    user_id = str(update.effective_user.id)
    
    # 如果用户被封禁，则不需要验证
    if block_manager.is_blocked(user_id):
        await update.message.reply_text('您已被封禁，无法使用此机器人。')
        return
        
    # 添加用户到验证列表
    pending_verification[user_id] = time.time()
    
    # 发送验证提示
    await update.message.reply_text('欢迎使用！请在30秒内发送 "hi" 完成验证，否则将被自动封禁。')
    
    # 启动验证检查任务
    asyncio.create_task(check_verification(user_id, context))

async def check_verification(user_id: str, context: ContextTypes.DEFAULT_TYPE):
    """检查用户是否在30秒内完成验证"""
    await asyncio.sleep(30)  # 等待30秒
    
    if user_id in pending_verification:
        # 用户未能完成验证
        del pending_verification[user_id]
        block_manager.block_user(user_id)
        
        try:
            await context.bot.send_message(user_id, "您未能在30秒内完成验证，已被自动封禁。")
            await context.bot.send_message(ADMIN_ID, f"用户 {user_id} 未能完成验证，已被自动封禁。")
        except Exception as e:
            logging.error(f"发送封禁通知时出错: {e}")

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /ban 命令"""
    if str(update.effective_user.id) != ADMIN_ID:
        await update.message.reply_text("只有管理员可以使用此命令。")
        return
    
    try:
        # 检查是否是回复消息
        if update.message.reply_to_message:
            original_text = update.message.reply_to_message.text
            if "用户ID: " in original_text:
                user_id = original_text.split("用户ID: ")[1].split("\n")[0]
                block_manager.block_user(user_id)
                await update.message.reply_text(f"已封禁用户 {user_id}")
                await context.bot.send_message(user_id, "您已被管理员封禁。")
                return
        
        # 如果不是回复消息，则检查命令参数
        if not context.args:
            await update.message.reply_text("请提供要封禁的用户ID。\n用法: /ban <用户ID> 或回复包含用户ID的消息")
            return
            
        user_id = context.args[0]
        block_manager.block_user(user_id)
        await update.message.reply_text(f"已封禁用户 {user_id}")
        await context.bot.send_message(user_id, "您已被管理员封禁。")
    except Exception as e:
        await update.message.reply_text(f"封禁用户时出错: {str(e)}")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /unban 命令"""
    if str(update.effective_user.id) != ADMIN_ID:
        await update.message.reply_text("只有管理员可以使用此命令。")
        return
    
    try:
        # 检查是否是回复消息
        if update.message.reply_to_message:
            original_text = update.message.reply_to_message.text
            if "用户ID: " in original_text:
                user_id = original_text.split("用户ID: ")[1].split("\n")[0]
                if block_manager.unblock_user(user_id):
                    await update.message.reply_text(f"已解封用户 {user_id}")
                    await context.bot.send_message(user_id, "您已被管理员解封。")
                else:
                    await update.message.reply_text(f"用户 {user_id} 未被封禁")
                return

        # 如果不是回复消息，则检查命令参数
        if not context.args:
            await update.message.reply_text("请提供要解封的用户ID。\n用法: /unban <用户ID> 或回复包含用户ID的消息")
            return
            
        user_id = context.args[0]
        if block_manager.unblock_user(user_id):
            await update.message.reply_text(f"已解封用户 {user_id}")
            await context.bot.send_message(user_id, "您已被管理员解封。")
        else:
            await update.message.reply_text(f"用户 {user_id} 未被封禁")
    except Exception as e:
        await update.message.reply_text(f"解封用户时出错: {str(e)}")

async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """将用户消息转发给管理员"""
    message = update.message
    user = message.from_user
    chat_id = message.chat.id
    user_id = str(chat_id)
    
    # 检查用户是否被封禁
    if block_manager.is_blocked(user_id):
        await message.reply_text("您已被封禁，无法使用此机器人。")
        return
    
    # 检查是否是待验证用户
    if user_id in pending_verification:
        # 检查是否发送了正确的验证消息
        if message.text and message.text.lower() == "hi":
            # 验证成功
            del pending_verification[user_id]
            await message.reply_text("验证成功！您现在可以正常使用机器人了。请直接发送消息，我会转发给管理员。")
            
            # 通知管理员
            admin_msg = f"新用户完成验证:\n用户名: {user.first_name} (@{user.username if user.username else '无用户名'})\n用户ID: {user_id}"
            await context.bot.send_message(ADMIN_ID, admin_msg)
            return
        else:
            # 提醒用户发送正确的验证消息
            await message.reply_text('请发送 "hi" 完成验证。')
            return
    
    if str(chat_id) != ADMIN_ID:  # 如果不是管理员发送的消息
        try:
            # 转发给管理员，并在消息前加上用户信息
            sender_info = f"来自用户: {user.first_name} (@{user.username if user.username else '无用户名'})\n"
            sender_info += f"用户ID: {chat_id}\n"
            sender_info += "------------------------\n"
            
            # 首先发送用户信息
            await context.bot.send_message(ADMIN_ID, sender_info)
            # 然后转发原始消息
            await message.forward(ADMIN_ID)
            
            # 保存用户ID到context，用于回复
            if 'user_chat_ids' not in context.bot_data:
                context.bot_data['user_chat_ids'] = {}
            context.bot_data['user_chat_ids'][str(chat_id)] = chat_id
            
            await message.reply_text("消息已转发给管理员，请等待回复。")
        except Exception as e:
            logging.error(f"转发消息时出错: {e}")
            await message.reply_text("转发消息时出错。")
    
    else:  # 如果是管理员发送的消息
        # 检查是否是回复其他消息
        if message.reply_to_message:
            try:
                # 获取原始用户信息
                original_text = message.reply_to_message.text
                if "用户ID: " in original_text:
                    user_id = original_text.split("用户ID: ")[1].split("\n")[0]
                    
                    # 检查是否是封禁命令
                    if message.text.lower() == "/ban":
                        block_manager.block_user(user_id)
                        await message.reply_text(f"已封禁用户 {user_id}")
                        await context.bot.send_message(user_id, "您已被管理员封禁。")
                        return
                    # 检查是否是解封命令
                    elif message.text.lower() == "/unban":
                        if block_manager.unblock_user(user_id):
                            await message.reply_text(f"已解封用户 {user_id}")
                            await context.bot.send_message(user_id, "您已被管理员解封。")
                        else:
                            await message.reply_text(f"用户 {user_id} 未被封禁")
                        return
                        
                    # 发送普通回复消息给用户
                    await context.bot.send_message(user_id, message.text)
                    await message.reply_text("回复已发送。")
                else:
                    await message.reply_text("请回复包含用户ID的消息。")
            except Exception as e:
                logging.error(f"回复消息时出错: {e}")
                await message.reply_text("发送回复时出错。")

def main():
    """启动机器人"""
    # 创建应用
    application = Application.builder().token(TOKEN).build()

    # 添加处理程序
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ban", ban))
    application.add_handler(CommandHandler("unban", unban))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, forward_to_admin))

    # 获取运行模式
    MODE = os.getenv('MODE', 'poll')  # 默认为polling模式
    
    if MODE == 'webhook':
        # 从环境变量获取webhook配置
        WEBHOOK_HOST = os.getenv('WEBHOOK_HOST')
        WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', 8443))
        WEBHOOK_LISTEN = os.getenv('WEBHOOK_LISTEN', '0.0.0.0')
        WEBHOOK_SECRET_TOKEN = os.getenv('WEBHOOK_SECRET_TOKEN')
        WEBHOOK_PATH = os.getenv('WEBHOOK_PATH', '')
        
        # 确保WEBHOOK_PATH正确格式化
        if WEBHOOK_PATH and not WEBHOOK_PATH.startswith('/'):
            WEBHOOK_PATH = f'/{WEBHOOK_PATH}'
            
        # 确保WEBHOOK_HOST不以/结尾
        if WEBHOOK_HOST and WEBHOOK_HOST.endswith('/'):
            WEBHOOK_HOST = WEBHOOK_HOST[:-1]
            
        # 构建完整的webhook URL
        webhook_url = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
        
        # 输出配置信息
        logging.info(f"使用webhook模式启动机器人")
        logging.info(f"监听地址: {WEBHOOK_LISTEN}:{WEBHOOK_PORT}")
        logging.info(f"Webhook URL: {webhook_url}")
        
        # 如果定义了路径，则删除开头的斜杠用于url_path参数
        url_path = WEBHOOK_PATH.lstrip('/') if WEBHOOK_PATH else TOKEN
        
        # 启动webhook模式
        application.run_webhook(
            listen=WEBHOOK_LISTEN,
            port=WEBHOOK_PORT,
            url_path=url_path,
            webhook_url=webhook_url,
            secret_token=WEBHOOK_SECRET_TOKEN
        )
    else:
        # 使用polling模式
        logging.info("使用polling模式启动机器人")
        application.run_polling()

if __name__ == '__main__':
    main()