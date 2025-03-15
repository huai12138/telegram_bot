import { Telegraf } from 'telegraf'
import { message } from 'telegraf/filters'
import { config } from './config.js';
import { blacklist } from './black.js';
process.removeAllListeners('warning');
class TelegramBot {
    constructor() {
        this.bot = new Telegraf(config.token);
        this.pendingUsers = new Map();
        this.setupMiddleware();
        this.setupCommands();
    }

    async deleteMessage(ctx, messageId, delay = config.messageDeleteDelay) {
        setTimeout(async () => {
            try {
                await ctx.deleteMessage(messageId);
            } catch (error) {
                console.error('删除消息失败:', error);
            }
        }, delay);
    }

    async isAdmin(ctx, userId) {
        const member = await ctx.getChatMember(userId);
        return ['administrator', 'creator'].includes(member.status);
    }

    setupMiddleware() {
        this.bot.use(async (ctx, next) => {
            try {
                await next();
            } catch (error) {
                console.error('Bot error:', error);
                const errorMsg = await ctx.reply('操作执行出错，请稍后重试！');
                this.deleteMessage(ctx, errorMsg.message_id);
            }
        });
    }

    setupCommands() {
        // 基础命令
        this.bot.start(this.handleStart.bind(this));
        this.bot.help(this.handleHelp.bind(this));
        this.bot.hears('Hi', this.handleVerification.bind(this));

        // 管理命令
        this.bot.command('mute', this.handleMute.bind(this));
        this.bot.command('unmute', this.handleUnmute.bind(this));
        this.bot.command('ban', this.handleBan.bind(this));
        this.bot.command('unban', this.handleUnban.bind(this));
        this.bot.command('d', this.handleDelete.bind(this));
        this.bot.command('mdel', this.handleMultiDelete.bind(this));
        this.bot.command('pin', this.handlePin.bind(this)); // 添加此行
        this.bot.command('unpin', this.handleUnpin.bind(this)); // 添加此行
        this.bot.command('admin', this.handleAdmin.bind(this));
        this.bot.command('unadmin', this.handleUnadmin.bind(this));

        // 事件处理
        this.bot.on(message('new_chat_members'), this.handleNewMember.bind(this));

        this.bot.hears('中文', async (ctx) => {
            const link = 'tg://setlanguage?lang=zhcncc';
            const text = `[聪聪中文](${link})`;

            // 删除用户的命令消息
            await ctx.deleteMessage(ctx.message.message_id);

            // 发送消息并获取消息ID
            const sentMessage = await ctx.reply(text, { parse_mode: 'Markdown' });

            // 延时删除bot的回复消息
            this.deleteMessage(ctx, sentMessage.message_id);
        });

        // 添加消息监听
        this.bot.on(message('text'), this.handleMessage.bind(this));
    }

    async handleStart(ctx) {
        const msg = await ctx.reply('欢迎使用');
        await ctx.deleteMessage(ctx.message.message_id); // 删除命令消息
        this.deleteMessage(ctx, msg.message_id);
    }

    async handleHelp(ctx) {
        const msg = await ctx.reply('执剑人');
        await ctx.deleteMessage(ctx.message.message_id); // 删除命令消息
        this.deleteMessage(ctx, msg.message_id);
    }

    async handleVerification(ctx) {
        const userId = ctx.from.id;
        if (this.pendingUsers.has(userId)) {
            const { timer, welcomeMessageId } = this.pendingUsers.get(userId);
            clearTimeout(timer);
            this.pendingUsers.delete(userId);

            // 获取群组信息
            const chatInfo = await ctx.getChat();
            const groupName = chatInfo.title;

            const successMessage = await ctx.reply(`验证成功,欢迎加入${groupName}!`);
            setTimeout(() => {
                ctx.deleteMessage(welcomeMessageId);
                ctx.deleteMessage(ctx.message.message_id);
                ctx.deleteMessage(successMessage.message_id);
            }, config.messageDeleteDelay);
        } else {
            ctx.reply('Hey there');
        }
    }

