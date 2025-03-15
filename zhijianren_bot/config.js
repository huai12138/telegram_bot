export const config = {
  token: '',
  messageDeleteDelay: 10000,
  verificationTimeout: 30000,
  messages: {
    welcome: (firstName, groupName) => `欢迎 ${firstName} 加入${groupName}!\n请在30秒内发送 "hi" 完成验证,否则将被禁言。`,
    verificationSuccess: '验证成功,欢迎加入群组!',
    needAdminRights: '抱歉，只有管理员或群主可以执行此操作！'
  }
};
