import os
import sys
import shutil
import threading
import ctypes
import platform
import tkinter as tk
from tkinter import messagebox
import winreg
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from send2trash import send2trash

# --- Definícia ikony ---
def set_window_icon(root):
    """Nastaví ikonu okna ak existuje icon.ico"""
    try:
        if os.path.exists("icon.ico"):
            root.iconbitmap("icon.ico")
    except Exception:
        pass

# --- DWM (Windows 11) helpers: rounded corners + dark title bar ---
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_DEFAULT = 0
DWMWCP_DONOTROUND = 1
DWMWCP_ROUND = 2
DWMWCP_ROUNDSMALL = 3

def set_win11_window_attributes(hwnd, dark_mode=True, rounded=True):
    try:
        use_dark = ctypes.c_int(1 if dark_mode else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(use_dark),
            ctypes.sizeof(use_dark)
        )
    except Exception:
        pass
    try:
        corner_pref = ctypes.c_int(DWMWCP_ROUND if rounded else DWMWCP_DEFAULT)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(corner_pref),
            ctypes.sizeof(corner_pref)
        )
    except Exception:
        pass

def get_hwnd(root):
    # Return window handle; works for tb.Window (tk.Tk)
    try:
        wid = root.winfo_id()
        parent = ctypes.windll.user32.GetParent(wid)
        return parent or wid
    except Exception:
        return root.winfo_id()

# --- Elevácia na správcu (Windows only) ---
def ensure_admin():
    try:
        if os.name == "nt" and not ctypes.windll.shell32.IsUserAnAdmin():
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
            sys.exit()
    except Exception:
        # ak detekcia zlyhá, pokračujeme bez elevácie
        pass

ensure_admin()

# --- Automatická detekcia systému a preferencií ---
def detect_system_mode():
    """
    Vracia tuple (is_windows, prefer_light_theme, is_win11_or_newer, supports_dwm).
    prefer_light_theme: True = svetlá, False = tmavá
    is_win11_or_newer: True ak build >= 22000
    supports_dwm: True ak DWM atribúty sú dostupné
    """
    is_windows = (os.name == "nt")
    prefer_light = True
    is_win11 = False
    supports_dwm = False

    if is_windows:
        # zisti verziu Windows (build)
        try:
            ver = sys.getwindowsversion()
            # ver.build je build number
            is_win11 = getattr(ver, "build", 0) >= 22000
        except Exception:
            try:
                # fallback cez platform
                release = platform.release()
                # Windows 11 má release "10" ale build >= 22000; ak nevieme, necháme False
                is_win11 = False
            except Exception:
                is_win11 = False

        # zisti preferenciu témy z registry (AppsUseLightTheme)
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                # 1 = light, 0 = dark
                val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                prefer_light = bool(val)
        except Exception:
            # ak nie je kľúč, necháme predvolené True (svetlá)
            prefer_light = True

        # test DWM dostupnosti
        try:
            ctypes.windll.dwmapi.DwmSetWindowAttribute
            supports_dwm = True
        except Exception:
            supports_dwm = False

    else:
        # nie Windows: použij predvolené (svetlá)
        prefer_light = True
        is_win11 = False
        supports_dwm = False

    return is_windows, prefer_light, is_win11, supports_dwm

# --- Pomocné funkcie pre zber položiek a výpočty ---
def collect_items_for_path(path):
    if os.path.isfile(path):
        return [path]
    items = []
    for root, dirs, files in os.walk(path, topdown=False):
        for f in files:
            items.append(os.path.join(root, f))
        for d in dirs:
            items.append(os.path.join(root, d))
    if os.path.isdir(path):
        items.append(path)
    return items

def safe_getsize(path):
    try:
        if os.path.isfile(path):
            return os.path.getsize(path)
        return 0
    except Exception:
        return 0

def vycisti_ciel(path, nazov, progress=None, safe=True):
    if not path or not os.path.exists(path):
        return {"nazov": nazov, "uvolnene_mb": 0.0, "zmazane": 0, "nezmazane": 0, "poznamka": "neexistuje"}

    items = collect_items_for_path(path)
    total = len(items)
    done = 0
    uvolnene_bytes = 0
    zmazane = 0
    nezmazane = 0

    for item in items:
        uvolnene_bytes += safe_getsize(item)
        try:
            if safe:
                send2trash(item)
            else:
                if os.path.isfile(item):
                    os.remove(item)
                else:
                    shutil.rmtree(item, ignore_errors=False)
            zmazane += 1
        except Exception:
            nezmazane += 1

        done += 1
        if progress and total > 0:
            progress["value"] = int(done / total * 100)
            progress.update()

    return {
        "nazov": nazov,
        "uvolnene_mb": round(uvolnene_bytes / 1024 / 1024, 2),
        "zmazane": zmazane,
        "nezmazane": nezmazane,
        "poznamka": ""
    }