    // 修改 handleMute 方法
    async handleMute(ctx) {
        const userId = ctx.from.id;
        const user = ctx.message.reply_to_message;
        const messageId = ctx.message.message_id;
        if (!user) {
            const replyMessage = await ctx.reply('请回复一条消息来禁言该用户哦！');
            this.deleteMessage(ctx, replyMessage.message_id);
            await ctx.deleteMessage(messageId);
            return;
        }

        if (!await this.isAdmin(ctx, userId)) {
            await ctx.deleteMessage(messageId);
            return;
        }

        try {
            const memberId = user.from.id;
            await ctx.restrictChatMember(memberId, { can_send_messages: false });
            const replyMessage = await ctx.reply(`用户 ${user.from.first_name || memberId} 已禁言哦！`);
            await ctx.deleteMessage(messageId);
            this.deleteMessage(ctx, replyMessage.message_id);
        } catch (error) {
            const errorMsg = await ctx.reply('禁言用户时发生错误，请检查您的权限或成员状态！');
            this.deleteMessage(ctx, errorMsg.message_id);
        }
    }

    // 修改 handleUnmute 方法
    async handleUnmute(ctx) {
        const userId = ctx.from.id;
        const user = ctx.message.reply_to_message;
        const messageId = ctx.message.message_id;
        if (!user) {
            const replyMessage = await ctx.reply('请回复一条消息来解除该用户的禁言哦！');
            this.deleteMessage(ctx, replyMessage.message_id);
            await ctx.deleteMessage(messageId);
            return;
        }

        if (!await this.isAdmin(ctx, userId)) {
            await ctx.deleteMessage(messageId);
            return;
        }

        try {
            const memberId = user.from.id;
            await ctx.restrictChatMember(memberId, { can_send_messages: true });
            const replyMessage = await ctx.reply(`用户 ${user.from.first_name || memberId} 已解除禁言哦！`);
            await ctx.deleteMessage(messageId);
            this.deleteMessage(ctx, replyMessage.message_id);
        } catch (error) {
            const errorMsg = await ctx.reply('解除禁言时发生错误，请检查您的权限或成员状态！');
            this.deleteMessage(ctx, errorMsg.message_id);
        }
    }

    // 修改 handleBan 方法
    async handleBan(ctx) {
        const userId = ctx.from.id;
        const user = ctx.message.reply_to_message;
        const messageId = ctx.message.message_id;
        if (!user) {
            const replyMessage = await ctx.reply('请回复一条消息来封禁该用户哦！！');
            this.deleteMessage(ctx, replyMessage.message_id);
            await ctx.deleteMessage(messageId);
            return;
        }

        if (!await this.isAdmin(ctx, userId)) {
            await ctx.deleteMessage(messageId);
            return;
        }

        try {
            const memberId = user.from.id;
            await ctx.deleteMessage(messageId);
            await ctx.banChatMember(memberId);
            const replyMessage = await ctx.reply(`用户 ${user.from.first_name || memberId} 已被封禁哦！`);
            this.deleteMessage(ctx, replyMessage.message_id);
        } catch (error) {
            const errorMsg = await ctx.reply('封禁用户时发生错误，请检查您的权限或成员状态！');
            this.deleteMessage(ctx, errorMsg.message_id);
        }
    }

    // 修改 handleUnban 方法 
    async handleUnban(ctx) {
        const userId = ctx.from.id;
        const user = ctx.message.reply_to_message;
        const messageId = ctx.message.message_id;
        if (!user) {
            const replyMessage = await ctx.reply('请回复一条消息来解封该用户哦！');
            this.deleteMessage(ctx, replyMessage.message_id);
            await ctx.deleteMessage(messageId);
            return;
        }

        if (!await this.isAdmin(ctx, userId)) {
            await ctx.deleteMessage(messageId);
            return;
        }

        try {
            const memberId = user.from.id;
            const targetMember = await ctx.getChatMember(memberId);
            if (targetMember.status !== 'kicked') {
                const replyMessage = await ctx.reply('该用户并未被封禁哦！');
                await ctx.deleteMessage(messageId);
                this.deleteMessage(ctx, replyMessage.message_id);
                return;
            }

            await ctx.unbanChatMember(memberId);
            const replyMessage = await ctx.reply(`用户 ${user.from.first_name || memberId} 已解封哦！`);
            await ctx.deleteMessage(messageId);
            this.deleteMessage(ctx, replyMessage.message_id);
        } catch (error) {
            const errorMsg = await ctx.reply('解封用户时发生错误，请检查您的权限或成员状态！');
            this.deleteMessage(ctx, errorMsg.message_id);
        }
    }

