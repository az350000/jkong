#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
群组管理模块 - 处理群组相关功能
"""

import asyncio
import threading
import json
import requests
import tkinter as tk
from tkinter import messagebox
from datetime import datetime


class GroupManager:
    def __init__(self, app):
        self.app = app

    def export_groups(self):
        """导出群组和频道"""
        selected = self.app.account_listbox.curselection()
        if not selected:
            messagebox.showwarning("警告", "请先选择要导出群组的账号")
            return

        # 获取选中的账号
        account_info = self.app.account_listbox.get(selected[0])
        phone = account_info.split('(')[1].split(')')[0]

        if phone not in self.app.clients:
            messagebox.showerror("错误", "账号未登录")
            return

        threading.Thread(target=self._export_groups_async, args=(phone,)).start()


    def _export_groups_async(self, phone):
        """异步导出群组 - 使用全局事件循环"""
        try:
            if phone not in self.app.clients:
                self.app.root.after(0, lambda: self.app.log_message("❌ 账号未登录"))
                return

            client = self.app.clients[phone]
            loop = self.app.global_loop

            async def export():
                try:
                    asyncio.set_event_loop(self.app.global_loop)
                    if not client.is_connected():
                        await client.connect()

                    groups = []
                    async for dialog in client.iter_dialogs():
                        if dialog.is_group or dialog.is_channel:
                            groups.append({
                                'title': dialog.title,
                                'username': getattr(dialog.entity, 'username', None),
                                'id': dialog.id,
                                'type': 'channel' if dialog.is_channel else 'group'
                            })

                    # 保存到文件
                    filename = f"groups_{phone}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(groups, f, ensure_ascii=False, indent=2)

                    self.app.root.after(0, lambda: self.app.log_message(
                        f"群组列表已导出到 {filename}，共 {len(groups)} 个群组/频道"))
                    self.app.root.after(0, lambda: messagebox.showinfo("成功",
                                                                       f"群组列表已导出到 {filename}\n共导出 {len(groups)} 个群组/频道"))

                except Exception as e:
                    error_msg = str(e)
                    self.app.root.after(0, lambda msg=error_msg: self.app.log_message(f"导出群组失败: {msg}"))

            # 在全局事件循环中运行导出协程
            asyncio.run_coroutine_threadsafe(export(), self.app.global_loop)

        except Exception as e:
            error_msg = str(e)
            self.app.root.after(0, lambda msg=error_msg: self.app.log_message(f"导出群组失败: {msg}"))


    def select_bot_groups(self):
        """选择Bot所在的群组"""
        bot_token = self.app.bot_token_var.get().strip()
        if not bot_token:
            messagebox.showerror("错误", "请先填写Bot Token")
            return

        self.app.log_message("正在获取Bot所在的群组...")
        threading.Thread(target=self._get_bot_groups_async).start()

    def _get_bot_groups_async(self):
        """异步获取Bot群组"""
        try:
            bot_token = self.app.bot_token_var.get().strip()

            # 使用简单的HTTP请求方式
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates?limit=100"

            # 获取代理配置
            proxy_config = self.app.network_proxy.get_proxy_config()
            proxies = None

            if proxy_config:
                if proxy_config['proxy_type'] == 'http':
                    proxies = {
                        'http': f"http://{proxy_config['addr']}:{proxy_config['port']}",
                        'https': f"http://{proxy_config['addr']}:{proxy_config['port']}"
                    }
                elif proxy_config['proxy_type'] == 'socks5':
                    proxies = {
                        'http': f"socks5://{proxy_config['addr']}:{proxy_config['port']}",
                        'https': f"socks5://{proxy_config['addr']}:{proxy_config['port']}"
                    }

            # 发送请求
            response = requests.get(url, proxies=proxies, timeout=30)
            data = response.json()

            if data.get('ok'):
                groups = {}
                for update in data.get('result', []):
                    if 'message' in update and 'chat' in update['message']:
                        chat = update['message']['chat']
                        if chat['type'] in ['group', 'supergroup']:
                            groups[chat['id']] = chat['title']

                # 在主线程中更新UI
                if groups:
                    self.app.root.after(0, lambda g=groups: self._show_group_dialog(g, "选择Bot群组"))
                    self.app.root.after(0, lambda: self.app.log_message(f"找到 {len(groups)} 个Bot群组"))
                else:
                    self.app.root.after(0, lambda: self.app.log_message("未找到Bot群组"))
                    self.app.root.after(0, lambda: messagebox.showinfo("提示",
                                                                   "未找到Bot群组\n请确保:\n1. Bot Token正确\n2. Bot已被添加到群组\n3. 群组中有消息记录"))
            else:
                error_msg = data.get('description', '未知错误')
                self.app.root.after(0, lambda msg=error_msg: self.app.log_message(f"Bot API错误: {msg}"))
                self.app.root.after(0, lambda msg=error_msg: messagebox.showerror("Bot错误",
                                                                              f"Bot Token可能无效:\n{msg}\n\n请检查:\n1. Token格式是否正确\n2. Bot是否被@BotFather禁用"))

        except requests.exceptions.ProxyError as e:
            error_msg = "代理连接失败"
            self.app.root.after(0, lambda: self.app.log_message(f"获取Bot群组失败: {error_msg}"))
            self.app.root.after(0, lambda: messagebox.showerror("代理错误",
                                                            f"{error_msg}\n请检查:\n1. 代理是否开启\n2. 代理配置是否正确\n3. 尝试关闭代理直连"))
        except requests.exceptions.Timeout as e:
            error_msg = "请求超时"
            self.app.root.after(0, lambda: self.app.log_message(f"获取Bot群组失败: {error_msg}"))
            self.app.root.after(0, lambda: messagebox.showerror("超时错误",
                                                            f"{error_msg}\n请检查网络连接"))
        except Exception as e:
            error_msg = str(e)
            self.app.root.after(0, lambda msg=error_msg: self.app.log_message(f"获取Bot群组失败: {msg}"))
            self.app.root.after(0, lambda msg=error_msg: messagebox.showerror("错误", f"获取Bot群组失败:\n{msg}"))

    def _show_group_dialog(self, groups, title):
        """显示群组选择对话框"""
        dialog = tk.Toplevel(self.app.root)
        dialog.title(title)
        dialog.geometry("500x400")
        dialog.transient(self.app.root)
        dialog.grab_set()

        frame = tk.Frame(dialog, padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="选择群组:").pack(anchor=tk.W)

        listbox = tk.Listbox(frame)
        listbox.pack(fill=tk.BOTH, expand=True, pady=10)

        group_list = list(groups.items())
        for group_id, group_name in group_list:
            listbox.insert(tk.END, f"{group_name} (ID: {group_id})")

        def on_select():
            selection = listbox.curselection()
            if selection:
                group_id = group_list[selection[0]][0]
                self.app.forward_to_var.set(str(group_id))
                self.app.log_message(f"已选择群组 ID: {group_id}")
                dialog.destroy()
            else:
                messagebox.showwarning("警告", "请选择一个群组")

        button_frame = tk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=10)

        tk.Button(button_frame, text="确定", command=on_select).pack(side=tk.RIGHT, padx=5)
        tk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.RIGHT)