# --- Definícia cieľov (bez Windows Update cache) ---
def get_targets():
    user_home = os.path.expanduser("~")
    env_temp = os.environ.get("TEMP")

    system_targets = {
        "používateľského TEMP": (env_temp, False),
        "Windows TEMP": (r"C:\Windows\Temp", False),
        "miniatúr (Explorer)": (os.path.join(user_home, r"AppData\Local\Microsoft\Windows\Explorer"), True),
        "Prefetch": (r"C:\Windows\Prefetch", True),
        "systémových logov": (r"C:\Windows\Logs", True)
    }

    browser_targets = {
        "Edge Cache": (os.path.join(user_home, r"AppData\Local\Microsoft\Edge\User Data\Default\Cache"), False),
        "Edge miniatúr": (os.path.join(user_home, r"AppData\Local\Microsoft\Edge\User Data\Default\Top Sites"), False),
        "Brave Cache": (os.path.join(user_home, r"AppData\Local\BraveSoftware\Brave-Browser\User Data\Default\Cache"), False),
        "Brave miniatúr": (os.path.join(user_home, r"AppData\Local\BraveSoftware\Brave-Browser\User Data\Default\Top Sites"), False),
        "Comet Cache": (os.path.join(user_home, r"AppData\Local\Perplexity\Comet\User Data\Default\Cache"), False),
        "Comet miniatúr": (os.path.join(user_home, r"AppData\Local\Perplexity\Comet\User Data\Default\Top Sites"), False),
    }
    return system_targets, browser_targets

