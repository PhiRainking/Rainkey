"""
Rainkey Steam Depot Downloader - GUI Version
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sys
import threading
import asyncio
import traceback
import time # For CheckLimit formatting
from pathlib import Path
import subprocess # Added for launching SteamTools
import platform # Added for OS-specific path handling
import webbrowser # Added for opening URLs

# Logging is handled by common.log, which now returns a NoOpLogger, so no GUI logging output.

# Add project root to sys.path to allow imports from common
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Attempt to import from common, handle if not found gracefully or ensure structure
try:
    from common import log, variable # log will now be a NoOpLogger
    import vdf # From requirements
    import httpx # From requirements
except ImportError as e:
    print(f"Error importing common modules or dependencies: {e}. Ensure they are installed and accessible.", file=sys.stderr)
    raise

# Global logger instance from common.log (will be a NoOpLogger)
LOG = log.log("RainkeyGUI") 

class App:
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("Rainkey Steam Depot Downloader GUI")
        self.root.geometry("750x400") # Adjusted height for new button

        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            current_theme = self.style.theme_use()
            print(f"Warning: 'clam' theme not available, using current theme: {current_theme}", file=sys.stderr)

        main_frame = ttk.Frame(self.root, padding="10 10 10 10")
        main_frame.pack(expand=True, fill=tk.BOTH)

        # Configuration Frame
        config_frame = ttk.LabelFrame(main_frame, text="配置", padding="10")
        config_frame.pack(fill=tk.X, pady=5)

        ttk.Label(config_frame, text="游戏 AppID:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        app_id_frame = ttk.Frame(config_frame) # Frame to hold AppID entry and search button
        app_id_frame.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.app_id_var = tk.StringVar()
        self.app_id_entry = ttk.Entry(app_id_frame, textvariable=self.app_id_var, width=40) # Adjusted width
        self.app_id_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)

        self.search_appid_button = ttk.Button(app_id_frame, text="搜索AppID", command=self.open_steamui_website)
        self.search_appid_button.pack(side=tk.LEFT, padx=(5,0))

        ttk.Label(config_frame, text="解锁工具:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        tool_frame = ttk.Frame(config_frame)
        tool_frame.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.tool_choice_var = tk.IntVar(value=1)
        self.steamtools_radio = ttk.Radiobutton(tool_frame, text="SteamTools (脚本解锁)", variable=self.tool_choice_var, value=1, command=self.toggle_version_lock)
        self.steamtools_radio.pack(side=tk.LEFT, padx=(0,10))
        self.greenluma_radio = ttk.Radiobutton(tool_frame, text="GreenLuma (脚本解锁)", variable=self.tool_choice_var, value=2, command=self.toggle_version_lock)
        self.greenluma_radio.pack(side=tk.LEFT)

        self.version_lock_var = tk.BooleanVar(value=False)
        self.version_lock_check = ttk.Checkbutton(config_frame, text="锁定版本 (SteamTools 脚本解锁推荐)", variable=self.version_lock_var)
        self.version_lock_check.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        self.toggle_version_lock()

        ttk.Label(config_frame, text="Steam 路径:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        steam_path_frame = ttk.Frame(config_frame)
        steam_path_frame.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
        self.steam_path_var = tk.StringVar(value=str(variable.STEAM_PATH))
        self.steam_path_entry = ttk.Entry(steam_path_frame, textvariable=self.steam_path_var, width=40)
        self.steam_path_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.browse_button = ttk.Button(steam_path_frame, text="浏览...", command=self.browse_steam_path)
        self.browse_button.pack(side=tk.LEFT, padx=(5,0))
        
        config_frame.columnconfigure(1, weight=1)

        # Action Buttons Frame
        action_buttons_frame = ttk.Frame(main_frame)
        action_buttons_frame.pack(pady=10)

        self.start_button = ttk.Button(action_buttons_frame, text="开始解锁 (脚本)", command=self.start_processing_thread, style="Accent.TButton")
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.launch_steamtools_button = ttk.Button(action_buttons_frame, text="启动 SteamTools (独立程序)", command=self.launch_steamtools_exe)
        self.launch_steamtools_button.pack(side=tk.LEFT)
        
        self.style.configure("Accent.TButton", font=("Helvetica", 10, "bold"))

        # Status Label
        self.status_var = tk.StringVar()
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var, font=("Helvetica", 10))
        self.status_label.pack(pady=5, fill=tk.X)
        self.status_var.set("请配置并选择操作。")

    def open_steamui_website(self):
        try:
            webbrowser.open_new_tab("https://steamui.com/")
            self.status_var.set("已尝试在浏览器中打开 steamui.com")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开浏览器: {e}")
            self.status_var.set(f"无法打开浏览器: {e}")

    def get_steamtools_exe_path(self):
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, "steamtools_bundle", "SteamTools.exe")

    def launch_steamtools_exe(self):
        steamtools_exe_path = self.get_steamtools_exe_path()
        if platform.system() != "Windows":
            messagebox.showerror("错误", "SteamTools.exe 只能在 Windows 系统上运行。")
            return

        if not os.path.exists(steamtools_exe_path):
            messagebox.showerror("错误", f"未找到 SteamTools.exe，请确保它位于以下路径：\n{steamtools_exe_path}\n如果程序已打包，请检查打包配置是否正确包含了 steamtools_bundle 文件夹。")
            self.status_var.set(f"错误: 未找到 {steamtools_exe_path}")
            return

        try:
            self.status_var.set("正在启动 SteamTools.exe...")
            steamtools_dir = os.path.dirname(steamtools_exe_path)
            subprocess.Popen([steamtools_exe_path], cwd=steamtools_dir)
            self.status_var.set("SteamTools.exe 已启动 (如果未弹出，请检查任务管理器或系统日志)。")
        except Exception as e:
            messagebox.showerror("启动失败", f"启动 SteamTools.exe 失败: {e}")
            self.status_var.set(f"启动 SteamTools.exe 失败: {e}")

    def browse_steam_path(self):
        directory = filedialog.askdirectory(initialdir=self.steam_path_var.get(), title="选择 Steam 安装目录")
        if directory:
            self.steam_path_var.set(directory)

    def toggle_version_lock(self):
        if self.tool_choice_var.get() == 1:
            self.version_lock_check.config(state=tk.NORMAL)
        else:
            self.version_lock_check.config(state=tk.DISABLED)
            self.version_lock_var.set(False)

    def start_processing_thread(self):
        app_id = self.app_id_var.get().strip()
        if not app_id:
            messagebox.showerror("输入错误", "请输入有效的游戏 App ID。")
            return

        tool_choice = self.tool_choice_var.get()
        version_lock = self.version_lock_var.get() if tool_choice == 1 else False
        
        current_steam_path_str = self.steam_path_var.get().strip()
        if not current_steam_path_str:
            messagebox.showerror("输入错误", "Steam 路径不能为空。")
            return
        
        new_steam_path = Path(current_steam_path_str)
        if new_steam_path != variable.STEAM_PATH:
            variable.STEAM_PATH = new_steam_path
        
        self.status_var.set("正在处理脚本解锁，请稍候... (预计需要1-5分钟)")
        self.start_button.config(state=tk.DISABLED)
        self.launch_steamtools_button.config(state=tk.DISABLED)

        thread = threading.Thread(target=self.run_async_tasks_wrapper, args=(app_id, tool_choice, version_lock, new_steam_path))
        thread.daemon = True
        thread.start()

    def run_async_tasks_wrapper(self, app_id, tool_choice, version_lock, steam_path_obj):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.MainLogic_adapted(app_id, tool_choice, version_lock, steam_path_obj))
        except Exception as e_async_wrapper: 
            self.root.after(0, lambda err=e_async_wrapper: messagebox.showerror("处理失败", f"发生严重错误: {err}. 请检查输入或网络。"))
            self.root.after(0, lambda: self.status_var.set(f"脚本解锁处理失败: {e_async_wrapper}"))
        finally:
            loop.close()

    def processing_finished(self, success_message="处理完成！"):
        self.start_button.config(state=tk.NORMAL)
        self.launch_steamtools_button.config(state=tk.NORMAL)
        self.status_var.set(success_message)

    def _init_banner_gui(self):
        pass

    async def _CheckCN_adapted(self, client):
        try:
            req = await client.get("https://mips.kugou.com/check/iscn?&format=json", timeout=10)
            body = req.json()
            scn = bool(body["flag"])
            variable.IS_CN = scn
            return variable.IS_CN
        except:
            variable.IS_CN = True 
            return False

    def _StackError_adapted(self, exception: Exception) -> str:
        return "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))

    async def _CheckLimit_adapted(self, headers, client):
        url = "https://api.github.com/rate_limit"
        try:
            r = await client.get(url, headers=headers)
            if r.status_code == 200:
                rate = r.json().get("rate", {})
                if rate.get("remaining", 0) == 0:
                    pass 
        except:
            pass 

    async def _GetLatestRepoInfo_adapted(self, repos: list, app_id: str, headers, client) -> tuple[str | None, str | None]:
        latest_date, selected_repo = None, None
        for repo_path in repos:
            url = f"https://api.github.com/repos/{repo_path}/branches/{app_id}"
            try:
                r = await client.get(url, headers=headers)
                if r.status_code == 200:
                    data = r.json()
                    date = data["commit"]["commit"]["author"]["date"]
                    if (latest_date is None) or (date > latest_date):
                        latest_date, selected_repo = str(date), str(repo_path)
            except:
                pass 
        return selected_repo, latest_date

    async def _FetchFiles_adapted(self, sha: str, file_path: str, repo: str, client):
        fetch_headers = {**variable.HEADER_USER_AGENT, **variable.HEADER}
        base_urls = variable.CHINA_CDN_URLS if variable.IS_CN else variable.GITHUB_RAW_URLS
        urls_to_try = [f"{base.rstrip("/")}/{repo}@{sha}/{file_path.lstrip("/")}" for base in base_urls]
        if not variable.IS_CN: 
            urls_to_try.insert(0, f"https://raw.githubusercontent.com/{repo}/{sha}/{file_path}")
        
        for attempt in range(3):
            for url in urls_to_try:
                try:
                    r = await client.get(url, headers=fetch_headers, timeout=30)
                    if r.status_code == 200:
                        return r.content
                except:
                    pass
        raise Exception(f"无法下载: {file_path}")

    async def _HandleDepotFiles_adapted(self, repos: list, app_id: str, steam_path: Path, client) -> tuple[list, dict]:
        collected_keys, depot_manifest_map = [], {}
        try:
            selected_repo, latest_date = await self._GetLatestRepoInfo_adapted(repos, app_id, variable.HEADER, client)
            if not selected_repo: return collected_keys, depot_manifest_map

            branch_data_url = f"https://api.github.com/repos/{selected_repo}/branches/{app_id}"
            branch_res = await client.get(branch_data_url, headers=variable.HEADER)
            branch_res.raise_for_status()
            branch_data = branch_res.json()
            
            tree_data_url = branch_data["commit"]["commit"]["tree"]["url"]
            tree_res = await client.get(tree_data_url, headers=variable.HEADER)
            tree_res.raise_for_status()
            tree_data = tree_res.json()
            
            depot_cache_path = steam_path / "depotcache"
            depot_cache_path.mkdir(parents=True, exist_ok=True)

            commit_sha = branch_data["commit"]["sha"]
            for item in tree_data.get("tree", []):
                file_path_str = item.get("path", "")
                if file_path_str.endswith(".manifest"):
                    content = await self._FetchFiles_adapted(commit_sha, file_path_str, selected_repo, client)
                    save_path = depot_cache_path / file_path_str
                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    save_path.write_bytes(content)
                    name_stem = Path(file_path_str).stem
                    if "_" in name_stem:
                        d_id, m_id = name_stem.split("_", 1)
                        if d_id.isdigit() and m_id.isdigit():
                            depot_manifest_map.setdefault(d_id, []).append(m_id)
                elif "key.vdf" in file_path_str.lower():
                    content = await self._FetchFiles_adapted(commit_sha, file_path_str, selected_repo, client)
                    collected_keys.extend(self._ParseKey_adapted(content))
            
            for d_id in depot_manifest_map: depot_manifest_map[d_id].sort(key=int, reverse=True)
        except Exception as e_handle_depot:
            raise Exception(f"文件处理失败: {e_handle_depot}") 
        return collected_keys, depot_manifest_map

    def _ParseKey_adapted(self, content: bytes) -> list:
        try:
            decoded_content = content.decode("utf-8", errors="replace")
            data = vdf.loads(decoded_content)
            if "depots" not in data:
                return []
            keys = [(k, v["DecryptionKey"]) for k, v in data["depots"].items() if isinstance(v, dict) and "DecryptionKey" in v]
            return keys
        except:
            return []

    def _SetupTools_adapted(self, depot_data: list, app_id: str, depot_map: dict, version_lock: bool, steam_path: Path) -> bool:
        try:
            st_plugin_path = steam_path / "config" / "stplug-in"
            st_plugin_path.mkdir(parents=True, exist_ok=True)
            lua_parts = [f'addappid({app_id}, 1, "None")']
            for d_id, d_key in depot_data:
                lua_parts.append(f'addappid({d_id}, 1, "{d_key}")')
                if version_lock and d_id in depot_map and depot_map[d_id]:
                    manifest_to_lock = depot_map[d_id][0]
                    lua_parts.append(f'setManifestid({d_id},"{manifest_to_lock}")')
            lua_file = st_plugin_path / f"{app_id}.lua"
            lua_file.write_text("\n".join(lua_parts) + "\n", encoding="utf-8")
            return True
        except:
            return False

    def _SetupGreenLuma_adapted(self, depot_data: list, steam_path: Path) -> bool:
        try:
            applist_dir = steam_path / "AppList"
            applist_dir.mkdir(parents=True, exist_ok=True)
            for f_txt in applist_dir.glob("*.txt"): f_txt.unlink()
            for i, (d_id, _) in enumerate(depot_data, 1):
                (applist_dir / f"{i}.txt").write_text(str(d_id), encoding="utf-8")
            
            cfg_path = steam_path / "config" / "config.vdf"
            cfg_data = {} 
            if cfg_path.exists():
                try:
                    with cfg_path.open("r", encoding="utf-8") as f_cfg:
                        cfg_data = vdf.load(f_cfg)
                except:
                    cfg_data = {} 
            
            cfg_data.setdefault("depots", {}) 
            for d_id, d_key in depot_data:
                 cfg_data["depots"][str(d_id)] = {"DecryptionKey": str(d_key)}
            
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            with cfg_path.open("w", encoding="utf-8") as f_cfg_write:
                vdf.dump(cfg_data, f_cfg_write, pretty=True)
            return True
        except:
            return False

    def _SetupUnlock_adapted(self, depot_data: list, app_id: str, tool_choice: int, depot_map: dict, version_lock: bool, steam_path: Path) -> bool:
        if tool_choice == 1: 
            return self._SetupTools_adapted(depot_data, app_id, depot_map, version_lock, steam_path)
        elif tool_choice == 2: 
            return self._SetupGreenLuma_adapted(depot_data, steam_path)
        return False

    async def MainLogic_adapted(self, app_id_str: str, tool_choice_int: int, version_lock_bool: bool, steam_path_obj: Path):
        self._init_banner_gui()
        app_ids = list(filter(str.isdecimal, app_id_str.strip().split("-")))
        if not app_ids:
            self.root.after(0, lambda: messagebox.showerror("错误", f"提供的 App ID \'{app_id_str}\' 无效。"))
            self.root.after(0, lambda: self.processing_finished(f"App ID 无效: {app_id_str}"))
            return
        actual_app_id = app_ids[0]

        async with httpx.AsyncClient(headers=variable.HEADER_USER_AGENT, http2=True, follow_redirects=True, timeout=30) as client:
            try:
                await self._CheckCN_adapted(client)
                await self._CheckLimit_adapted(variable.HEADER, client) 
                depot_keys, depot_manifests = await self._HandleDepotFiles_adapted(variable.REPO_LIST, actual_app_id, steam_path_obj, client)

                if not depot_keys:
                    self.root.after(0, lambda: messagebox.showerror("错误", f"未能找到 AppID {actual_app_id} 的清单或密钥数据."))
                    self.root.after(0, lambda: self.processing_finished(f"未能找到 AppID {actual_app_id} 的数据"))
                    return

                success = self._SetupUnlock_adapted(depot_keys, actual_app_id, tool_choice_int, depot_manifests, version_lock_bool, steam_path_obj)
                
                if success:
                    self.root.after(0, lambda: messagebox.showinfo("成功", "游戏脚本解锁配置成功！重启Steam后生效."))
                    self.root.after(0, lambda: self.processing_finished("游戏脚本解锁配置成功！"))
                else:
                    self.root.after(0, lambda: messagebox.showerror("失败", "脚本解锁配置失败. 请检查输入或Steam路径权限。"))
                    self.root.after(0, lambda: self.processing_finished("脚本解锁配置失败。"))
            except Exception as e_main_logic:
                self.root.after(0, lambda err=e_main_logic: messagebox.showerror("运行时错误", f"发生严重错误: {err}. 请检查输入或网络。"))
                self.root.after(0, lambda err=e_main_logic: self.processing_finished(f"运行时错误: {err}"))

if __name__ == "__main__":
    if not hasattr(variable, 'CHINA_CDN_URLS'): variable.CHINA_CDN_URLS = ["https://cdn.jsdmirror.com/gh", "https://raw.gitmirror.com", "https://raw.dgithub.xyz", "https://gh.akass.cn"]
    if not hasattr(variable, 'GITHUB_RAW_URLS'): variable.GITHUB_RAW_URLS = ["https://raw.githubusercontent.com"]
    if not hasattr(variable, 'HEADER_USER_AGENT'): variable.HEADER_USER_AGENT = {"User-Agent": "RainkeySteamDownloaderGUI/1.0"} 
    
    root = tk.Tk()
    gui_app = App(root)
    try:
        root.mainloop()
    finally:
        pass