    // 修改 handleDelete 方法
    async handleDelete(ctx) {
        const userId = ctx.from.id;
        const user = ctx.message.reply_to_message;
        const messageId = ctx.message.message_id;
        if (!user) {
            const replyMessage = await ctx.reply('请回复一条消息来删除消息哦！');
            this.deleteMessage(ctx, replyMessage.message_id);
            await ctx.deleteMessage(messageId);
            return;
        }

        if (!await this.isAdmin(ctx, userId)) {
            await ctx.deleteMessage(messageId);
            return;
        }

        try {
            await ctx.deleteMessage(ctx.message.reply_to_message.message_id);
            await ctx.deleteMessage(messageId);
            const replyMessage = await ctx.reply(`用户 ${user.from.first_name || user.from.id} 消息已删除哦！`);
            this.deleteMessage(ctx, replyMessage.message_id);
        } catch (error) {
            const errorMsg = await ctx.reply('删除用户消息时发生错误，请检查您的权限或成员状态！');
            this.deleteMessage(ctx, errorMsg.message_id);
        }
    }

    // 修改 handleMultiDelete 方法
    async handleMultiDelete(ctx) {
        const userId = ctx.from.id;
        const user = ctx.message.reply_to_message;
        const messageId = ctx.message.message_id;
        if (!user) {
            const replyMessage = await ctx.reply('请回复一条消息，我将删除该消息之后的所有消息！');
            this.deleteMessage(ctx, replyMessage.message_id);
            await ctx.deleteMessage(messageId);
            return;
        }

        if (!await this.isAdmin(ctx, userId)) {
            await ctx.deleteMessage(messageId);
            return;
        }

        try {
            const targetMessageId = user.message_id;
            for (let i = targetMessageId; i <= messageId; i++) {
                try {
                    await ctx.deleteMessage(i);
                } catch (error) {
                    continue;
                }
            }

            const replyMessage = await ctx.reply('批量删除消息完成！');
            this.deleteMessage(ctx, replyMessage.message_id);
        } catch (error) {
            const errorMsg = await ctx.reply('批量删除消息时发生错误，请检查您的权限！');
            this.deleteMessage(ctx, errorMsg.message_id);
        }
    }

    async handlePin(ctx) {
        const userId = ctx.from.id;
        const replyToMessage = ctx.message.reply_to_message;
        const messageId = ctx.message.message_id;

        if (!replyToMessage) {
            const replyMessage = await ctx.reply('请回复一条消息来置顶该消息！');
            this.deleteMessage(ctx, replyMessage.message_id);
            await ctx.deleteMessage(messageId);
            return;
        }

        if (!await this.isAdmin(ctx, userId)) {
            await ctx.deleteMessage(messageId);
            return;
        }

        try {
            await ctx.pinChatMessage(replyToMessage.message_id);
            const replyMessage = await ctx.reply('消息已成功置顶！');
            await ctx.deleteMessage(messageId);
            this.deleteMessage(ctx, replyMessage.message_id);
        } catch (error) {
            const errorMsg = await ctx.reply('置顶消息时发生错误，请检查您的权限！');
            this.deleteMessage(ctx, errorMsg.message_id);
        }
    }

    async handleUnpin(ctx) {
        const userId = ctx.from.id;
        const messageId = ctx.message.message_id;

        if (!await this.isAdmin(ctx, userId)) {
            await ctx.deleteMessage(messageId);
            return;
        }

        try {
            await ctx.unpinChatMessage();
            const replyMessage = await ctx.reply('消息已取消置顶！');
            await ctx.deleteMessage(messageId);
            this.deleteMessage(ctx, replyMessage.message_id);
        } catch (error) {
            const errorMsg = await ctx.reply('取消置顶消息时发生错误，请检查您的权限！');
            this.deleteMessage(ctx, errorMsg.message_id);
        }
    }

    async handleAdmin(ctx) {
        const userId = ctx.from.id;
        const user = ctx.message.reply_to_message;
        const messageId = ctx.message.message_id;

        if (!user) {
            const replyMessage = await ctx.reply('请回复一条消息来设置该用户为管理员！');
            this.deleteMessage(ctx, replyMessage.message_id);
            await ctx.deleteMessage(messageId);
            return;
        }

        if (!await this.isAdmin(ctx, userId)) {
            await ctx.deleteMessage(messageId);
            return;
        }

        try {
            const memberId = user.from.id;
            await ctx.promoteChatMember(memberId, {
                can_manage_chat: true,
                can_delete_messages: true,
                can_restrict_members: true,
                can_pin_messages: true
            });
            const replyMessage = await ctx.reply(`用户 ${user.from.first_name || memberId} 已被设置为管理员！`);
            await ctx.deleteMessage(messageId);
            this.deleteMessage(ctx, replyMessage.message_id);
        } catch (error) {
            const errorMsg = await ctx.reply('设置管理员失败，请检查您的权限！');
            this.deleteMessage(ctx, errorMsg.message_id);
        }
    }