# --- GUI aplikácia v štýle Windows 11 (ttkbootstrap) s automatickým režimom ---
class CleanerApp:
    def __init__(self, root: tb.Window):
        self.root = root
        self.root.title("PC Čistič")
        self.root.geometry("980x800")

        # Nastav ikonu
        set_window_icon(self.root)

        # Detekcia systému a preferencií
        self.is_windows, self.pref_light, self.is_win11, self.supports_dwm = detect_system_mode()

        # Inicializuj tb.Window tému podľa detekcie
        theme_name = "flatly" if self.pref_light else "darkly"
        # ak root je tb.Window, nastav thema pri vytvorení; tu len uistíme, že style existuje
        try:
            self.root.style.theme_use(theme_name)
        except Exception:
            pass

        # DWM dekorácie (rounded + dark title) ak sú podporované
        if self.is_windows and self.supports_dwm:
            set_win11_window_attributes(get_hwnd(self.root), dark_mode=(not self.pref_light), rounded=self.is_win11)

        # Horný panel s prepínačom témy a info o automatickom režime
        topbar = tb.Frame(root, padding=8)
        topbar.pack(fill="x", padx=10, pady=(10, 0))
        tb.Label(topbar, text="Čistenie PC").pack(side="left")
        self.theme_btn = tb.Button(topbar,
                                   text=("Prepni na tmavú" if self.pref_light else "Prepni na svetlú"),
                                   bootstyle="secondary",
                                   command=self.toggle_theme_manual)
        self.theme_btn.pack(side="right")

        # Notebook
        self.notebook = tb.Notebook(root, bootstyle="primary")
        self.notebook.pack(fill="both", expand=True, pady=10, padx=10)

        # Progressbar
        self.progress = tb.Progressbar(root, orient="horizontal", length=940, mode="determinate", bootstyle="info-striped")
        self.progress.pack(pady=6)

        # Ciele
        self.system_targets, self.browser_targets = get_targets()

        # Tabs
        self.frame_sys = tb.Frame(self.notebook, padding=12)
        self.frame_browser = tb.Frame(self.notebook, padding=12)
        self.frame_bin = tb.Frame(self.notebook, padding=12)
        self.frame_adv = tb.Frame(self.notebook, padding=12)

        self.notebook.add(self.frame_sys, text="🖥️ Systém")
        self.notebook.add(self.frame_browser, text="🌐 Prehliadače")
        self.notebook.add(self.frame_bin, text="🗑️ Kôš")
        self.notebook.add(self.frame_adv, text="⚙️ Pokročilé")

        # Naplnenie tabov
        self.build_system_tab()
        self.build_browser_tab()
        self.build_bin_tab()
        self.build_advanced_tab()

        # Panel výsledkov
        self.build_results_panel()

        # Spodný panel
        bottom = tb.Frame(root, padding=6)
        bottom.pack(fill="x", padx=10, pady=6)
        tb.Button(bottom, text="Koniec", bootstyle="danger", command=root.quit).pack(side="right")

    # --- Téma prepínanie (manuálne) ---
    def toggle_theme_manual(self):
        # prepne tému a aktualizuje DWM titulok ak je Windows
        self.pref_light = not self.pref_light
        theme_name = "flatly" if self.pref_light else "darkly"
        try:
            self.root.style.theme_use(theme_name)
        except Exception:
            pass
        if self.is_windows and self.supports_dwm:
            set_win11_window_attributes(get_hwnd(self.root), dark_mode=(not self.pref_light), rounded=self.is_win11)
        self.theme_btn.configure(text=("Prepnúť na tmavý režim" if self.pref_light else "Prepnúť na svetlý režim"))

    # --- Výsledky (Treeview) ---
    def build_results_panel(self):
        panel = tb.Frame(self.root, padding=10)
        panel.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        tb.Label(panel, text="Výsledky čistenia", bootstyle="inverse-primary").pack(anchor="w", pady=(0, 6))

        columns = ("nazov", "uvolnene", "zmazane", "nezmazane", "poznamka")
        self.tree = tb.Treeview(panel, columns=columns, show="headings", bootstyle="primary")
        self.tree.heading("nazov", text="Cieľ")
        self.tree.heading("uvolnene", text="Uvoľnené (MB)")
        self.tree.heading("zmazane", text="Zmazané")
        self.tree.heading("nezmazane", text="Nezmazané")
        self.tree.heading("poznamka", text="Poznámka")

        self.tree.column("nazov", width=420, anchor="w")
        self.tree.column("uvolnene", width=160, anchor="center")
        self.tree.column("zmazane", width=140, anchor="center")
        self.tree.column("nezmazane", width=140, anchor="center")
        self.tree.column("poznamka", width=220, anchor="w")

        self.tree.pack(fill="both", expand=True)

    def add_result_row(self, result):
        self.tree.insert("", "end", values=(
            result["nazov"],
            f'{result["uvolnene_mb"]:.2f}',
            result["zmazane"],
            result["nezmazane"],
            result.get("poznamka", "")
        ))

    def clear_results(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

    # --- Systém tab ---
    def build_system_tab(self):
        tb.Label(self.frame_sys, text="Vyberte systémové položky na čistenie").pack(anchor="w", pady=(0, 6))

        self.sys_vars = {}
        grid = tb.Frame(self.frame_sys)
        grid.pack(fill="x")

        for i, (name, (path, safe)) in enumerate(self.system_targets.items()):
            var = tk.BooleanVar(value=False)
            self.sys_vars[name] = (var, path, safe)
            tb.Checkbutton(grid, text=f"{name}  —  {path}", variable=var, bootstyle="round-toggle").grid(row=i, column=0, sticky="w", pady=2)

        btns = tb.Frame(self.frame_sys)
        btns.pack(fill="x", pady=8)
        tb.Button(btns, text="🧹 Vyčistiť vybrané", bootstyle="primary", command=self.clean_selected_system).pack(side="left")
        tb.Button(btns, text="🧯 Vyčistiť všetko", bootstyle="secondary", command=self.clean_all_system).pack(side="left", padx=6)

    # --- Prehliadače tab ---
    def build_browser_tab(self):
        tb.Label(self.frame_browser, text="Vyberte prehliadačové položky na čistenie").pack(anchor="w", pady=(0, 6))

        self.browser_vars = {}
        grid = tb.Frame(self.frame_browser)
        grid.pack(fill="x")

        for i, (name, (path, safe)) in enumerate(self.browser_targets.items()):
            var = tk.BooleanVar(value=False)
            self.browser_vars[name] = (var, path, safe)
            tb.Checkbutton(grid, text=f"{name}  —  {path}", variable=var, bootstyle="round-toggle").grid(row=i, column=0, sticky="w", pady=2)

        btns = tb.Frame(self.frame_browser)
        btns.pack(fill="x", pady=8)
        tb.Button(btns, text="🧹 Vyčistiť vybrané", bootstyle="primary", command=self.clean_selected_browser).pack(side="left")
        tb.Button(btns, text="🧯 Vyčistiť všetko", bootstyle="secondary", command=self.clean_all_browser).pack(side="left", padx=6)

    # --- Kôš tab ---
    def build_bin_tab(self):
        tb.Label(self.frame_bin, text="Kôš").pack(anchor="w", pady=(0, 6))
        tb.Button(self.frame_bin, text="🗑️ Vysypať kôš", bootstyle="danger", command=self.empty_recycle_bin).pack(pady=4)

    # --- Pokročilé tab ---
    def build_advanced_tab(self):
        tb.Label(self.frame_adv, text="Rozšírené").pack(anchor="w", pady=(0, 6))
        tb.Button(self.frame_adv, text="🚀 Vyčistiť všetko (Systém + Prehliadače)", bootstyle="success", command=self.clean_everything).pack(pady=4)
        tb.Button(self.frame_adv, text="🧰 Spustiť Čistenie disku (Cleanmgr)", bootstyle="info", command=self.run_cleanmgr).pack(pady=4)

    # --- Čistenie vo vlákne ---
    def run_cleaning_jobs(self, jobs):
        self.progress["value"] = 0
        self.clear_results()

        def worker():
            for name, path, safe in jobs:
                result = vycisti_ciel(path, name, self.progress, safe)
                self.root.after(0, lambda r=result: self.add_result_row(r))
            self.root.after(0, lambda: self.progress.config(value=0))
            messagebox.showinfo("Výsledok čistenia", "Čistenie dokončené. Podrobnosti sú v tabuľke výsledkov.")

        threading.Thread(target=worker, daemon=True).start()

    # --- Handlery ---
    def clean_selected_system(self):
        jobs = [(name, path, safe) for name, (var, path, safe) in self.sys_vars.items() if var.get()]
        if not jobs:
            messagebox.showinfo("Systém", "Nie sú vybrané žiadne položky.")
            return
        self.run_cleaning_jobs(jobs)

    def clean_all_system(self):
        jobs = [(name, path, safe) for name, (path, safe) in self.system_targets.items()]
        self.run_cleaning_jobs(jobs)

    def clean_selected_browser(self):
        jobs = [(name, path, safe) for name, (var, path, safe) in self.browser_vars.items() if var.get()]
        if not jobs:
            messagebox.showinfo("Prehliadače", "Nie sú vybrané žiadne položky.")
            return
        self.run_cleaning_jobs(jobs)

    def clean_all_browser(self):
        jobs = [(name, path, safe) for name, (path, safe) in self.browser_targets.items()]
        self.run_cleaning_jobs(jobs)

    def clean_everything(self):
        jobs = []
        jobs.extend([(name, path, safe) for name, (path, safe) in self.system_targets.items()])
        jobs.extend([(name, path, safe) for name, (path, safe) in self.browser_targets.items()])
        self.run_cleaning_jobs(jobs)

    # --- Kôš ---
    def empty_recycle_bin(self):
        try:
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x0007)
            messagebox.showinfo("Kôš", "Kôš bol úspešne vysypaný.")
        except Exception as e:
            messagebox.showerror("Kôš", f"Nepodarilo sa vysypať Kôš: {e}")

    # --- Cleanmgr ---
    def run_cleanmgr(self):
        try:
            ctypes.windll.shell32.ShellExecuteW(None, "open", "cleanmgr.exe", None, None, 1)
        except Exception as e:
            messagebox.showerror("Čistenie disku", f"Nepodarilo sa spustiť cleanmgr: {e}")

# --- Spustenie aplikácie ---
if __name__ == "__main__":
    # Inicializuj tb.Window s predvolenou témou podľa detekcie (detect_system_mode sa volá v CleanerApp)
    root = tb.Window(themename="flatly")  # predvolená, CleanerApp prepne podľa systému
    app = CleanerApp(root)
    # Ak je Windows a podporuje DWM, aplikuj dekorácie po vytvorení okna
    try:
        is_win, pref_light, is_win11, supports_dwm = detect_system_mode()
        if is_win and supports_dwm:
            set_win11_window_attributes(get_hwnd(root), dark_mode=(not pref_light), rounded=is_win11)
    except Exception:
        pass
    root.mainloop()
