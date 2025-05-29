#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
账号管理模块 - 处理Telegram账号的登录、连接、管理等功能
"""

import asyncio
import threading
import os
import glob
import time
import tkinter as tk
import tkinter.simpledialog
from tkinter import messagebox
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
import python_socks


class AccountManager:
    def __init__(self, app):
        self.app = app

    def login_account(self):
        """登录Telegram账号"""
        api_id = self.app.api_id_var.get().strip()
        api_hash = self.app.api_hash_var.get().strip()

        if not api_id or not api_hash:
            messagebox.showerror("错误", "请先填写API ID和API Hash")
            return

        phone = tk.simpledialog.askstring("登录", "请输入手机号码(包含国家代码):")
        if not phone:
            return

        def safe_run_async_in_thread(async_func, *args, **kwargs):
            """在线程中安全运行异步函数"""

            def thread_target():
                # 为当前线程创建新的事件循环
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    # 运行异步函数
                    loop.run_until_complete(async_func(*args, **kwargs))
                except Exception as e:
                    print(f"异步函数执行失败: {e}")
                finally:
                    loop.close()

            thread = threading.Thread(target=thread_target)
            thread.daemon = True  # 设置为守护线程
            thread.start()
            return thread

    def _login_account_async(self, api_id, api_hash, phone):
        """异步登录账号 - 使用全局事件循环"""
        try:
            # 先检查并清理可能存在的session文件锁定
            session_file = f'session_{phone}.session'
            if os.path.exists(session_file):
                try:
                    # 尝试重命名文件来检查是否被锁定
                    temp_file = f'session_{phone}_temp.session'
                    os.rename(session_file, temp_file)
                    os.rename(temp_file, session_file)
                    self.app.root.after(0, lambda: self.app.log_message(f"✓ Session文件 {session_file} 可访问"))
                except OSError:
                    self.app.root.after(0, lambda: self.app.log_message(f"⚠️ Session文件被锁定，尝试删除..."))
                    try:
                        os.remove(session_file)
                        self.app.root.after(0, lambda: self.app.log_message(f"✓ 已删除锁定的session文件"))
                    except:
                        self.app.root.after(0, lambda: self.app.log_message(f"❌ 无法删除session文件，请手动删除"))
                        return

            # 获取代理配置
            proxy_config = self.app.network_proxy.get_proxy_config()

            if proxy_config:
                self.app.root.after(0, lambda: self.app.log_message(
                    f"使用代理: {proxy_config['proxy_type']}://{proxy_config['addr']}:{proxy_config['port']}"))

                if proxy_config['proxy_type'] == 'http':
                    proxy = (python_socks.ProxyType.HTTP, proxy_config['addr'], proxy_config['port'])
                elif proxy_config['proxy_type'] == 'socks5':
                    proxy = (python_socks.ProxyType.SOCKS5, proxy_config['addr'], proxy_config['port'])
                else:
                    proxy = None

                client = TelegramClient(
                    f'session_{phone}',
                    int(api_id),
                    api_hash,
                    proxy=proxy,
                    connection_retries=5,
                    timeout=60,
                    retry_delay=2,
                    # 添加以下参数
                    system_version="4.16.30-vxCUSTOM",
                    device_model="PC 64bit",
                    app_version="4.0.0",
                    lang_code="en",
                )
            else:
                self.app.root.after(0, lambda: self.app.log_message("不使用代理，直接连接"))

                client = TelegramClient(
                    f'session_{phone}',
                    int(api_id),
                    api_hash,
                    connection_retries=5,
                    timeout=60,
                    retry_delay=2,
                    # 添加以下参数
                    system_version="4.16.30-vxCUSTOM",
                    device_model="PC 64bit",
                    app_version="4.0.0",
                    lang_code="en",
                )

            # 定义登录协程
            async def login_coroutine():
                try:
                    self.app.root.after(0, lambda: self.app.log_message("正在连接到Telegram服务器..."))

                    # 连接时使用较短的超时
                    await client.connect()
                    self.app.root.after(0, lambda: self.app.log_message("✓ 连接成功！"))

                    if not await client.is_user_authorized():
                        await client.send_code_request(phone)
                        self.app.root.after(0, lambda: self.app.log_message("验证码已发送，请查看手机"))

                        # 验证码输入循环 - 最多3次机会
                        code_attempts = 0
                        max_code_attempts = 3

                        while code_attempts < max_code_attempts:
                            # 创建Future用于等待用户输入
                            code_future = asyncio.Future()

                            def get_code():
                                try:
                                    attempt_info = f" (第{code_attempts + 1}/{max_code_attempts}次)" if code_attempts > 0 else ""
                                    code = tk.simpledialog.askstring("验证",
                                                                     f"验证码已发送到 {phone}{attempt_info}\n请输入验证码:")
                                    if code is None:
                                        # 用户取消
                                        code_future.set_exception(Exception("用户取消输入验证码"))
                                    else:
                                        code_future.set_result(code)
                                except Exception as e:
                                    code_future.set_exception(e)

                            # 在主线程中弹出对话框
                            self.app.root.after(0, get_code)

                            try:
                                code = await code_future
                            except Exception as e:
                                raise e

                            try:
                                await client.sign_in(phone, code)
                                self.app.root.after(0, lambda: self.app.log_message("✓ 验证码验证成功"))
                                break  # 验证成功，跳出循环

                            except SessionPasswordNeededError:
                                # 需要二级密码，跳出验证码循环
                                self.app.root.after(0, lambda: self.app.log_message("✓ 验证码正确，需要输入二级密码"))
                                break

                            except Exception as code_error:
                                code_attempts += 1
                                error_msg = str(code_error)

                                if code_attempts >= max_code_attempts:
                                    raise Exception(f"验证码错误次数过多 ({max_code_attempts}次)，请稍后重试")
                                else:
                                    self.app.root.after(0, lambda: self.app.log_message(
                                        f"❌ 验证码错误 ({code_attempts}/{max_code_attempts})，请重新输入"))
                                    # 继续循环，要求重新输入验证码

                        # 处理二级密码
                        if not await client.is_user_authorized():
                            # 二级密码输入循环 - 最多3次机会
                            password_attempts = 0
                            max_password_attempts = 3

                            while password_attempts < max_password_attempts:
                                # 创建Future用于等待用户输入
                                password_future = asyncio.Future()

                                def get_password():
                                    try:
                                        attempt_info = f" (第{password_attempts + 1}/{max_password_attempts}次)" if password_attempts > 0 else ""
                                        password = tk.simpledialog.askstring(
                                            "二级密码",
                                            f"账号 {phone} 需要二级密码{attempt_info}\n请输入您的二级密码:",
                                            show='*'
                                        )
                                        if password is None:
                                            # 用户取消
                                            password_future.set_exception(Exception("用户取消输入二级密码"))
                                        else:
                                            password_future.set_result(password)
                                    except Exception as e:
                                        password_future.set_exception(e)

                                # 在主线程中弹出对话框
                                self.app.root.after(0, get_password)

                                try:
                                    password = await password_future
                                    await client.sign_in(password=password)
                                    self.app.root.after(0, lambda: self.app.log_message("✓ 二级密码验证成功"))
                                    break  # 验证成功，跳出循环
                                except Exception as pwd_error:
                                    password_attempts += 1
                                    error_msg = str(pwd_error)

                                    if password_attempts >= max_password_attempts:
                                        raise Exception(
                                            f"二级密码错误次数过多 ({max_password_attempts}次)，请稍后重试")
                                    else:
                                        self.app.root.after(0, lambda: self.app.log_message(
                                            f"❌ 二级密码错误 ({password_attempts}/{max_password_attempts})，请重新输入"))
                                        # 继续循环，要求重新输入密码

                    # 获取用户信息
                    me = await client.get_me()
                    username = me.username or me.first_name or me.last_name or "未知用户"

                    # 重要：确保客户端保持连接
                    self.app.clients[phone] = client

                    # 更新UI
                    self.app.root.after(0, lambda: self.app.update_account_list(phone, username))
                    self.app.root.after(0, lambda: self.app.log_message(f"账号 {username} ({phone}) 登录成功"))

                except asyncio.TimeoutError:
                    raise Exception("连接超时，请检查网络连接或代理设置")
                except Exception as e:
                    raise Exception(f"连接失败: {str(e)}")

            # 在全局事件循环中运行登录协程
            asyncio.run_coroutine_threadsafe(login_coroutine(), self.app.global_loop)

        except Exception as e:
            error_msg = str(e)
            self.app.root.after(0, lambda msg=error_msg: self.app.log_message(f"登录失败: {msg}"))
            self.app.root.after(0, lambda msg=error_msg: messagebox.showerror("登录失败", msg))

    def delete_account(self):
        """删除选中的账户 - 修复版本"""
        selected = self.app.account_listbox.curselection()
        if not selected:
            messagebox.showwarning("警告", "请先选择要删除的账号")
            return

        account_info = self.app.account_listbox.get(selected[0])
        phone = account_info.split('(')[1].split(')')[0]
        username = account_info.split(' (')[0]

        result = messagebox.askyesno("确认删除",
                                     f"确定要删除账号 {username} ({phone}) 吗？\n\n这将会：\n1. 断开账号连接\n2. 删除session文件\n3. 从列表中移除")

        if not result:
            return

        try:
            self.app.log_message(f"🗑️ 开始删除账号 {username} ({phone})")

            # 1. 停止监控（如果正在运行）
            if self.app.is_running:
                self.app.log_message("⏸️ 停止监控以删除账号")
                self.app.stop_monitoring()

            # 2. 断开连接
            if phone in self.app.clients:
                client = self.app.clients[phone]
                self.app.log_message(f"🔌 正在断开 {phone} 连接...")

                def disconnect_and_delete():
                    try:
                        # 创建新的事件循环来断开连接
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                        async def disconnect():
                            try:
                                if client.is_connected():
                                    await asyncio.wait_for(client.disconnect(), timeout=10)
                                    self.app.root.after(0, lambda: self.app.log_message(f"✓ {phone} 连接已断开"))
                            except Exception as e:
                                self.app.root.after(0, lambda: self.app.log_message(f"⚠️ 断开连接时出错: {str(e)}"))

                        loop.run_until_complete(disconnect())
                        loop.close()

                        # 断开连接后删除session文件
                        self.app.root.after(0, lambda: self._delete_session_files(phone, username))

                    except Exception as e:
                        self.app.root.after(0, lambda: self.app.log_message(f"❌ 断开连接失败: {str(e)}"))
                        # 即使断开失败，也尝试删除session文件
                        self.app.root.after(0, lambda: self._delete_session_files(phone, username))

                # 在新线程中断开连接
                threading.Thread(target=disconnect_and_delete, daemon=True).start()

                # 从客户端字典中移除
                del self.app.clients[phone]
            else:
                # 没有客户端连接，直接删除session文件
                self._delete_session_files(phone, username)

            # 3. 从界面列表中移除
            self.app.account_listbox.delete(selected[0])

            # 4. 从选中账号列表中移除
            if phone in self.app.selected_accounts:
                self.app.selected_accounts.remove(phone)

            self.app.log_message(f"✅ 账号 {username} ({phone}) 删除操作已启动")

        except Exception as e:
            error_msg = str(e)
            self.app.log_message(f"❌ 删除账号失败: {error_msg}")
            messagebox.showerror("删除失败", f"删除账号时出错:\n{error_msg}")

    def _delete_session_files(self, phone, username):
        """删除session相关文件"""
        try:
            import glob
            import time

            # 等待一下确保连接完全断开
            time.sleep(2)

            # 查找所有相关的session文件
            session_patterns = [
                f"session_{phone}.session",
                f"session_{phone}.session-journal",
                f"session_{phone}.session-shm",
                f"session_{phone}.session-wal"
            ]

            deleted_files = []
            failed_files = []

            for pattern in session_patterns:
                files = glob.glob(pattern)
                for file_path in files:
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            deleted_files.append(file_path)
                            self.app.log_message(f"🗑️ 已删除: {file_path}")
                    except Exception as e:
                        failed_files.append((file_path, str(e)))
                        self.app.log_message(f"❌ 删除 {file_path} 失败: {str(e)}")

            # 报告删除结果
            if deleted_files:
                self.app.log_message(f"✅ 成功删除 {len(deleted_files)} 个session文件")

            if failed_files:
                self.app.log_message(f"⚠️ {len(failed_files)} 个文件删除失败，可能被占用")
                # 尝试强制删除
                for file_path, error in failed_files:
                    try:
                        # 等待更长时间再试
                        time.sleep(1)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            self.app.log_message(f"✅ 延迟删除成功: {file_path}")
                    except:
                        self.app.log_message(f"❌ 请手动删除文件: {file_path}")

            # 最终消息
            messagebox.showinfo("删除完成", f"账号 {username} ({phone}) 删除完成\n\n删除了 {len(deleted_files)} 个文件")

        except Exception as e:
            self.app.log_message(f"❌ 删除session文件时出错: {str(e)}")
            messagebox.showerror("删除错误", f"删除session文件时出错:\n{str(e)}")

    def clear_all_accounts(self):
        """清理所有账户 - 修复版本"""
        if not self.app.clients:
            messagebox.showinfo("提示", "没有账号需要清理")
            return

        result = messagebox.askyesno("确认清理",
                                     f"确定要清理所有 {len(self.app.clients)} 个账号吗？\n\n这将会：\n1. 断开所有连接\n2. 删除所有session文件\n3. 清空账号列表")

        if not result:
            return

        try:
            self.app.log_message(f"🗑️ 开始清理所有 {len(self.app.clients)} 个账号")

            # 停止监控
            if self.app.is_running:
                self.app.log_message("⏸️ 停止监控以清理账号")
                self.app.stop_monitoring()

            # 获取所有账号列表
            all_phones = list(self.app.clients.keys())

            # 断开所有连接
            def disconnect_all():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    async def disconnect_clients():
                        for phone in all_phones:
                            if phone in self.app.clients:
                                try:
                                    client = self.app.clients[phone]
                                    if client.is_connected():
                                        await asyncio.wait_for(client.disconnect(), timeout=5)
                                        self.app.root.after(0,
                                                            lambda p=phone: self.app.log_message(f"🔌 {p} 连接已断开"))
                                except Exception as e:
                                    self.app.root.after(0, lambda p=phone, err=str(e):
                                    self.app.log_message(f"⚠️ 断开 {p} 时出错: {err}"))

                    loop.run_until_complete(disconnect_clients())
                    loop.close()

                    # 断开连接后删除所有session文件
                    self.app.root.after(0, lambda: self._delete_all_session_files(all_phones))

                except Exception as e:
                    self.app.root.after(0, lambda: self.app.log_message(f"❌ 断开连接过程失败: {str(e)}"))
                    # 即使断开失败，也尝试删除session文件
                    self.app.root.after(0, lambda: self._delete_all_session_files(all_phones))

            # 在新线程中断开所有连接
            threading.Thread(target=disconnect_all, daemon=True).start()

            # 清空所有列表
            self.app.clients.clear()
            self.app.selected_accounts.clear()
            self.app.account_listbox.delete(0, tk.END)

            self.app.log_message("✅ 账号清理操作已启动")

        except Exception as e:
            error_msg = str(e)
            self.app.log_message(f"❌ 清理账号失败: {error_msg}")
            messagebox.showerror("清理失败", f"清理账号时出错:\n{error_msg}")

    def _delete_all_session_files(self, phone_list):
        """删除所有session相关文件"""
        try:
            import glob
            import time

            # 等待确保所有连接都断开
            time.sleep(3)

            total_deleted = 0
            total_failed = 0

            # 删除每个账号的session文件
            for phone in phone_list:
                session_patterns = [
                    f"session_{phone}.session",
                    f"session_{phone}.session-journal",
                    f"session_{phone}.session-shm",
                    f"session_{phone}.session-wal"
                ]

                for pattern in session_patterns:
                    files = glob.glob(pattern)
                    for file_path in files:
                        try:
                            if os.path.exists(file_path):
                                os.remove(file_path)
                                total_deleted += 1
                                self.app.log_message(f"🗑️ 已删除: {file_path}")
                        except Exception as e:
                            total_failed += 1
                            self.app.log_message(f"❌ 删除 {file_path} 失败: {str(e)}")

            # 查找并删除其他可能的session文件
            try:
                other_sessions = glob.glob("session_*.session*")
                for file_path in other_sessions:
                    try:
                        os.remove(file_path)
                        total_deleted += 1
                        self.app.log_message(f"🗑️ 清理遗留文件: {file_path}")
                    except Exception as e:
                        total_failed += 1
                        self.app.log_message(f"❌ 清理 {file_path} 失败: {str(e)}")
            except:
                pass

            # 报告结果
            if total_failed > 0:
                self.app.log_message(f"⚠️ 部分文件清理失败，尝试强制清理...")
                # 再次尝试删除失败的文件
                time.sleep(2)
                remaining_files = glob.glob("session_*.session*")
                for file_path in remaining_files:
                    try:
                        os.remove(file_path)
                        total_deleted += 1
                        self.app.log_message(f"✅ 强制删除成功: {file_path}")
                    except:
                        self.app.log_message(f"❌ 请手动删除: {file_path}")

            self.app.log_message(f"🗑️ 清理完成: 删除了 {total_deleted} 个文件")

            if total_failed == 0:
                messagebox.showinfo("清理完成", f"所有账号已成功清理\n删除了 {total_deleted} 个session文件")
            else:
                messagebox.showwarning("部分清理完成",
                                       f"账号清理完成\n成功删除: {total_deleted} 个文件\n失败: {total_failed} 个文件\n\n部分文件可能需要手动删除")

        except Exception as e:
            self.app.log_message(f"❌ 清理session文件时出错: {str(e)}")
            messagebox.showerror("清理错误", f"清理session文件时出错:\n{str(e)}")

    def reconnect_account(self):
        """重新连接账号"""
        if not self.app.selected_accounts:
            messagebox.showwarning("提示", "请先选择账号")
            return

        for phone in self.app.selected_accounts:
            if phone not in self.app.clients:
                messagebox.showerror("错误", f"账号 {phone} 不存在")
                continue

            self.app.log_message(f"🔄 重新连接账号 {phone}...")
            threading.Thread(target=self._reconnect_async, args=(phone,), daemon=True).start()

    # 修改 _reconnect_async 方法
    def _reconnect_async(self, phone):
        """异步重新连接 - 修复事件循环问题"""
        try:
            client = self.app.clients[phone]

            # 使用客户端已有的循环
            loop = client.loop

            async def reconnect():
                try:
                    # 先断开
                    if client.is_connected():
                        await client.disconnect()
                        self.app.root.after(0, lambda: self.app.log_message(f"🔌 账号 {phone} 已断开"))

                    # 等待一下
                    await asyncio.sleep(1)

                    # 重连
                    await client.connect()

                    # 验证连接
                    me = await client.get_me()
                    username = me.username or me.first_name or "Unknown"

                    self.app.root.after(0, lambda: self.app.log_message(f"✅ 账号 {phone} ({username}) 重连成功"))

                    # 如果正在监控，提示重新开始监控
                    if self.app.is_running:
                        self.app.root.after(0, lambda: self.app.log_message("💡 请重新开始监控以应用连接"))

                except Exception as e:
                    error_msg = str(e)
                    self.app.root.after(0, lambda: self.app.log_message(f"❌ 重连失败: {error_msg}"))
                    self.app.root.after(0, lambda: messagebox.showerror("重连失败",
                                                                        f"账号 {phone} 重连失败:\n{error_msg}\n\n建议重新登录账号"))

            # 在客户端已有的循环中运行
            asyncio.run_coroutine_threadsafe(reconnect(), loop)

        except Exception as e:
            self.app.root.after(0, lambda: self.app.log_message(f"❌ 重连过程失败: {str(e)}"))

    def load_existing_sessions(self):
        """自动加载已有的session文件"""
        try:
            if not hasattr(self.app, 'log_text'):
                return

            session_files = glob.glob("session_*.session")

            for session_file in session_files:
                phone = session_file.replace("session_", "").replace(".session", "")

                if phone:
                    self.app.log_message(f"发现session文件: {phone}")
                    threading.Thread(target=self._load_session_async, args=(phone,)).start()

        except Exception as e:
            print(f"加载session文件失败: {e}")

    def _load_session_async(self, phone):
        """异步加载session"""
        try:
            api_id = self.app.config.get('api_id', '')
            api_hash = self.app.config.get('api_hash', '')

            if not api_id or not api_hash:
                self.app.root.after(0, lambda: self.app.log_message(f"跳过 {phone}: 未配置API"))
                return

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            proxy_config = self.app.network_proxy.get_proxy_config()
            proxy = None

            if proxy_config:
                if proxy_config['proxy_type'] == 'http':
                    proxy = (python_socks.ProxyType.HTTP, proxy_config['addr'], proxy_config['port'])
                elif proxy_config['proxy_type'] == 'socks5':
                    proxy = (python_socks.ProxyType.SOCKS5, proxy_config['addr'], proxy_config['port'])

            client = TelegramClient(f'session_{phone}', int(api_id), api_hash, proxy=proxy)

            async def load_session():
                await client.connect()

                if await client.is_user_authorized():
                    me = await client.get_me()
                    username = me.username or me.first_name or me.last_name or "未知用户"

                    self.app.clients[phone] = client
                    self.app.root.after(0, lambda: self.app.update_account_list(phone, username))
                    self.app.root.after(0, lambda: self.app.log_message(f"自动加载账号: {username} ({phone})"))
                else:
                    await client.disconnect()
                    self.app.root.after(0, lambda: self.app.log_message(f"Session {phone} 已过期，需要重新登录"))

            loop.run_until_complete(load_session())

        except Exception as e:
            self.app.root.after(0, lambda: self.app.log_message(f"加载session {phone} 失败: {str(e)}"))
        finally:
            try:
                loop.close()
            except:
                pass

    def close_all_connections(self):
        """关闭所有客户端连接"""
        try:
            self.app.log_message("正在关闭所有连接...")

            # 等待一下让监控完全停止
            time.sleep(1)

            # 关闭所有客户端连接
            for phone, client in list(self.app.clients.items()):
                try:
                    if hasattr(client, 'is_connected') and client.is_connected():
                        self.app.log_message(f"正在断开账号 {phone}...")

                        def disconnect_client():
                            try:
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)

                                async def disconnect():
                                    try:
                                        await asyncio.wait_for(client.disconnect(), timeout=5)
                                    except asyncio.TimeoutError:
                                        pass

                                loop.run_until_complete(disconnect())
                            except:
                                pass
                            finally:
                                try:
                                    loop.close()
                                except:
                                    pass

                        # 在新线程中断开连接，避免阻塞
                        thread = threading.Thread(target=disconnect_client)
                        thread.daemon = True
                        thread.start()

                except Exception as e:
                    print(f"断开 {phone} 时出错: {e}")

        except Exception as e:
            print(f"关闭连接时出错: {e}")