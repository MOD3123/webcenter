import os, shutil, tkinter as tk
from tkinter import ttk, messagebox
import ctypes, sys

# --- Funkcie ---
def vycisti_cestu(path, nazov, progress=None):
    if not path or not os.path.exists(path):
        return f"{nazov}: priečinok/súbor neexistuje."
    uvolnene = 0
    try:
        if os.path.isfile(path):
            uvolnene += os.path.getsize(path)
            os.remove(path)
        else:
            polozky = []
            for root, dirs, files in os.walk(path, topdown=False):
                for f in files:
                    polozky.append(os.path.join(root, f))
                for d in dirs:
                    polozky.append(os.path.join(root, d))
            total = len(polozky)
            done = 0
            for item in polozky:
                try:
                    if os.path.isfile(item):
                        uvolnene += os.path.getsize(item)
                        os.remove(item)
                    else:
                        shutil.rmtree(item)
                except Exception:
                    pass
                done += 1
                if progress and total > 0:
                    progress["value"] = int(done / total * 100)
                    progress.update()
    except Exception:
        pass
    return f"{nazov}: uvoľnené {round(uvolnene/1024/1024,2)} MB"

def spusti_cistenie(ciele, progress):
    vysledky = []
    progress["value"] = 0
    progress.update()
    for nazov, cesta in ciele.items():
        vysledky.append(vycisti_cestu(cesta, nazov, progress))
    messagebox.showinfo("Výsledok čistenia", "\n".join(vysledky))
    progress["value"] = 0

def vysypat_kos():
    try:
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x0007)
        messagebox.showinfo("Kôš", "Kôš bol úspešne vysypaný.")
    except Exception as e:
        messagebox.showerror("Kôš", f"Nepodarilo sa vysypať Kôš: {e}")

def spusti_cleanmgr():
    try:
        ctypes.windll.shell32.ShellExecuteW(None, "open", "cleanmgr.exe", None, None, 1)
    except Exception as e:
        messagebox.showerror("Čistenie disku", f"Nepodarilo sa spustiť cleanmgr: {e}")

# --- Spustenie ako správca hneď ---
if not ctypes.windll.shell32.IsUserAnAdmin():
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()

# --- GUI ---
root = tk.Tk()
root.title("PC Čistič")
root.geometry("750x600")

# Nastavenie ikony okna
root.iconbitmap("icon.ico")

# Tmavý režim
style = ttk.Style()
style.theme_use("clam")

bg_color = "#2b2b2b"
fg_color = "#ffffff"
btn_bg = "#444444"
btn_active = "#666666"
tab_bg = "#333333"
tab_active = "#555555"

root.configure(bg=bg_color)

style.configure("TNotebook", background=bg_color, borderwidth=0)
style.configure("TNotebook.Tab", background=tab_bg, foreground=fg_color, padding=[10,5])
style.map("TNotebook.Tab", background=[("selected", tab_active)], foreground=[("selected", fg_color)])

style.configure("TButton", background=btn_bg, foreground=fg_color, font=("Segoe UI", 11), padding=6)
style.map("TButton", background=[("active", btn_active)], foreground=[("active", fg_color)])

style.configure("TLabel", background=bg_color, foreground=fg_color, font=("Segoe UI", 11))
style.configure("TProgressbar", troughcolor=bg_color, background="#00aa00", bordercolor=bg_color,
                lightcolor="#00aa00", darkcolor="#008800")

notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True, pady=10)

progress = ttk.Progressbar(root, orient="horizontal", length=700, mode="determinate")
progress.pack(pady=5)

# --- Systém ---
frame_sys = ttk.Frame(notebook, padding=10)
notebook.add(frame_sys, text="Systém")

systemove_ciele = {
    "používateľského TEMP": os.environ.get("TEMP"),
    "Windows TEMP": r"C:\Windows\Temp",
    "Windows Update cache": r"C:\Windows\SoftwareDistribution\Download",
    "miniatúr (Explorer)": os.path.expanduser("~\\AppData\\Local\\Microsoft\\Windows\\Explorer"),
    "Prefetch": r"C:\Windows\Prefetch",
    "nedávnych dokumentov": os.path.expanduser("~\\AppData\\Roaming\\Microsoft\\Windows\\Recent"),
    "systémových logov": r"C:\Windows\Logs",
    "optimalizácie doručovania": r"C:\Windows\SoftwareDistribution\DeliveryOptimization"
}

for nazov in systemove_ciele.keys():
    ttk.Button(frame_sys, text=f"Čistenie {nazov}", width=65,
               command=lambda l=nazov: spusti_cistenie({l: systemove_ciele[l]}, progress)).pack(pady=3)

# --- Prehliadače (bez cookies) ---
frame_browser = ttk.Frame(notebook, padding=10)
notebook.add(frame_browser, text="Prehliadače")

prehliadace_ciele = {
    "Edge Cache": os.path.expanduser("~\\AppData\\Local\\Microsoft\\Edge\\User Data\\Default\\Cache"),
    "Edge miniatúr": os.path.expanduser("~\\AppData\\Local\\Microsoft\\Edge\\User Data\\Default\\Top Sites"),
    "Brave Cache": os.path.expanduser("~\\AppData\\Local\\BraveSoftware\\Brave-Browser\\User Data\\Default\\Cache"),
    "Brave miniatúr": os.path.expanduser("~\\AppData\\Local\\BraveSoftware\\Brave-Browser\\User Data\\Default\\Top Sites"),
    "Comet Cache": r"C:\Users\penia\AppData\Local\Perplexity\Comet\User Data\Default\Cache",
    "Comet miniatúr": r"C:\Users\penia\AppData\Local\Perplexity\Comet\User Data\Default\Top Sites"
}

for nazov in prehliadace_ciele.keys():
    ttk.Button(frame_browser, text=f"Čistenie {nazov}", width=65,
               command=lambda l=nazov: messagebox.showinfo("Výsledok", vycisti_cestu(prehliadace_ciele[l], l, progress))).pack(pady=3)

# --- Kôš ---
frame_bin = ttk.Frame(notebook, padding=10)
notebook.add(frame_bin, text="Kôš")
ttk.Button(frame_bin, text="Vysypať kôš", width=65, command=vysypat_kos).pack(pady=20)

# --- Pokročilé ---
frame_adv = ttk.Frame(notebook, padding=10)
notebook.add(frame_adv, text="Pokročilé")

def vycisti_vsetko():
    spusti_cistenie(systemove_ciele, progress)
    for nazov, cesta in prehliadace_ciele.items():
        vycisti_cestu(cesta, nazov, progress)
    vysypat_kos()

ttk.Button(frame_adv, text="Čistenie všetkého naraz", width=65, command=vycisti_vsetko).pack(pady=10)
ttk.Button(frame_adv, text="Spustiť Čistenie disku (Cleanmgr)", width=65, command=spusti_cleanmgr).pack(pady=10)

# --- Koniec ---
ttk.Button(root, text="Koniec", command=root.quit).pack(pady=5)

root.mainloop()