import logging
import asyncio
import os
from dotenv import load_dotenv
from telegram import Update, ChatPermissions
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from telegram.error import TelegramError

# 加载环境变量
load_dotenv()

# 从环境变量获取配置
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(id_) for id_ in os.getenv('ADMIN_IDS').split(',')]
DELETE_DELAY = int(os.getenv('DELETE_DELAY', 3))
BAN_MSG_DELAY = int(os.getenv('BAN_MSG_DELAY', 3))
VERIFY_TIMEOUT = int(os.getenv('VERIFY_TIMEOUT', 30))

# Webhook配置
WEBHOOK_HOST = os.getenv('WEBHOOK_HOST')  # 例如 'https://example.com'
WEBHOOK_PATH = os.getenv('WEBHOOK_PATH', f'/{BOT_TOKEN}')  # 例如 '/telegram-bot'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', 8443))
WEBHOOK_LISTEN = os.getenv('WEBHOOK_LISTEN', '0.0.0.0')  # 监听地址
SSL_CERT = os.getenv('SSL_CERT')  # SSL证书路径，可选
SSL_KEY = os.getenv('SSL_KEY')    # SSL密钥路径，可选
WEBHOOK_SECRET_TOKEN = os.getenv('WEBHOOK_SECRET_TOKEN')  # 可选的安全令牌

# 反向代理设置
BEHIND_PROXY = os.getenv('BEHIND_PROXY', 'False').lower() == 'true'

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 检查用户是否是管理员的函数
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# 存储待验证用户信息
pending_users = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # 记录原始消息ID
    original_message_id = update.message.message_id
    
    if is_admin(user_id):
        response_message = await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text="Hi Master 我是防御之盾，您的坚实护盾。"
        )
    else:
        response_message = await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text="你不是管理员，无权使用我。"
        )
    
    # 创建后台任务来处理延迟删除，而不是直接等待
    chat_id = update.effective_chat.id
    asyncio.create_task(delayed_delete_messages(
        chat_id, 
        [original_message_id, response_message.message_id], 
        context.bot, 
        DELETE_DELAY
    ))

# 添加一个通用的延迟删除消息函数
async def delayed_delete_messages(chat_id: int, message_ids: list, bot, delay: int):
    """在指定延迟后删除消息的通用函数"""
    await asyncio.sleep(delay)
    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except TelegramError as e:
            logging.error(f"删除消息失败 - 消息ID:{msg_id} - {e}")

async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理新成员入群事件"""
    chat_id = update.effective_chat.id
    logging.info(f"新成员入群事件触发 - Chat ID: {chat_id}")
    
    for new_member in update.message.new_chat_members:
        # 先限制用户权限
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=new_member.id,
                permissions=ChatPermissions(
                    can_send_messages=True,          # 只允许发送文本消息
                    can_send_other_messages=False,   # 禁止发送其他类型消息
                    can_add_web_page_previews=False,
                    can_send_polls=False,
                    can_change_info=False,
                    can_invite_users=False,
                    can_pin_messages=False
                )
            )
        except TelegramError as e:
            logging.error(f"Failed to restrict user {new_member.id} - {e}")
            continue

        # 记录用户加入时间和验证状态
        pending_users[new_member.id] = {
            'verified': False,
            'join_time': asyncio.get_event_loop().time(),
            'messages_to_delete': []  # 存储需要删除的消息ID
        }
        
        welcome_message = (
            f"欢迎新成员 {new_member.full_name} 加入！\n"
            f"请在30秒内发送 'hi' 完成验证，否则将被永久封禁。\n"
            f"用户ID: {new_member.id}\n"
            f"用户名: @{new_member.username if new_member.username else '无'}"
        )
        
        # 发送欢迎消息并保存消息ID
        welcome_msg = await context.bot.send_message(
            chat_id=chat_id,
            text=welcome_message
        )
        pending_users[new_member.id]['messages_to_delete'].append(welcome_msg.message_id)
        
        # 启动验证检查任务
        asyncio.create_task(check_verification(new_member.id, chat_id, context.bot))
        
        logging.info(f"New member joined: ID={new_member.id}, Name={new_member.full_name}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理用户消息"""
    user_id = update.effective_user.id
    message_text = update.message.text.lower()
    chat_id = update.effective_chat.id
    
    if user_id in pending_users and not pending_users[user_id]['verified']:
        # 记录用户发送的验证消息ID
        pending_users[user_id]['messages_to_delete'].append(update.message.message_id)
        
        if message_text == 'hi':
            pending_users[user_id]['verified'] = True
            try:
                # 解除用户限制
                await context.bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=user_id,
                    permissions=ChatPermissions(
                        can_send_messages=True,
                        can_send_other_messages=True,
                        can_add_web_page_previews=True,
                        can_send_polls=True,
                        can_invite_users=True,
                        can_pin_messages=False,  # 保持禁用置顶权限
                        can_change_info=False    # 保持禁用修改群信息权限
                    )
                )
            except TelegramError as e:
                logging.error(f"Failed to unrestrict user {user_id} - {e}")
            
            success_msg = await context.bot.send_message(
                chat_id=chat_id,
                text=f"验证成功，欢迎加入！"
            )
            # 记录验证成功消息ID
            pending_users[user_id]['messages_to_delete'].append(success_msg.message_id)

