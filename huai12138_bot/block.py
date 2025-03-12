import json
import os

class BlockManager:
    def __init__(self, file_path='blocked_users.json'):
        self.file_path = file_path
        self.blocked_users = set()
        self.load_blocked_users()

    def load_blocked_users(self):
        """从文件加载封禁用户列表"""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self.blocked_users = set(json.load(f))
            except Exception as e:
                print(f"加载封禁用户列表时出错: {e}")

    def save_blocked_users(self):
        """保存封禁用户列表到文件"""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(list(self.blocked_users), f)
        except Exception as e:
            print(f"保存封禁用户列表时出错: {e}")

    def block_user(self, user_id: str) -> bool:
        """封禁用户"""
        self.blocked_users.add(user_id)
        self.save_blocked_users()
        return True

    def unblock_user(self, user_id: str) -> bool:
        """解封用户"""
        if user_id in self.blocked_users:
            self.blocked_users.remove(user_id)
            self.save_blocked_users()
            return True
        return False

    def is_blocked(self, user_id: str) -> bool:
        """检查用户是否被封禁"""
        return user_id in self.blocked_users

    def get_blocked_users(self) -> set:
        """获取所有被封禁的用户"""
        return self.blocked_users