#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
消息监控模块 - 核心的消息处理功能
修复了消息接收和关键词匹配问题，增加了详细的调试日志
"""

import asyncio
import threading
import telegram
from datetime import datetime
from telethon import events
from tkinter import messagebox
from telethon import types



class MessageMonitor:
    def __init__(self, app):
        self.app = app
        self.monitoring_tasks = []
        self.event_handlers = {}  # 存储每个客户端的事件处理器

    # message_monitor.py

    def start_monitoring(self):
        """开始监控 - 使用全局事件循环"""
        try:
            self.app.log_message("🚀 启动消息监控系统...")

            # 初始化Bot
            bot_token = self.app.bot_token_var.get().strip()
            self.app.bot = telegram.Bot(token=bot_token)

            # 为每个选中的账号启动监控
            active_count = 0
            for phone in self.app.selected_accounts:
                if phone in self.app.clients:
                    client = self.app.clients[phone]

                    # 检查连接状态
                    if not client.is_connected():
                        self.app.log_message(f"🔄 账号 {phone} 未连接，尝试重新连接...")
                        self._reconnect_client(phone, client)

                        # 等待重连
                        import time
                        for i in range(5):
                            time.sleep(1)
                            if client.is_connected():
                                self.app.log_message(f"✅ 账号 {phone} 重连成功")
                                break
                        else:
                            self.app.log_message(f"❌ 账号 {phone} 重连超时")
                            continue

                    # 如果连接正常，启动消息监听
                    if client.is_connected():
                        # 在全局事件循环中启动监控
                        asyncio.run_coroutine_threadsafe(
                            self._start_client_monitoring(phone, client),
                            self.app.global_loop
                        )
                        active_count += 1
                        self.app.log_message(f"✅ 账号 {phone} 监控已启动")
                    else:
                        self.app.log_message(f"❌ 账号 {phone} 连接失败")

            if active_count == 0:
                raise Exception("没有可用的已连接账号，请重新连接")

            self.app.log_message(f"🎯 成功启动 {active_count} 个账号的监控")
            self.app.log_message(f"📤 转发目标: {self.app.forward_to_var.get()}")

            # 显示关键词设置
            keywords = [k.strip() for k in self.app.target_keywords_var.get().split(',') if k.strip()]
            if keywords:
                self.app.log_message(f"🔍 监控关键词: {keywords}")
            else:
                self.app.log_message("📝 监控所有消息（无关键词限制）")

            self.app.log_message("📱 监控运行中，等待消息...")

            # 启动心跳检测
            self._start_heartbeat_check()

        except Exception as e:
            error_msg = str(e)
            self.app.log_message(f"❌ 监控启动失败: {error_msg}")
            self.app.stop_monitoring()



    # 修改 _start_client_monitoring 方法
    def _start_client_monitoring(self, phone, client):
        """为单个客户端启动监控"""
        try:
            asyncio.set_event_loop(self.app.global_loop)
            # 移除旧的事件处理器
            if phone in self.event_handlers:
                try:
                    client.remove_event_handler(self.event_handlers[phone])
                except:
                    pass

            # 创建新的事件处理器 - 监听所有消息但只处理群组/频道
            @client.on(events.NewMessage())
            async def message_handler(event):
                try:
                    chat = await event.get_chat()
                    if isinstance(chat, (types.Chat, types.Channel)):
                        await self._handle_message(event, phone)
                except Exception as e:
                    self.app.root.after(0, lambda: self.app.log_message(f"处理消息错误: {str(e)}"))

            self.event_handlers[phone] = message_handler
            self.app.log_message(f"👂 账号 {phone} 开始监听消息...")



        except Exception as e:
            error_msg = str(e)
            self.app.root.after(0, lambda msg=error_msg: self.app.log_message(f"❌ 启动账号 {phone} 监控失败: {msg}"))

    def get_account_info(self, phone):
        """获取账号信息 - 同步方式"""
        if phone not in self.app.clients:
            return None

        try:
            client = self.app.clients[phone]
            if not client.is_connected():
                return f"{phone} (未连接)"

            # 使用简单的方式获取信息，避免事件循环冲突
            return f"{phone} (已连接)"

        except Exception as e:
            return f"{phone} (状态未知: {str(e)})"

    async def _handle_message(self, event, phone):
        try:
            message = event.message
            if not message:
                return

            # 获取聊天信息
            chat = await message.get_chat()
            chat_title = getattr(chat, 'title', 'Private Chat')
            chat_id = chat.id
            message_text = message.text or '[非文本消息]'

            # 调试日志 - 记录所有收到的消息
            log_msg = f"📨 [{phone}] 收到消息: {chat_title}(ID:{chat_id}) | {message_text[:100]}"
            self.app.root.after(0, lambda msg=log_msg: self.app.log_message(msg))

            # 1. 检查是否是群组/频道消息
            if not (chat.is_group or chat.is_channel):
                self.app.root.after(0, lambda: self.app.log_message(f"⚪ 跳过私聊/非群组消息"))
                return

            # 2. 检查白名单
            if self._is_in_whitelist(chat_title, getattr(chat, 'username', ''), chat_id):
                self.app.root.after(0, lambda: self.app.log_message(f"⚪ 白名单过滤: {chat_title}"))
                return

            # 3. 检查过滤条件
            if not self._should_forward_message(message):
                return

            # 4. 检查关键词
            if not self._contains_target_keywords(message_text):
                return

            # 5. 转发消息
            await self._forward_message(message, phone)

        except Exception as e:
            error_msg = str(e)  # 捕获错误信息
            self.app.root.after(0, lambda msg=error_msg: self.app.log_message(f"❗ [{phone}] 处理消息错误: {msg}"))

    def _is_in_whitelist(self, chat_title, chat_username, chat_id):
        """检查是否在白名单中（需要跳过的群组）"""
        whitelist_text = self.app.whitelist_groups_var.get().strip()
        if not whitelist_text:
            return False

        whitelist = [item.strip() for item in whitelist_text.split(',') if item.strip()]

        for item in whitelist:
            # 检查用户名匹配
            if item.startswith('@') and chat_username and item[1:] == chat_username:
                return True
            # 检查ID匹配
            elif (item.startswith('-') or item.isdigit()) and str(chat_id) == item:
                return True
            # 检查标题包含匹配
            elif item and chat_title and item.lower() in chat_title.lower():
                return True

        return False

    def _should_forward_message(self, message):
        """检查消息是否应该转发"""
        # 检查发送者用户名过滤
        if self.app.filter_username.get():
            if message.sender and hasattr(message.sender, 'username') and message.sender.username:
                return False

        # 检查链接过滤
        if self.app.filter_links.get():
            text = message.text or ''
            if 'http' in text or 't.me' in text or 'www.' in text:
                return False

        # 检查按钮过滤
        if self.app.filter_buttons.get():
            if message.reply_markup:
                return False

        # 检查媒体过滤
        if self.app.filter_media.get():
            if message.media or message.document or message.photo:
                return False

        # 检查转发消息过滤
        if self.app.filter_forwarded.get():
            if message.forward:
                return False

        # 检查过滤关键词
        filter_keywords_text = self.app.filter_keywords_var.get().strip()
        if filter_keywords_text and message.text:
            filter_keywords = [k.strip().lower() for k in filter_keywords_text.split(',') if k.strip()]
            text_lower = message.text.lower()

            for keyword in filter_keywords:
                if keyword in text_lower:
                    return False

        return True

    def _contains_target_keywords(self, text):
        """检查是否包含目标关键词 - 支持中英文"""
        if not text:
            return False

        keywords_text = self.app.target_keywords_var.get().strip()
        if not keywords_text:
            return True  # 如果没有设置关键词，则转发所有消息

        keywords = [k.strip() for k in keywords_text.split(',') if k.strip()]
        if not keywords:
            return True

        # 准备两个版本用于匹配
        text_original = text
        text_lower = text.lower()

        for keyword in keywords:
            keyword_original = keyword
            keyword_lower = keyword.lower()

            # 同时检查原文和小写版本
            if keyword_original in text_original or keyword_lower in text_lower:
                return True

        return False

    def _is_duplicate_message(self, message, chat_id):
        """检查是否为重复消息"""
        message_id = f"{chat_id}_{message.id}"
        if message_id in self.app.processed_messages:
            return True

        self.app.processed_messages.add(message_id)
        return False

    async def _forward_message(self, message, phone):
        """转发消息 - 根据是否有用户名选择转发方式"""
        try:
            forward_to = self.app.forward_to_var.get().strip()
            sender = message.sender

            # 获取发送者信息
            sender_info = "Unknown"
            has_username = False

            if sender:
                if hasattr(sender, 'username') and sender.username:
                    sender_info = f"@{sender.username}"
                    has_username = True
                elif hasattr(sender, 'first_name'):
                    sender_info = sender.first_name or "Unknown"

            # 根据需求：有用户名的用Bot发送，没有用户名的直接转发
            if has_username:
                # 通过Bot发送
                chat = await message.get_chat()
                chat_title = getattr(chat, 'title', 'Private')

                full_message = f"来源: {sender_info}\n群组: {chat_title}\n\n{message.text or '[媒体消息]'}"

                await self.app.bot.send_message(chat_id=forward_to, text=full_message)
                self.app.root.after(0, lambda: self.app.log_message(f"📤 通过Bot转发成功 (来自 {sender_info})"))
            else:
                # 直接转发
                client = self.app.clients[phone]
                await client.forward_messages(forward_to, message)
                self.app.root.after(0, lambda: self.app.log_message(f"📤 直接转发成功 (无用户名用户)"))

        except Exception as e:
            error_msg = str(e)
            self.app.root.after(0, lambda msg=error_msg: self.app.log_message(f"❌ 转发失败: {msg}"))

    # 修改 _reconnect_client 方法
    def _reconnect_client(self, phone, client):
        """重连客户端 - 使用客户端现有循环"""
        try:
            # 获取客户端的事件循环
            loop = client.loop

            async def reconnect():
                try:
                    # 先断开现有连接
                    if client.is_connected():
                        await client.disconnect()
                        self.app.root.after(0, lambda: self.app.log_message(f"🔌 {phone} 已断开旧连接"))

                    await asyncio.sleep(2)  # 等待断开完成

                    # 重新连接
                    await client.connect()

                    # 验证连接
                    me = await client.get_me()
                    username = me.username or me.first_name or "Unknown"
                    self.app.root.after(0, lambda: self.app.log_message(f"🔄 {phone} ({username}) 重连成功"))

                except Exception as e:
                    error_msg = str(e)
                    self.app.root.after(0, lambda: self.app.log_message(f"❌ {phone} 重连失败: {error_msg}"))

            # 在客户端已有的循环中运行
            asyncio.run_coroutine_threadsafe(reconnect(), loop)

        except Exception as e:
            error_msg = str(e)  # 捕获错误信息
            self.app.root.after(0, lambda msg=error_msg: self.app.log_message(f"❌ 重连过程失败: {msg}"))

        # 在新线程中运行重连
        threading.Thread(target=reconnect_in_thread, daemon=True).start()

    def _start_heartbeat_check(self):
        """启动心跳检测"""

        def heartbeat_check():
            import time
            while self.app.is_running:
                try:
                    connected_count = sum(1 for phone in self.app.selected_accounts
                                          if phone in self.app.clients and self.app.clients[phone].is_connected())

                    if connected_count < len(self.app.selected_accounts):
                        self.app.root.after(0, lambda: self.app.log_message(
                            f"⚠️ 连接检查: {connected_count}/{len(self.app.selected_accounts)} 账号在线"))

                    time.sleep(60)  # 每分钟检查一次
                except Exception as e:
                    self.app.root.after(0, lambda: self.app.log_message(f"❗ 心跳检查错误: {str(e)}"))
                    break

        threading.Thread(target=heartbeat_check, daemon=True).start()

    def stop_monitoring(self):
        """停止监控"""
        try:
            # 移除所有事件处理器
            for phone, handler in self.event_handlers.items():
                if phone in self.app.clients:
                    try:
                        client = self.app.clients[phone]
                        client.remove_event_handler(handler)
                        self.app.log_message(f"🛑 停止 {phone} 监控")
                    except Exception as e:
                        # 忽略移除处理器时的错误
                        pass

            self.event_handlers.clear()
            self.monitoring_tasks.clear()

        except Exception as e:
            self.app.log_message(f"❌ 停止监控时出错: {str(e)}")

    def send_test_message(self):
        """发送测试消息"""
        try:
            forward_to = self.app.forward_to_var.get().strip()
            if not forward_to:
                messagebox.showwarning("警告", "请先设置转发目标群")
                return

            test_message = "🧪 这是一条测试消息，用于验证Bot转发功能\n时间: " + str(datetime.now())

            def send_test():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    async def send():
                        bot_token = self.app.bot_token_var.get().strip()
                        bot = telegram.Bot(token=bot_token)
                        await bot.send_message(chat_id=forward_to, text=test_message)

                    loop.run_until_complete(send())
                    self.app.root.after(0, lambda: self.app.log_message("✅ 测试消息发送成功"))

                except Exception as e:
                    error_msg = str(e)
                    self.app.root.after(0, lambda: self.app.log_message(f"❌ 测试消息发送失败: {error_msg}"))
                finally:
                    try:
                        loop.close()
                    except:
                        pass

            threading.Thread(target=send_test, daemon=True).start()
            self.app.log_message("🧪 正在发送测试消息...")

        except Exception as e:
            self.app.log_message(f"❌ 发送测试消息错误: {str(e)}")

    def test_chinese_keywords(self):
        """测试中文关键词匹配"""
        from tkinter import messagebox

        self.app.log_message("=== 测试中文关键词匹配 ===")

        # 获取当前关键词设置
        keywords_setting = self.app.target_keywords_var.get().strip()
        keywords = [k.strip() for k in keywords_setting.split(',') if k.strip()]

        self.app.log_message(f"关键词设置: '{keywords_setting}'")
        self.app.log_message(f"解析结果: {keywords}")

        # 测试各种消息
        test_cases = [
            "日本",
            "今天去日本",
            "日本料理很好吃",
            "JAPAN",
            "japan",
            "I love Japan",
            "这是普通消息",
            "日本精聊群欢迎你",
            "Hello world",
            "测试消息"
        ]

        matched_count = 0
        for test_msg in test_cases:
            # 使用相同的匹配逻辑
            has_match = self._contains_target_keywords(test_msg)

            if has_match:
                matched_count += 1

            result = "✅匹配" if has_match else "❌无匹配"
            self.app.log_message(f"  '{test_msg}' -> {result}")

        self.app.log_message(f"=== 测试完成: {matched_count}/{len(test_cases)} 条消息匹配 ===")

        # 显示结果对话框
        messagebox.showinfo("关键词测试结果",
                            f"测试完成！\n\n关键词: {keywords}\n匹配: {matched_count}/{len(test_cases)} 条消息\n\n详细结果请查看日志")