async def check_verification(user_id: int, chat_id: int, bot):
    """检查用户是否在30秒内完成验证"""
    await asyncio.sleep(VERIFY_TIMEOUT)
    if user_id in pending_users:
        # 删除所有相关消息
        for msg_id in pending_users[user_id]['messages_to_delete']:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except TelegramError as e:
                logging.error(f"Failed to delete message {msg_id} - {e}")

        if not pending_users[user_id]['verified']:
            try:
                # 直接封禁用户，不再解封
                await bot.ban_chat_member(
                    chat_id=chat_id, 
                    user_id=user_id,
                    revoke_messages=True  # 撤回该用户的所有消息
                )
                ban_msg = await bot.send_message(
                    chat_id=chat_id,
                    text=f"用户 ID:{user_id} 未在30秒内完成验证，已被永久封禁。"
                )
                # 等待指定时间后删除封禁提示消息
                await asyncio.sleep(BAN_MSG_DELAY)
                await bot.delete_message(chat_id=chat_id, message_id=ban_msg.message_id)
            except TelegramError as e:
                logging.error(f"Failed to ban user ID:{user_id} - {e}")
        
        del pending_users[user_id]

async def set_chinese(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理设置中文语言的命令"""
    try:
        # 记录原始消息ID
        original_message_id = update.message.message_id
        
        # 发送语言设置链接作为回复
        link = 'tg://setlanguage?lang=zhcncc'
        reply_message = await update.message.reply_text(
            text='[设置聪聪中文]('+link+')',
            parse_mode='Markdown'
        )
        
        # 创建后台任务来处理延迟删除
        asyncio.create_task(delayed_delete_messages(
            update.effective_chat.id,
            [original_message_id, reply_message.message_id],
            context.bot,
            DELETE_DELAY
        ))
            
    except TelegramError as e:
        logging.error(f"Failed to send language setting message - {e}")

async def delete_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理删除消息的命令 - 仅限管理员使用"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # 检查发送命令的用户是否是管理员
    if not is_admin(user_id):
        try:
            # 直接删除非管理员的命令消息，不做提示
            await update.message.delete()
        except TelegramError as e:
            logging.error(f"删除消息失败 - {e}")
        return
    
    # 检查是否是回复消息
    if not update.message.reply_to_message:
        try:
            error_msg = await update.message.reply_text("请回复要删除的消息。")
            # 创建后台任务来处理延迟删除
            asyncio.create_task(delayed_delete_messages(
                chat_id,
                [update.message.message_id, error_msg.message_id],
                context.bot,
                DELETE_DELAY
            ))
        except TelegramError as e:
            logging.error(f"删除消息失败 - {e}")
        return
        
    try:
        # 删除被回复的消息和命令消息
        await update.message.reply_to_message.delete()
        await update.message.delete()
    except TelegramError as e:
        logging.error(f"删除消息失败 - {e}")

if __name__ == '__main__':
    # 设置更详细的日志级别
    logging.getLogger().setLevel(logging.DEBUG)
    logging.info("启动机器人应用...")
    logging.info(f"Webhook 配置: URL={WEBHOOK_URL}, PORT={WEBHOOK_PORT}, PATH={WEBHOOK_PATH}")
    
    # 检查配置有效性
    if not WEBHOOK_HOST:
        logging.error("缺少 WEBHOOK_HOST 配置，请检查 .env 文件")
        exit(1)
    
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # 按照优先级顺序添加处理器
    # 1. 新成员处理器（最高优先级）
    application.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS, 
        handle_new_members
    ), group=1)
    
    # 2. 管理命令处理器
    application.add_handler(CommandHandler('start', start), group=2)
    application.add_handler(CommandHandler('d', delete_message), group=2)
    
    # 3. 中文语言设置处理器 - 提高优先级
    application.add_handler(MessageHandler(
        filters.Regex('^中文$') & (~filters.COMMAND), 
        set_chinese
    ), group=2)  # 与管理命令同级
    
    # 4. 普通消息处理器（最低优先级）
    application.add_handler(MessageHandler(
        filters.TEXT & (~filters.COMMAND), 
        handle_message
    ), group=3)
    
    # 添加错误处理器
    application.add_error_handler(lambda update, context: logging.error(f"Update {update} caused error {context.error}"))
    
    # 启动机器人，使用webhook
    logging.info(f"Starting bot with webhook on {WEBHOOK_URL}")
    
    # 设置webhook
    webhook_kwargs = {
        'webhook_url': WEBHOOK_URL,  # 完整URL，用于通知Telegram服务器
        'port': WEBHOOK_PORT,
        'listen': WEBHOOK_LISTEN,
        'url_path': WEBHOOK_PATH  # 使用url_path而不是path参数
    }
    
    # 添加SSL证书配置（如果有的话且不在反向代理后面）
    if SSL_CERT and SSL_KEY and not BEHIND_PROXY:
        webhook_kwargs['cert'] = SSL_CERT
        webhook_kwargs['key'] = SSL_KEY
    
    # 添加Secret Token（如果有的话）
    if WEBHOOK_SECRET_TOKEN:
        webhook_kwargs['secret_token'] = WEBHOOK_SECRET_TOKEN
    
    # 添加代理配置（如果在反向代理后面）
    if BEHIND_PROXY:
        webhook_kwargs['drop_pending_updates'] = True
        # 在反向代理后面时，通常不需要指定证书
        if 'cert' in webhook_kwargs:
            del webhook_kwargs['cert']
        if 'key' in webhook_kwargs:
            del webhook_kwargs['key']
    
    # 使用webhook启动机器人
    application.run_webhook(**webhook_kwargs)