#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试工具 - 专门用于测试消息接收和处理
"""

import asyncio
import threading
from telethon import events
from telethon import types


class DebugTools:
    def __init__(self, app):
        self.app = app
        self.debug_handler = None
        self.debug_active = False

    def start_raw_message_debug(self):
        """启动原始消息调试 - 显示所有收到的消息"""
        if self.debug_active:
            self.app.log_message("🐛 调试模式已经在运行")
            return

        if not self.app.selected_accounts:
            self.app.log_message("❌ 请先选择账号")
            return

        self.debug_active = True
        self.app.log_message("🐛 启动原始消息调试模式...")

        for phone in self.app.selected_accounts:
            if phone in self.app.clients:
                client = self.app.clients[phone]
                self._add_debug_handler(phone, client)

    def _add_debug_handler(self, phone, client):
        """为客户端添加调试处理器"""
        try:
            @client.on(events.NewMessage(chats=(types.Chat, types.Channel)))
            async def debug_message_handler(event):
                try:
                    message = event.message
                    chat = await message.get_chat()

                    chat_title = getattr(chat, 'title', 'Private')
                    chat_id = chat.id
                    message_text = (message.text or '[非文本]')[:100]

                    # 获取发送者信息
                    sender_info = "Unknown"
                    if message.sender:
                        if hasattr(message.sender, 'username') and message.sender.username:
                            sender_info = f"@{message.sender.username}"
                        elif hasattr(message.sender, 'first_name'):
                            sender_info = message.sender.first_name or "Unknown"

                    # 详细调试信息
                    debug_msg = f"🐛 RAW [{phone}]: {chat_title}(ID:{chat_id}) | {sender_info} | {message_text}"
                    self.app.root.after(0, lambda msg=debug_msg: self.app.log_message(msg))

                    # 如果包含关键词，特别标注
                    keywords = [k.strip() for k in self.app.target_keywords_var.get().split(',') if k.strip()]
                    if keywords and message.text:
                        for keyword in keywords:
                            if keyword in message.text:
                                highlight_msg = f"🎯 关键词匹配! [{phone}]: '{keyword}' 在 '{message.text[:50]}'"
                                self.app.root.after(0, lambda msg=highlight_msg: self.app.log_message(msg))
                                break

                except Exception as e:
                    error_msg = f"🐛 调试处理器错误: {str(e)}"
                    self.app.root.after(0, lambda msg=error_msg: self.app.log_message(msg))

            self.debug_handler = debug_message_handler
            self.app.log_message(f"🐛 账号 {phone} 调试处理器已启动")

        except Exception as e:
            self.app.log_message(f"❌ 添加调试处理器失败: {str(e)}")

    def stop_raw_message_debug(self):
        """停止原始消息调试"""
        if not self.debug_active:
            self.app.log_message("🐛 调试模式未运行")
            return

        self.debug_active = False

        # 移除调试处理器
        for phone in self.app.selected_accounts:
            if phone in self.app.clients:
                try:
                    client = self.app.clients[phone]
                    if self.debug_handler:
                        client.remove_event_handler(self.debug_handler)
                except:
                    pass

        self.debug_handler = None
        self.app.log_message("🐛 原始消息调试已停止")

    def test_specific_group(self, group_name_or_id):
        """测试特定群组的消息接收"""
        if not self.app.selected_accounts:
            self.app.log_message("❌ 请先选择账号")
            return

        phone = self.app.selected_accounts[0]  # 使用第一个账号
        if phone not in self.app.clients:
            self.app.log_message("❌ 账号未连接")
            return

        client = self.app.clients[phone]
        threading.Thread(target=self._test_group_async, args=(phone, client, group_name_or_id)).start()

    def _test_group_async(self, phone, client, group_identifier):
        """异步测试特定群组"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def test_group():
                try:
                    # 查找群组
                    target_dialog = None
                    async for dialog in client.iter_dialogs():
                        if (dialog.title and group_identifier.lower() in dialog.title.lower()) or \
                                str(dialog.id) == str(group_identifier):
                            target_dialog = dialog
                            break

                    if not target_dialog:
                        self.app.root.after(0, lambda: self.app.log_message(f"❌ 未找到群组: {group_identifier}"))
                        return

                    # 获取最近的消息
                    self.app.root.after(0, lambda: self.app.log_message(f"🔍 测试群组: {target_dialog.title}"))

                    messages = await client.get_messages(target_dialog, limit=5)
                    for msg in messages:
                        if msg.text:
                            self.app.root.after(0,
                                                lambda text=msg.text: self.app.log_message(f"📝 历史消息: {text[:100]}"))

                except Exception as e:
                    error_msg = str(e)
                    self.app.root.after(0, lambda: self.app.log_message(f"❌ 测试群组失败: {error_msg}"))

            loop.run_until_complete(test_group())

        except Exception as e:
            self.app.root.after(0, lambda: self.app.log_message(f"❌ 测试过程失败: {str(e)}"))
        finally:
            try:
                loop.close()
            except:
                pass

    def list_recent_groups(self):
        """列出最近活跃的群组"""
        if not self.app.selected_accounts:
            self.app.log_message("❌ 请先选择账号")
            return

        phone = self.app.selected_accounts[0]
        if phone not in self.app.clients:
            self.app.log_message("❌ 账号未连接")
            return

        client = self.app.clients[phone]
        threading.Thread(target=self._list_groups_async, args=(phone, client)).start()



    def _list_groups_async(self, phone, client):
        """异步列出群组 - 使用全局事件循环"""
        try:
            loop = self.app.global_loop

            async def list_groups():
                try:
                    if not client.is_connected():
                        await client.connect()

                    self.app.root.after(0, lambda: self.app.log_message(f"📋 账号 {phone} 的群组列表:"))

                    count = 0
                    async for dialog in client.iter_dialogs(limit=50):
                        if dialog.is_group or dialog.is_channel:
                            count += 1
                            group_type = "频道" if dialog.is_channel else "群组"
                            last_msg_date = dialog.date.strftime("%Y-%m-%d %H:%M") if dialog.date else "未知"
                            info = f"📍 {count}. {dialog.title} ({group_type}) | ID: {dialog.id} | 最后活动: {last_msg_date}"
                            self.app.root.after(0, lambda msg=info: self.app.log_message(msg))

                    self.app.root.after(0, lambda: self.app.log_message(f"📋 共找到 {count} 个群组/频道"))

                except Exception as e:
                    error_msg = str(e)
                    self.app.root.after(0, lambda: self.app.log_message(f"❌ 列出群组失败: {error_msg}"))

            # 在全局事件循环中运行协程
            asyncio.run_coroutine_threadsafe(list_groups(), loop)

        except Exception as e:
            error_msg = str(e)
            self.app.root.after(0, lambda msg=error_msg: self.app.log_message(f"❌ 列出群组过程失败: {msg}"))