    async handleUnadmin(ctx) {
        const userId = ctx.from.id;
        const user = ctx.message.reply_to_message;
        const messageId = ctx.message.message_id;

        if (!user) {
            const replyMessage = await ctx.reply('请回复一条消息来移除该用户的管理员权限！');
            this.deleteMessage(ctx, replyMessage.message_id);
            await ctx.deleteMessage(messageId);
            return;
        }

        if (!await this.isAdmin(ctx, userId)) {
            await ctx.deleteMessage(messageId);
            return;
        }

        try {
            const memberId = user.from.id;
            await ctx.promoteChatMember(memberId, {
                can_manage_chat: false,
                can_delete_messages: false,
                can_restrict_members: false,
                can_pin_messages: false
            });
            const replyMessage = await ctx.reply(`用户 ${user.from.first_name || memberId} 已被移除管理员权限！`);
            await ctx.deleteMessage(messageId);
            this.deleteMessage(ctx, replyMessage.message_id);
        } catch (error) {
            const errorMsg = await ctx.reply('移除管理员权限失败，请检查您的权限！');
            this.deleteMessage(ctx, errorMsg.message_id);
        }
    }

    async handleNewMember(ctx) {
        const newMember = ctx.message.new_chat_members[0];
        if (newMember.is_bot) return;

        const userId = newMember.id;
        const chatInfo = await ctx.getChat();
        const groupName = chatInfo.title;

        const welcomeMessage = await ctx.reply(
            `欢迎 ${newMember.first_name} 加入${groupName}!\n请在30秒内发送 "Hi" 完成验证,否则将被禁言。`
        );

        const timer = setTimeout(async () => {
            if (this.pendingUsers.has(userId)) {
                try {
                    await ctx.restrictChatMember(userId, { can_send_messages: false });
                    const timeoutMessage = await ctx.reply(
                        `用户 ${newMember.first_name} 未完成${groupName}的验证,已被禁言。`
                    );
                    this.deleteMessage(ctx, timeoutMessage.message_id);
                    this.deleteMessage(ctx, welcomeMessage.message_id);
                } catch (error) {
                    console.error('禁言失败:', error);
                }
                this.pendingUsers.delete(userId);
            }
        }, 30000);

        this.pendingUsers.set(userId, { timer, welcomeMessageId: welcomeMessage.message_id });
    }

    async handleMessage(ctx) {
        const text = ctx.message.text;

        // 检查消息是否包含黑名单内容
        const matchesBlacklist = blacklist.some(pattern => {
            // 如果是正则表达式对象
            if (pattern instanceof RegExp) {
                return pattern.test(text);
            }
            
            // 如果是包含通配符的字符串
            if (typeof pattern === 'string' && (pattern.includes('*') || pattern.includes('?'))) {
                const regexPattern = pattern
                    .replace(/[.+?^${}()|[\]\\]/g, '\\$&') // 转义特殊字符
                    .replace(/\*/g, '.*')                   // * 转换为 .*
                    .replace(/\?/g, '.');                   // ? 转换为 .
                return new RegExp(regexPattern).test(text);
            }

            // 普通字符串，区分大小写完全匹配
            if (pattern.startsWith('"') && pattern.endsWith('"')) {
                return text.includes(pattern.slice(1, -1));
            }

            // 默认：不区分大小写的包含匹配
            return text.toLowerCase().includes(pattern.toLowerCase());
        });

        if (matchesBlacklist) {
            try {
                await ctx.deleteMessage(ctx.message.message_id);
                const warningMsg = await ctx.reply('检测到不当内容，消息已被删除');
                this.deleteMessage(ctx, warningMsg.message_id);
            } catch (error) {
                console.error('删除违规消息失败:', error);
            }
        }
    }

    async launch() {
        await this.bot.launch();
        console.log('Bot started successfully');
    }
}

const bot = new TelegramBot();
bot.launch();

process.once('SIGINT', () => bot.bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.bot.stop('SIGTERM'));