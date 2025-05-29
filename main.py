#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram消息监控转发程序 - 主程序
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import asyncio
import threading
import json
import os
import sys
from datetime import datetime

# 导入功能模块
from network_proxy import NetworkProxy
from account_manager import AccountManager
from message_monitor import MessageMonitor
from config_manager import ConfigManager
from group_manager import GroupManager
from debug_tools import DebugTools


class TelegramMonitorApp:
    def __init__(self):
        # 如果是Windows系统，设置事件循环策略
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        self.root = tk.Tk()
        self.global_loop = None
        self.loop_thread = None
        self.root.title("Telegram消息监控转发程序 - v2.0")
        self.root.geometry("1200x900")

        # 数据存储
        self.clients = {}  # 存储已登录的客户端
        self.selected_accounts = []  # 选中的账号列表
        self.is_running = False
        self.processed_messages = set()  # 防重复转发
        self.bot = None
        self.heartbeat_task = None

        # 创建全局事件循环
        self.global_loop = asyncio.new_event_loop()

        # 初始化功能模块
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config()

        self.network_proxy = NetworkProxy(self)
        self.account_manager = AccountManager(self)
        self.message_monitor = MessageMonitor(self)
        self.group_manager = GroupManager(self)
        self.debug_tools = DebugTools(self)

        # 创建界面
        self.setup_ui()

        # 加载已有session
        self.account_manager.load_existing_sessions()

        # 在第一次空闲时启动全局事件循环
        self.root.after(100, self.start_global_loop)

    def setup_ui(self):
        """创建用户界面"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 配置行列权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        row = 0

        # API配置区域
        self.create_api_config_frame(main_frame, row)
        row += 1

        # 代理配置区域
        self.create_proxy_config_frame(main_frame, row)
        row += 1

        # 账号管理区域
        self.create_account_frame(main_frame, row)
        row += 1

        # 过滤选项区域
        self.create_filter_frame(main_frame, row)
        row += 1

        # 关键词配置区域
        self.create_keyword_frame(main_frame, row)
        row += 1

        # 目标配置区域
        self.create_target_frame(main_frame, row)
        row += 1

        # 控制按钮区域
        self.create_control_frame(main_frame, row)
        row += 1

        # 日志区域
        self.create_log_frame(main_frame, row)
        row += 1

        # 状态栏
        self.create_status_bar(main_frame, row)

    def create_api_config_frame(self, parent, row):
        """创建API配置区域"""
        api_frame = ttk.LabelFrame(parent, text="API配置", padding="5")
        api_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        api_frame.columnconfigure(1, weight=1)

        ttk.Label(api_frame, text="API ID:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.api_id_var = tk.StringVar(value=self.config.get('api_id', ''))
        ttk.Entry(api_frame, textvariable=self.api_id_var, width=20).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)

        ttk.Label(api_frame, text="API Hash:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.api_hash_var = tk.StringVar(value=self.config.get('api_hash', ''))
        ttk.Entry(api_frame, textvariable=self.api_hash_var, width=40).grid(row=0, column=3, sticky=(tk.W, tk.E),
                                                                            padx=5)

        ttk.Label(api_frame, text="Bot Token:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.bot_token_var = tk.StringVar(value=self.config.get('bot_token', ''))
        ttk.Entry(api_frame, textvariable=self.bot_token_var, width=60).grid(row=1, column=1, columnspan=3,
                                                                             sticky=(tk.W, tk.E), padx=5, pady=5)

    def create_proxy_config_frame(self, parent, row):
        """创建代理配置区域"""
        proxy_frame = ttk.LabelFrame(parent, text="代理配置", padding="5")
        proxy_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        proxy_frame.columnconfigure(1, weight=1)

        self.use_proxy = tk.BooleanVar(value=self.config.get('use_proxy', True))
        ttk.Checkbutton(proxy_frame, text="使用代理", variable=self.use_proxy).grid(row=0, column=0, sticky=tk.W,
                                                                                    padx=5)

        ttk.Label(proxy_frame, text="代理地址:").grid(row=0, column=1, sticky=tk.W, padx=5)
        self.proxy_host_var = tk.StringVar(value=self.config.get('proxy_host', '127.0.0.1'))
        ttk.Entry(proxy_frame, textvariable=self.proxy_host_var, width=15).grid(row=0, column=2, sticky=tk.W, padx=5)

        ttk.Label(proxy_frame, text="端口:").grid(row=0, column=3, sticky=tk.W, padx=5)
        self.proxy_port_var = tk.StringVar(value=self.config.get('proxy_port', '7890'))
        ttk.Entry(proxy_frame, textvariable=self.proxy_port_var, width=8).grid(row=0, column=4, sticky=tk.W, padx=5)

        ttk.Label(proxy_frame, text="类型:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.proxy_type_var = tk.StringVar(value=self.config.get('proxy_type', 'HTTP'))
        proxy_type_combo = ttk.Combobox(proxy_frame, textvariable=self.proxy_type_var, values=['HTTP', 'SOCKS5'],
                                        width=10, state='readonly')
        proxy_type_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)

        ttk.Button(proxy_frame, text="测试连接", command=self.network_proxy.test_proxy).grid(row=1, column=2, padx=5,
                                                                                             pady=5)
        ttk.Button(proxy_frame, text="诊断网络", command=self.network_proxy.diagnose_network).grid(row=1, column=3,
                                                                                                   padx=5, pady=5)
        ttk.Button(proxy_frame, text="扫描端口", command=self.network_proxy.scan_proxy_ports).grid(row=1, column=4,
                                                                                                   padx=5, pady=5)

    def create_account_frame(self, parent, row):
        """创建账号管理区域"""
        account_frame = ttk.LabelFrame(parent, text="账号管理", padding="5")
        account_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        account_frame.columnconfigure(1, weight=1)

        account_btn_frame1 = ttk.Frame(account_frame)
        account_btn_frame1.grid(row=0, column=0, columnspan=3, pady=5)

        ttk.Button(account_btn_frame1, text="登录新账号", command=self.account_manager.login_account).pack(side=tk.LEFT,
                                                                                                           padx=5)
        ttk.Button(account_btn_frame1, text="删除账号", command=self.account_manager.delete_account).pack(side=tk.LEFT,
                                                                                                          padx=5)
        ttk.Button(account_btn_frame1, text="清理所有", command=self.account_manager.clear_all_accounts).pack(
            side=tk.LEFT, padx=5)
        ttk.Button(account_btn_frame1, text="导出群组", command=self.group_manager.export_groups).pack(side=tk.LEFT,
                                                                                                       padx=5)

        self.account_listbox = tk.Listbox(account_frame, selectmode=tk.MULTIPLE, height=4)
        self.account_listbox.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), padx=5, pady=5)

    def create_filter_frame(self, parent, row):
        """创建过滤选项区域"""
        filter_frame = ttk.LabelFrame(parent, text="过滤选项", padding="5")
        filter_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        self.filter_username = tk.BooleanVar(value=self.config.get('filter_username', False))
        self.filter_links = tk.BooleanVar(value=self.config.get('filter_links', False))
        self.filter_buttons = tk.BooleanVar(value=self.config.get('filter_buttons', False))
        self.filter_media = tk.BooleanVar(value=self.config.get('filter_media', False))
        self.filter_forwarded = tk.BooleanVar(value=self.config.get('filter_forwarded', False))

        ttk.Checkbutton(filter_frame, text="过滤带用户名", variable=self.filter_username).grid(row=0, column=0,
                                                                                               sticky=tk.W, padx=5)
        ttk.Checkbutton(filter_frame, text="过滤带链接", variable=self.filter_links).grid(row=0, column=1, sticky=tk.W,
                                                                                          padx=5)
        ttk.Checkbutton(filter_frame, text="过滤带按钮", variable=self.filter_buttons).grid(row=0, column=2,
                                                                                            sticky=tk.W, padx=5)
        ttk.Checkbutton(filter_frame, text="过滤图片/文件", variable=self.filter_media).grid(row=1, column=0,
                                                                                             sticky=tk.W, padx=5)
        ttk.Checkbutton(filter_frame, text="过滤转发消息", variable=self.filter_forwarded).grid(row=1, column=1,
                                                                                                sticky=tk.W, padx=5)

    def create_keyword_frame(self, parent, row):
        """创建关键词配置区域"""
        keyword_frame = ttk.LabelFrame(parent, text="关键词配置", padding="5")
        keyword_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        keyword_frame.columnconfigure(1, weight=1)

        ttk.Label(keyword_frame, text="过滤关键词:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.filter_keywords_var = tk.StringVar(value=self.config.get('filter_keywords', ''))
        ttk.Entry(keyword_frame, textvariable=self.filter_keywords_var).grid(row=0, column=1, sticky=(tk.W, tk.E),
                                                                             padx=5)
        ttk.Label(keyword_frame, text="(多个用逗号分隔)").grid(row=0, column=2, sticky=tk.W, padx=5)

        ttk.Label(keyword_frame, text="获取关键词:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.target_keywords_var = tk.StringVar(value=self.config.get('target_keywords', ''))
        ttk.Entry(keyword_frame, textvariable=self.target_keywords_var).grid(row=1, column=1, sticky=(tk.W, tk.E),
                                                                             padx=5, pady=5)
        ttk.Label(keyword_frame, text="(多个用逗号分隔)").grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)

    def create_target_frame(self, parent, row):
        """创建目标配置区域"""
        target_frame = ttk.LabelFrame(parent, text="目标配置", padding="5")
        target_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        target_frame.columnconfigure(1, weight=1)

        ttk.Label(target_frame, text="转发到群:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.forward_to_var = tk.StringVar(value=self.config.get('forward_to', ''))
        ttk.Entry(target_frame, textvariable=self.forward_to_var).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)

        group_btn_frame = ttk.Frame(target_frame)
        group_btn_frame.grid(row=1, column=0, columnspan=2, pady=5)
        ttk.Button(group_btn_frame, text="选择Bot群组", command=self.group_manager.select_bot_groups, width=12).grid(
            row=0, column=0, padx=5)

        ttk.Label(target_frame, text="白名单群:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.whitelist_groups_var = tk.StringVar(value=self.config.get('whitelist_groups', ''))
        ttk.Entry(target_frame, textvariable=self.whitelist_groups_var).grid(row=2, column=1, sticky=(tk.W, tk.E),
                                                                             padx=5, pady=5)
        ttk.Label(target_frame, text="(跳过这些群，用逗号分隔)").grid(row=2, column=2, sticky=tk.W, padx=5, pady=5)

    def create_control_frame(self, parent, row):
        """创建控制按钮区域"""
        control_frame = ttk.Frame(parent)
        control_frame.grid(row=row, column=0, columnspan=2, pady=10)

        self.start_button = ttk.Button(control_frame, text="开始运行", command=self.start_monitoring)
        self.start_button.grid(row=0, column=0, padx=5)

        self.stop_button = ttk.Button(control_frame, text="停止运行", command=self.stop_monitoring, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=5)

        ttk.Button(control_frame, text="保存配置", command=self.save_config).grid(row=0, column=2, padx=5)
        ttk.Button(control_frame, text="加载配置", command=self.load_config).grid(row=0, column=3, padx=5)
        ttk.Button(control_frame, text="重新连接", command=self.account_manager.reconnect_account).grid(row=0, column=4,
                                                                                                        padx=5)
        ttk.Button(control_frame, text="测试消息", command=self.send_test_message).grid(row=0, column=5, padx=5)
        ttk.Button(control_frame, text="检查状态", command=self.check_account_status).grid(row=0, column=6, padx=5)

        # 第二行按钮
        ttk.Button(control_frame, text="开启心跳日志", command=self.start_heartbeat).grid(row=1, column=0, padx=5)
        ttk.Button(control_frame, text="停止心跳日志", command=self.stop_heartbeat).grid(row=1, column=1, padx=5)
        ttk.Button(control_frame, text="测试关键词", command=self.test_keywords).grid(row=1, column=2, padx=5)

        # 第三行调试按钮
        ttk.Button(control_frame, text="开启消息调试", command=self.debug_tools.start_raw_message_debug).grid(row=2,
                                                                                                              column=0,
                                                                                                              padx=5)
        ttk.Button(control_frame, text="停止消息调试", command=self.debug_tools.stop_raw_message_debug).grid(row=2,
                                                                                                             column=1,
                                                                                                             padx=5)
        ttk.Button(control_frame, text="列出群组", command=self.debug_tools.list_recent_groups).grid(row=2, column=2,
                                                                                                     padx=5)
        ttk.Button(control_frame, text="测试消息接收", command=self.test_message_reception).grid(row=2, column=3,
                                                                                                 padx=5)

    def create_log_frame(self, parent, row):
        """创建日志区域"""
        log_frame = ttk.LabelFrame(parent, text="运行日志", padding="5")
        log_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        parent.rowconfigure(row, weight=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=25, width=100)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    def create_status_bar(self, parent, row):
        """创建状态栏"""
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(parent, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

    def log_message(self, message):
        """添加日志消息"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)

    def start_heartbeat(self):
        """开启心跳日志"""
        if self.heartbeat_task is None:
            self.heartbeat_task = threading.Thread(target=self._heartbeat_loop, daemon=True)
            self.heartbeat_task.start()
            self.log_message("💓 心跳日志已开启")

    def setup_event_loop(self):
        """设置事件循环 - 新增方法"""
        if self.global_loop is None or self.global_loop.is_closed():
            self.global_loop = asyncio.new_event_loop()

    def stop_heartbeat(self):
        """停止心跳日志"""
        self.heartbeat_task = None
        self.log_message("💓 心跳日志已停止")

    def _heartbeat_loop(self):
        """心跳循环"""
        import time
        while self.heartbeat_task is not None:
            try:
                connected_count = sum(1 for client in self.clients.values() if client.is_connected())
                self.root.after(0, lambda: self.log_message(
                    f"💓 心跳: {connected_count}/{len(self.clients)} 账号在线, 监控状态: {'运行中' if self.is_running else '已停止'}"
                ))
                time.sleep(30)
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"💓 心跳错误: {str(e)}"))
                break

    def start_monitoring(self):
        """开始监控"""
        if self.is_running:
            return

        # 验证配置
        if not self.api_id_var.get() or not self.api_hash_var.get():
            messagebox.showerror("错误", "请填写API配置")
            return

        if not self.bot_token_var.get():
            messagebox.showerror("错误", "请填写Bot Token")
            return

        if not self.forward_to_var.get():
            messagebox.showerror("错误", "请填写转发目标群")
            return

        selected = self.account_listbox.curselection()
        if not selected:
            messagebox.showwarning("警告", "请选择要监控的账号")
            return

        self.is_running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_var.set("运行中...")

        # 获取选中的账号
        self.selected_accounts = []
        for i in selected:
            account_info = self.account_listbox.get(i)
            phone = account_info.split('(')[1].split(')')[0]
            self.selected_accounts.append(phone)

        self.log_message("开始监控消息...")

        # 启动消息监控
        self.message_monitor.start_monitoring()

    def stop_monitoring(self):
        """停止监控"""
        self.is_running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set("已停止")

        self.processed_messages.clear()
        self.message_monitor.stop_monitoring()
        self.log_message("🛑 监控已停止")

    def send_test_message(self):
        """发送测试消息"""
        self.message_monitor.send_test_message()

    def check_account_status(self):
        """检查账号状态"""
        self.log_message("=== 检查账号状态 ===")
        for phone in self.selected_accounts:
            if phone in self.clients:
                client = self.clients[phone]
                is_connected = client.is_connected()
                self.log_message(f"账号 {phone}: {'✅ 已连接' if is_connected else '❌ 未连接'}")
            else:
                self.log_message(f"账号 {phone}: ❌ 不存在")

    def test_keywords(self):
        """测试关键词匹配"""
        self.message_monitor.test_chinese_keywords()

    def test_message_reception(self):
        """测试消息接收能力"""
        if not self.is_running:
            messagebox.showwarning("提示", "请先开始监控")
            return

        self.log_message("=== 开始消息接收测试 ===")
        self.log_message("📱 当前监控状态:")

        for phone in self.selected_accounts:
            if phone in self.clients:
                client = self.clients[phone]
                status = "已连接" if client.is_connected() else "未连接"
                self.log_message(f"  📞 {phone}: {status}")
            else:
                self.log_message(f"  📞 {phone}: 不存在")

        self.log_message("🔍 请在任意群组发送消息测试...")
        self.log_message("💡 如果开启了消息调试，会显示原始消息")
        self.log_message("💡 如果包含关键词'日本'，会显示匹配信息")

        # 启动简单的连接监控
        def monitor_connection():
            import time
            start_time = time.time()
            while time.time() - start_time < 30:  # 监控30秒
                try:
                    connected = sum(1 for phone in self.selected_accounts
                                    if phone in self.clients and self.clients[phone].is_connected())
                    if connected == 0:
                        self.root.after(0, lambda: self.log_message("⚠️ 所有账号连接丢失!"))
                        break
                    time.sleep(5)
                except:
                    break

            self.root.after(0, lambda: self.log_message("=== 消息接收测试结束 ==="))

        threading.Thread(target=monitor_connection, daemon=True).start()

    def save_config(self):
        """保存配置"""
        config = {
            'api_id': self.api_id_var.get(),
            'api_hash': self.api_hash_var.get(),
            'bot_token': self.bot_token_var.get(),
            'use_proxy': self.use_proxy.get(),
            'proxy_host': self.proxy_host_var.get(),
            'proxy_port': self.proxy_port_var.get(),
            'proxy_type': self.proxy_type_var.get(),
            'filter_username': self.filter_username.get(),
            'filter_links': self.filter_links.get(),
            'filter_buttons': self.filter_buttons.get(),
            'filter_media': self.filter_media.get(),
            'filter_forwarded': self.filter_forwarded.get(),
            'filter_keywords': self.filter_keywords_var.get(),
            'target_keywords': self.target_keywords_var.get(),
            'forward_to': self.forward_to_var.get(),
            'whitelist_groups': self.whitelist_groups_var.get()
        }

        try:
            self.config_manager.save_config(config)
            self.log_message("配置已保存")
            messagebox.showinfo("成功", "配置已保存")
        except Exception as e:
            self.log_message(f"保存配置失败: {str(e)}")
            messagebox.showerror("错误", f"保存配置失败: {str(e)}")

    def load_config(self):
        """加载配置"""
        try:
            self.config = self.config_manager.load_config()

            # 更新界面
            self.api_id_var.set(self.config.get('api_id', ''))
            self.api_hash_var.set(self.config.get('api_hash', ''))
            self.bot_token_var.set(self.config.get('bot_token', ''))
            self.use_proxy.set(self.config.get('use_proxy', True))
            self.proxy_host_var.set(self.config.get('proxy_host', '127.0.0.1'))
            self.proxy_port_var.set(self.config.get('proxy_port', '7890'))
            self.proxy_type_var.set(self.config.get('proxy_type', 'HTTP'))
            self.filter_username.set(self.config.get('filter_username', False))
            self.filter_links.set(self.config.get('filter_links', False))
            self.filter_buttons.set(self.config.get('filter_buttons', False))
            self.filter_media.set(self.config.get('filter_media', False))
            self.filter_forwarded.set(self.config.get('filter_forwarded', False))
            self.filter_keywords_var.set(self.config.get('filter_keywords', ''))
            self.target_keywords_var.set(self.config.get('target_keywords', ''))
            self.forward_to_var.set(self.config.get('forward_to', ''))
            self.whitelist_groups_var.set(self.config.get('whitelist_groups', ''))

            self.log_message("配置已加载")
            messagebox.showinfo("成功", "配置已加载")

        except Exception as e:
            self.log_message(f"加载配置失败: {str(e)}")
            messagebox.showerror("错误", f"加载配置失败: {str(e)}")

    def update_account_list(self, phone, username):
        """更新账号列表"""
        self.account_listbox.insert(tk.END, f"{username} ({phone})")

    def run_global_loop(self):
        """运行全局事件循环"""
        asyncio.set_event_loop(self.global_loop)
        try:
            if not self.global_loop.is_running():
                self.log_message("启动全局事件循环...")
                self.global_loop.run_forever()
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: self.log_message(f"全局事件循环错误: {msg}"))

    def run(self):
        """运行程序"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 启动全局事件循环
        threading.Thread(target=self.start_global_loop, daemon=True).start()
        self.root.mainloop()

    def start_global_loop(self):
        """安全启动全局事件循环 - 替换原方法"""
        if self.loop_thread is not None and self.loop_thread.is_alive():
            print("事件循环线程已经在运行")
            return

        self.setup_event_loop()

        def run_loop():
            """在线程中运行事件循环"""
            asyncio.set_event_loop(self.global_loop)
            try:
                self.global_loop.run_forever()
            except Exception as e:
                print(f"事件循环出错: {e}")

        # 创建并启动事件循环线程
        self.loop_thread = threading.Thread(target=run_loop, daemon=True)
        self.loop_thread.start()
        print("事件循环已在新线程中启动")

    def stop_global_loop(self):
        """停止事件循环 - 新增方法"""
        if self.global_loop and not self.global_loop.is_closed():
            self.global_loop.call_soon_threadsafe(self.global_loop.stop)

    def run_async_task(self, coro):
        """在事件循环中运行异步任务 - 新增方法"""
        if self.global_loop and not self.global_loop.is_closed():
            future = asyncio.run_coroutine_threadsafe(coro, self.global_loop)
            return future
        else:
            print("事件循环未运行，无法执行异步任务")

    def on_closing(self):
        """程序关闭时的清理 - 新增方法"""
        self.stop_global_loop()
        self.root.destroy()

    # 在 TelegramMonitorApp 的 on_closing 方法中
    def on_closing(self):
        """关闭程序时的处理"""
        try:
            self.log_message("正在关闭程序...")

            if self.is_running:
                self.stop_monitoring()

            # 关闭所有客户端连接
            for phone, client in self.clients.items():
                if client.is_connected():
                    try:
                        # 在全局事件循环中断开连接
                        asyncio.run_coroutine_threadsafe(client.disconnect(), self.global_loop).result()
                    except:
                        pass

            # 停止全局事件循环
            if self.global_loop.is_running():
                self.log_message("停止全局事件循环...")
                self.global_loop.call_soon_threadsafe(self.global_loop.stop)

            # 等待事件循环线程结束
            if hasattr(self, 'global_thread') and self.global_thread.is_alive():
                self.log_message("等待事件循环线程结束...")
                self.global_thread.join(timeout=5.0)

            self.log_message("程序关闭完成")

        except Exception as e:
            error_msg = str(e)
            self.log_message(f"关闭程序时出错: {error_msg}")
        finally:
            try:
                self.root.quit()
                self.root.destroy()
            except:
                pass


if __name__ == "__main__":
    # 检查依赖
    try:
        import tkinter.simpledialog
        from telethon import TelegramClient, events
        from telethon.errors import SessionPasswordNeededError
        import telegram
        from telegram.ext import Application
        import requests
        import python_socks
    except ImportError as e:
        print(f"缺少依赖库: {e}")
        print("请安装以下库:")
        print("pip install telethon python-telegram-bot requests python-socks")
        exit(1)

    app = TelegramMonitorApp()
    app.root.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.run()