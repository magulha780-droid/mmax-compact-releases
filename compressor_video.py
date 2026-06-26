"""
M.MAX COMPACT - App principal
Hospedado no GitHub. Executado pelo launcher.exe.
Requer: FFmpeg e psutil instalados no sistema.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess, threading, os, sys, shutil, json, urllib.request
from pathlib import Path

# ------------------------------------------------------------------
# Informacoes injetadas pelo launcher (ou defaults se rodar direto)
# ------------------------------------------------------------------
_LAUNCHER = globals().get("_LAUNCHER", {})

CACHE_DIR       = _LAUNCHER.get("cache_dir",      os.path.join(os.environ.get("APPDATA","~"), "MMaxCompact"))
VERSION_URL     = _LAUNCHER.get("version_url",    "https://raw.githubusercontent.com/magulha780-droid/mmax-compact-releases/main/version.json")
SCRIPT_URL      = _LAUNCHER.get("script_url",     "https://raw.githubusercontent.com/magulha780-droid/mmax-compact-releases/main/compressor_video.py")
CACHED_SCRIPT   = _LAUNCHER.get("cached_script",  os.path.join(CACHE_DIR, "compressor_video.py"))
CACHED_VERSION  = _LAUNCHER.get("cached_version", os.path.join(CACHE_DIR, "version.txt"))
LAUNCHER_EXE    = _LAUNCHER.get("launcher_exe",   sys.executable)

# ------------------------------------------------------------------
# Versao atual (lida do cache)
# ------------------------------------------------------------------
def _read_local_version():
    try:
        return open(CACHED_VERSION, encoding="utf-8").read().strip()
    except Exception:
        return "?"

APP_VERSION = _read_local_version()
APP_NAME    = "M.MAX COMPACT"

# ------------------------------------------------------------------
# Cores
# ------------------------------------------------------------------
BG       = "#1e1e2e"
BG2      = "#2a2a3d"
BG3      = "#33334a"
ACCENT   = "#7c6fe0"
ACCENT_H = "#9b8ff5"
TEXT     = "#e0e0f0"
TEXT_DIM = "#888aaa"
GREEN    = "#4ade80"
RED      = "#f87171"
YELLOW   = "#facc15"
ORANGE   = "#fb923c"
BORDER   = "#44446a"

ST_WAIT = ""
ST_PROC = "⌛"
ST_OK   = "✅"
ST_ERR  = "❌"
ST_SKIP = "⚠"

# ------------------------------------------------------------------
# Utilitarios
# ------------------------------------------------------------------

def _no_window():
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}

def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       check=True, **_no_window())
        return True
    except Exception:
        return False

def get_duration_seconds(filepath):
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", filepath],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, **_no_window())
        return float(r.stdout.strip())
    except Exception:
        return None

def format_size(b):
    if b < 1024:       return str(b) + " B"
    if b < 1024**2:    return "{:.1f} KB".format(b / 1024)
    if b < 1024**3:    return "{:.1f} MB".format(b / 1024**2)
    return "{:.2f} GB".format(b / 1024**3)

def play_done_sound():
    try:
        import winsound
        winsound.Beep(523, 120)
        winsound.Beep(659, 120)
        winsound.Beep(784, 240)
    except Exception:
        pass

def suspend_proc(pid):
    try:
        import psutil
        p = psutil.Process(pid)
        for c in p.children(recursive=True): c.suspend()
        p.suspend()
        return True
    except Exception as e:
        return str(e)

def resume_proc(pid):
    try:
        import psutil
        p = psutil.Process(pid)
        for c in p.children(recursive=True): c.resume()
        p.resume()
        return True
    except Exception as e:
        return str(e)

# ------------------------------------------------------------------
# Sistema de atualizacao (atualiza apenas o .py, sem recompilar)
# ------------------------------------------------------------------

def _ver_tuple(v):
    try:    return tuple(int(x) for x in str(v).split("."))
    except: return (0,)

def fetch_remote_version():
    try:
        req = urllib.request.Request(VERSION_URL, headers={"User-Agent": "MMaxCompact"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read()).get("version", "0")
    except Exception:
        return None

def download_new_script(on_progress=None):
    os.makedirs(CACHE_DIR, exist_ok=True)
    req = urllib.request.Request(SCRIPT_URL, headers={"User-Agent": "MMaxCompact"})
    with urllib.request.urlopen(req, timeout=30) as r:
        total = int(r.headers.get("Content-Length", 0))
        data  = b""
        while True:
            chunk = r.read(8192)
            if not chunk: break
            data += chunk
            if on_progress and total:
                on_progress(len(data) / total * 100)
    with open(CACHED_SCRIPT, "wb") as f:
        f.write(data)

def save_version_cache(version):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHED_VERSION, "w", encoding="utf-8") as f:
        f.write(version)

def restart_launcher():
    """Reinicia o launcher.exe para aplicar a atualizacao."""
    try:
        subprocess.Popen([LAUNCHER_EXE])
    except Exception:
        pass
    os._exit(0)

# ------------------------------------------------------------------
# Frame rolavel
# ------------------------------------------------------------------

class ScrollableFrame(tk.Frame):
    def __init__(self, parent, bg=BG2, **kwargs):
        super().__init__(parent, bg=bg, **kwargs)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self._canvas = tk.Canvas(self, bg=bg, bd=0, highlightthickness=0)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._sb = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._sb.grid(row=0, column=1, sticky="ns")
        self._canvas.configure(yscrollcommand=self._sb.set)
        self.inner = tk.Frame(self._canvas, bg=bg)
        self._win_id = self._canvas.create_window((0,0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner)
        self._canvas.bind("<Configure>", self._on_canvas)
        self._canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _on_inner(self, _):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
    def _on_canvas(self, e):
        self._canvas.itemconfig(self._win_id, width=e.width)
    def _on_wheel(self, e):
        self._canvas.yview_scroll(-1 * (e.delta // 120), "units")

# ------------------------------------------------------------------
# App principal
# ------------------------------------------------------------------

class VideoCompressorApp:

    EXTENSIONS = (".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v")
    SORT_OPTIONS = [
        ("Ordem selecionada",        "manual"),
        ("Nome (A-Z)",               "name_asc"),
        ("Nome (Z-A)",               "name_desc"),
        ("Tamanho (menor -> maior)", "size_asc"),
        ("Tamanho (maior -> menor)", "size_desc"),
    ]
    CPU_MODES = [
        ("Normal (todos os nucleos)",      "normal"),
        ("Economico (metade dos nucleos)", "economico"),
        ("Minimo (1 nucleo, frio)",        "minimo"),
    ]

    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME + " v" + APP_VERSION)
        self.root.geometry("980x740")
        self.root.minsize(820, 600)
        self.root.configure(bg=BG)

        self.files            = []
        self.tree_items       = []
        self.last_output_dirs = []
        self.is_running       = False
        self.is_paused        = False
        self.cancel_flag      = threading.Event()
        self.current_proc     = None
        self._pending_version = None

        self._build_ui()
        self._check_ffmpeg_on_start()
        threading.Thread(target=self._silent_update_check, daemon=True).start()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        hdr = tk.Frame(self.root, bg=BG, pady=12)
        hdr.grid(row=0, column=0, sticky="ew", padx=20)

        tk.Label(hdr, text="M.MAX",   font=("Bahnschrift",22,"bold"), bg=BG, fg=ACCENT).pack(side="left")
        tk.Label(hdr, text=" COMPACT",font=("Bahnschrift",22,"bold"), bg=BG, fg=TEXT).pack(side="left")
        tk.Label(hdr, text="   v"+APP_VERSION, font=("Segoe UI",9), bg=BG, fg=TEXT_DIM).pack(side="left", pady=(6,0))

        self.lbl_update_badge = tk.Label(hdr, text="",
                                         font=("Segoe UI",8,"bold"),
                                         bg=ORANGE, fg="white", padx=6, pady=2, cursor="hand2")
        self.lbl_update_badge.pack(side="left", padx=(10,0), pady=(4,0))
        self.lbl_update_badge.bind("<Button-1>", lambda e: self._show_update_dialog())

        tk.Label(hdr, text="Compressor de video profissional",
                 font=("Segoe UI",9), bg=BG, fg=TEXT_DIM).pack(side="right", pady=(6,0))

        body = tk.Frame(self.root, bg=BG)
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0,14))
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, minsize=295)
        body.rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0,10))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=1)
        self._build_file_panel(left)

        right_outer = tk.Frame(body, bg=BG)
        right_outer.grid(row=0, column=1, sticky="nsew")
        right_outer.columnconfigure(0, weight=1)
        right_outer.rowconfigure(0, weight=1)
        self._sf = ScrollableFrame(right_outer, bg=BG)
        self._sf.grid(row=0, column=0, sticky="nsew")
        self._sf.inner.columnconfigure(0, weight=1)
        self._build_settings_panel(self._sf.inner)

    def _build_file_panel(self, parent):
        btn_row = tk.Frame(parent, bg=BG)
        btn_row.grid(row=0, column=0, sticky="ew", pady=(0,6))
        self._btn(btn_row, "+ Adicionar videos", self._add_files, ACCENT).pack(side="left")
        self._btn(btn_row, "x Remover", self._remove_selected, BG3).pack(side="left", padx=(8,0))
        self._btn(btn_row, "Limpar lista", self._clear_files, BG3).pack(side="right")

        sort_row = tk.Frame(parent, bg=BG)
        sort_row.grid(row=1, column=0, sticky="ew", pady=(0,6))
        tk.Label(sort_row, text="Ordenar por:", font=("Segoe UI",8), bg=BG, fg=TEXT_DIM).pack(side="left")
        self.sort_var = tk.StringVar(value="manual")
        sort_labels = [o[0] for o in self.SORT_OPTIONS]
        cb = ttk.Combobox(sort_row, textvariable=self.sort_var, values=sort_labels, state="readonly", width=22)
        cb.pack(side="left", padx=(6,0))
        cb.current(0)
        cb.bind("<<ComboboxSelected>>", self._on_sort_change)

        tf = tk.Frame(parent, bg=BORDER, highlightbackground=BORDER, highlightthickness=1)
        tf.grid(row=2, column=0, sticky="nsew")
        tf.columnconfigure(0, weight=1)
        tf.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(tf, columns=("num","nome","tamanho","status"),
                                  show="headings", selectmode="extended")
        self.tree.heading("num",     text="#",       anchor="center")
        self.tree.heading("nome",    text="Arquivo", anchor="w")
        self.tree.heading("tamanho", text="Tamanho", anchor="e")
        self.tree.heading("status",  text="Status",  anchor="center")
        self.tree.column("num",     width=36,  minwidth=36,  stretch=False, anchor="center")
        self.tree.column("nome",    width=280, anchor="w")
        self.tree.column("tamanho", width=80,  minwidth=70,  stretch=False, anchor="e")
        self.tree.column("status",  width=60,  minwidth=50,  stretch=False, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)

        self.hint = tk.Label(tf, text="Clique em '+ Adicionar videos' para comecar",
                             font=("Segoe UI",10), bg=BG2, fg=TEXT_DIM)
        self.hint.place(relx=0.5, rely=0.5, anchor="center")

        self.lbl_count = tk.Label(parent, text="Nenhum arquivo adicionado",
                                  font=("Segoe UI",8), bg=BG, fg=TEXT_DIM)
        self.lbl_count.grid(row=3, column=0, sticky="w", pady=(6,0))

    def _build_settings_panel(self, parent):
        # Qualidade
        _, iq = self._section(parent, "QUALIDADE DE COMPRESSAO", row=0)
        tk.Label(iq, text="Quanto menor o valor, melhor a qualidade (maior o arquivo).",
                 font=("Segoe UI",8), bg=BG2, fg=TEXT_DIM, wraplength=255, justify="left"
                 ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,4))
        self.crf_var = tk.IntVar(value=23)
        tk.Scale(iq, from_=18, to=28, orient="horizontal", variable=self.crf_var,
                 bg=BG2, fg=TEXT, troughcolor=BG3, activebackground=ACCENT,
                 highlightthickness=0, bd=0, sliderrelief="flat",
                 command=self._update_quality_label
                 ).grid(row=1, column=0, columnspan=2, sticky="ew")
        self.lbl_quality = tk.Label(iq, text="", font=("Segoe UI",9,"bold"), bg=BG2, fg=GREEN)
        self.lbl_quality.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2,0))
        self._update_quality_label(23)

        # Velocidade
        _, iv = self._section(parent, "VELOCIDADE / EFICIENCIA", row=1)
        tk.Label(iv, text="Preset:", font=("Segoe UI",9), bg=BG2, fg=TEXT).grid(row=0, column=0, sticky="w")
        self.preset_var   = tk.StringVar(value="medium")
        self.cpu_mode_var = tk.StringVar(value="normal")
        ttk.Combobox(iv, textvariable=self.preset_var,
                     values=["ultrafast","fast","medium","slow","veryslow"],
                     state="readonly", width=18
                     ).grid(row=1, column=0, sticky="w", pady=(4,0))
        tk.Label(iv, text="'slow' = melhor compressao  |  'fast' = mais rapido",
                 font=("Segoe UI",8), bg=BG2, fg=TEXT_DIM).grid(row=2, column=0, sticky="w", pady=(4,0))

        # CPU
        _, ic = self._section(parent, "USO DA CPU", row=2)
        cpu_count = os.cpu_count() or 4
        tk.Label(ic, text="Controla quantos nucleos o ffmpeg usa. Menos nucleos = menos calor.",
                 font=("Segoe UI",8), bg=BG2, fg=TEXT_DIM, wraplength=255, justify="left"
                 ).grid(row=0, column=0, sticky="w", pady=(0,4))
        tk.Label(ic, text="CPU detectada: {} nucleo(s)".format(cpu_count),
                 font=("Segoe UI",8), bg=BG2, fg=TEXT_DIM).grid(row=1, column=0, sticky="w", pady=(0,6))
        ttk.Combobox(ic, textvariable=self.cpu_mode_var,
                     values=[o[0] for o in self.CPU_MODES],
                     state="readonly", width=28).grid(row=2, column=0, sticky="w")

        # Destino
        _, id_ = self._section(parent, "PASTA DE DESTINO", row=3)
        self.output_mode = tk.StringVar(value="subfolder")
        for val, lbl in [("subfolder","Criar pasta 'comprimidos' na origem"),
                          ("choose","Escolher pasta de destino"),
                          ("replace","Substituir arquivo original")]:
            tk.Radiobutton(id_, text=lbl, variable=self.output_mode, value=val,
                           bg=BG2, fg=TEXT, selectcolor=BG3,
                           activebackground=BG2, activeforeground=TEXT,
                           font=("Segoe UI",9),
                           command=self._toggle_folder_btn).pack(anchor="w")
        self.btn_choose_folder = self._btn(id_, "Escolher pasta...", self._choose_dest_folder, BG3, full=True)
        self.btn_choose_folder.pack(fill="x", pady=(6,0))
        self.lbl_dest = tk.Label(id_, text="", font=("Segoe UI",8), bg=BG2, fg=TEXT_DIM, wraplength=240, justify="left")
        self.lbl_dest.pack(anchor="w", pady=(2,0))
        self.dest_folder = ""
        self._toggle_folder_btn()

        # Progresso
        _, ip = self._section(parent, "PROGRESSO", row=4)
        ip.columnconfigure(0, weight=1)
        self.lbl_status = tk.Label(ip, text="Aguardando...",
                                   font=("Segoe UI",9), bg=BG2, fg=TEXT_DIM, wraplength=240, justify="left")
        self.lbl_status.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,6))

        tk.Label(ip, text="Total:", font=("Segoe UI",8), bg=BG2, fg=TEXT_DIM).grid(row=1, column=0, sticky="w")
        pr1 = tk.Frame(ip, bg=BG2)
        pr1.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(2,6))
        pr1.columnconfigure(0, weight=1)
        self.progress_total = ttk.Progressbar(pr1, mode="determinate", maximum=100)
        self.progress_total.grid(row=0, column=0, sticky="ew")
        self.lbl_pct_total = tk.Label(pr1, text="0%", font=("Segoe UI",9,"bold"), bg=BG2, fg=ACCENT, width=5)
        self.lbl_pct_total.grid(row=0, column=1, sticky="w", padx=(6,0))

        tk.Label(ip, text="Arquivo atual:", font=("Segoe UI",8), bg=BG2, fg=TEXT_DIM).grid(row=3, column=0, sticky="w")
        pr2 = tk.Frame(ip, bg=BG2)
        pr2.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(2,0))
        pr2.columnconfigure(0, weight=1)
        self.progress_file = ttk.Progressbar(pr2, mode="determinate", maximum=100)
        self.progress_file.grid(row=0, column=0, sticky="ew")
        self.lbl_pct_file = tk.Label(pr2, text="0%", font=("Segoe UI",9,"bold"), bg=BG2, fg=YELLOW, width=5)
        self.lbl_pct_file.grid(row=0, column=1, sticky="w", padx=(6,0))

        self.lbl_file_prog = tk.Label(ip, text="", font=("Segoe UI",8), bg=BG2, fg=TEXT_DIM, wraplength=240)
        self.lbl_file_prog.grid(row=5, column=0, columnspan=2, sticky="w", pady=(4,0))

        # Botoes
        btn_outer = tk.Frame(parent, bg=BG, pady=6)
        btn_outer.grid(row=5, column=0, sticky="ew", padx=6)
        btn_outer.columnconfigure(0, weight=1)
        btn_outer.columnconfigure(1, weight=1)

        self.btn_start = self._btn(btn_outer, "Iniciar compressao",
                                   self._start_compression, ACCENT, full=True, font_size=11)
        self.btn_start.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0,6))

        self.btn_pause = self._btn(btn_outer, "Pausar", self._toggle_pause, ORANGE, full=True)
        self.btn_pause.grid(row=1, column=0, sticky="ew", padx=(0,4))
        self.btn_pause.configure(state="disabled")

        self.btn_cancel = self._btn(btn_outer, "Cancelar", self._cancel, BG3, full=True)
        self.btn_cancel.grid(row=1, column=1, sticky="ew", padx=(4,0))
        self.btn_cancel.configure(state="disabled")

        # Resultado
        _, il = self._section(parent, "RESULTADO", row=6)
        il.columnconfigure(0, weight=1)
        self.txt_log = tk.Text(il, height=6, bg=BG3, fg=TEXT,
                               font=("Courier New",8), bd=0,
                               highlightthickness=0, state="disabled", wrap="word")
        self.txt_log.grid(row=0, column=0, sticky="nsew")
        self.txt_log.tag_config("ok",   foreground=GREEN)
        self.txt_log.tag_config("err",  foreground=RED)
        self.txt_log.tag_config("skip", foreground=YELLOW)

        row2 = tk.Frame(il, bg=BG2)
        row2.grid(row=1, column=0, sticky="ew", pady=(6,0))
        row2.columnconfigure(0, weight=1)
        row2.columnconfigure(1, weight=1)

        self.btn_show_folder = self._btn(row2, "Mostrar na pasta", self._show_output_folder, BG3, full=True)
        self.btn_show_folder.grid(row=0, column=0, sticky="ew", padx=(0,4))
        self.btn_show_folder.configure(state="disabled")

        self.btn_check_update = self._btn(row2, "Verificar atualizacoes", self._manual_update_check, BG3, full=True)
        self.btn_check_update.grid(row=0, column=1, sticky="ew", padx=(4,0))

        tk.Frame(parent, bg=BG, height=10).grid(row=7, column=0)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _section(self, parent, title, row=0):
        outer = tk.Frame(parent, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        outer.grid(row=row, column=0, sticky="ew", padx=6, pady=(0,8))
        outer.columnconfigure(0, weight=1)
        tk.Label(outer, text=title, font=("Segoe UI",8,"bold"),
                 bg=BG2, fg=ACCENT).grid(row=0, column=0, sticky="w", padx=10, pady=(8,2))
        inner = tk.Frame(outer, bg=BG2)
        inner.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0,10))
        inner.columnconfigure(0, weight=1)
        return outer, inner

    def _btn(self, parent, text, cmd, color, full=False, font_size=9):
        b = tk.Button(parent, text=text, command=cmd,
                      bg=color, fg=TEXT, activebackground=ACCENT_H,
                      activeforeground="white", relief="flat", bd=0,
                      padx=10, pady=6, cursor="hand2",
                      font=("Segoe UI", font_size))
        b.bind("<Enter>", lambda e, c=color: b.configure(bg=ACCENT_H))
        b.bind("<Leave>", lambda e, c=color: b.configure(bg=c))
        return b

    def _update_quality_label(self, val=None):
        crf = int(self.crf_var.get())
        if   crf <= 20: self.lbl_quality.configure(text="CRF {}  -  Alta qualidade (arquivo maior)".format(crf),  fg=GREEN)
        elif crf <= 24: self.lbl_quality.configure(text="CRF {}  -  Qualidade equilibrada".format(crf),           fg=YELLOW)
        else:           self.lbl_quality.configure(text="CRF {}  -  Maior compressao (leve perda)".format(crf),   fg=RED)

    def _toggle_folder_btn(self):
        if self.output_mode.get() == "choose":
            self.btn_choose_folder.configure(state="normal")
        else:
            self.btn_choose_folder.configure(state="disabled")
            self.dest_folder = ""
            self.lbl_dest.configure(text="")

    def _log(self, msg, tag=""):
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", msg+"\n", tag)
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.tree_items = []
        for i, path in enumerate(self.files):
            name = Path(path).name
            try:   size_str = format_size(os.path.getsize(path))
            except: size_str = "?"
            iid = self.tree.insert("", "end", values=(str(i+1), name, size_str, ST_WAIT))
            self.tree_items.append(iid)

    def _set_item_status(self, idx, status):
        if 0 <= idx < len(self.tree_items):
            iid = self.tree_items[idx]
            self.root.after(0, lambda i=iid, s=status: self.tree.set(i, "status", s))

    def _update_count(self):
        n = len(self.files)
        if n == 0:
            self.lbl_count.configure(text="Nenhum arquivo adicionado")
            self.hint.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self.hint.place_forget()
            total = sum(os.path.getsize(p) for p in self.files if os.path.exists(p))
            self.lbl_count.configure(text="{} arquivo(s)  -  {}".format(n, format_size(total)))

    def _on_sort_change(self, event=None):
        label = self.sort_var.get()
        key   = next((k for l,k in self.SORT_OPTIONS if l == label), "manual")
        if key == "manual": return
        if   key == "name_asc":  self.files.sort(key=lambda p: Path(p).name.lower())
        elif key == "name_desc": self.files.sort(key=lambda p: Path(p).name.lower(), reverse=True)
        elif key == "size_asc":  self.files.sort(key=lambda p: os.path.getsize(p) if os.path.exists(p) else 0)
        elif key == "size_desc": self.files.sort(key=lambda p: os.path.getsize(p) if os.path.exists(p) else 0, reverse=True)
        self._refresh_tree()

    # ------------------------------------------------------------------
    # Acoes de arquivos
    # ------------------------------------------------------------------

    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="Selecionar videos",
            filetypes=[("Videos", " ".join("*"+e for e in self.EXTENSIONS)),
                       ("Todos os arquivos", "*.*")])
        for p in paths:
            if p not in self.files:
                self.files.append(p)
        self._refresh_tree()
        self._update_count()

    def _remove_selected(self):
        selected = self.tree.selection()
        if not selected: return
        for i in sorted([self.tree.index(it) for it in selected], reverse=True):
            self.files.pop(i)
        self._refresh_tree()
        self._update_count()

    def _clear_files(self):
        self.files.clear()
        self._refresh_tree()
        self._update_count()

    def _choose_dest_folder(self):
        folder = filedialog.askdirectory(title="Escolher pasta de destino")
        if folder:
            self.dest_folder = folder
            short = folder if len(folder) <= 34 else "..."+folder[-32:]
            self.lbl_dest.configure(text=short)

    def _show_output_folder(self):
        if not self.last_output_dirs: return
        folder = self.last_output_dirs[0]
        try:
            if os.name == "nt": os.startfile(folder)
            else: subprocess.Popen(["xdg-open", folder])
        except Exception as exc:
            messagebox.showerror("Erro", "Nao foi possivel abrir a pasta:\n"+str(exc))

    # ------------------------------------------------------------------
    # Pausa / Retomada
    # ------------------------------------------------------------------

    def _toggle_pause(self):
        if not self.is_running or not self.current_proc: return
        pid = self.current_proc.pid
        if not self.is_paused:
            r = suspend_proc(pid)
            if r is True:
                self.is_paused = True
                self.root.after(0, self._apply_paused_ui)
            else:
                messagebox.showerror("Erro ao pausar", "Instale o psutil:\n  pip install psutil\n\n"+str(r))
        else:
            r = resume_proc(pid)
            if r is True:
                self.is_paused = False
                self.root.after(0, self._apply_running_ui)
            else:
                messagebox.showerror("Erro ao retomar", str(r))

    def _apply_paused_ui(self):
        self.btn_pause.configure(text="Retomar", bg=GREEN)
        self.btn_pause.bind("<Leave>", lambda e: self.btn_pause.configure(bg=GREEN))
        self._set_status("Pausado. Clique em 'Retomar' para continuar.")

    def _apply_running_ui(self):
        self.btn_pause.configure(text="Pausar", bg=ORANGE)
        self.btn_pause.bind("<Leave>", lambda e: self.btn_pause.configure(bg=ORANGE))
        self._set_status("Retomado.")

    # ------------------------------------------------------------------
    # Compressao
    # ------------------------------------------------------------------

    def _start_compression(self):
        if not self.files:
            messagebox.showwarning("Sem arquivos", "Adicione pelo menos um video a lista.")
            return
        if self.output_mode.get() == "choose" and not self.dest_folder:
            messagebox.showwarning("Pasta nao selecionada", "Escolha uma pasta de destino antes de iniciar.")
            return

        self.is_running = True
        self.is_paused  = False
        self.cancel_flag.clear()
        self.last_output_dirs = []

        self.btn_start.configure(state="disabled")
        self.btn_pause.configure(state="normal", text="Pausar", bg=ORANGE)
        self.btn_cancel.configure(state="normal")
        self.btn_show_folder.configure(state="disabled")
        self.progress_total["value"] = 0
        self.progress_file["value"]  = 0
        self.lbl_pct_total.configure(text="0%")
        self.lbl_pct_file.configure(text="0%")
        self.txt_log.configure(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.configure(state="disabled")

        for iid in self.tree_items:
            self.tree.set(iid, "status", ST_WAIT)

        threading.Thread(target=self._run_batch, daemon=True).start()

    def _run_batch(self):
        files  = list(self.files)
        total  = len(files)
        crf    = self.crf_var.get()
        preset = self.preset_var.get()
        mode   = self.output_mode.get()
        output_dirs = set()

        for idx, src in enumerate(files):
            if self.cancel_flag.is_set(): break

            name = Path(src).name
            self._set_status("[{}/{}] {}".format(idx+1, total, name))
            self._set_file_prog("Processando: "+name)
            self._set_file_progress(0)
            self._set_item_status(idx, ST_PROC)

            out_path = self._resolve_output(src, mode)
            if out_path is None:
                self._log("ERRO: {} - destino invalido".format(name), "err")
                self._set_item_status(idx, ST_ERR)
                continue

            output_dirs.add(str(out_path.parent))
            duration  = get_duration_seconds(src)
            tmp_path  = out_path.with_suffix(".tmp"+out_path.suffix)
            orig_size = os.path.getsize(src)

            success = self._run_ffmpeg(src, str(tmp_path), crf, preset, duration, idx, total, self._get_cpu_threads())

            if self.cancel_flag.is_set():
                if tmp_path.exists(): tmp_path.unlink()
                self._set_item_status(idx, ST_ERR)
                break

            if success:
                comp_size = os.path.getsize(str(tmp_path))

                if comp_size >= orig_size and mode != "replace":
                    tmp_path.unlink()
                    self._log("AVISO: {} ja esta otimizado — mantido original\n   {} (comprimido seria {})".format(
                        name, format_size(orig_size), format_size(comp_size)), "skip")
                    self._set_item_status(idx, ST_SKIP)
                else:
                    if mode == "replace":
                        shutil.move(str(tmp_path), src)
                        comp_size = os.path.getsize(src)
                        self._log("OK {} - substituido ({})".format(name, format_size(comp_size)), "ok")
                    else:
                        shutil.move(str(tmp_path), str(out_path))
                        saving = (1.0 - comp_size/orig_size)*100 if orig_size else 0
                        self._log("OK {}\n   {} -> {}  (-{:.1f}%)".format(
                            name, format_size(orig_size), format_size(comp_size), saving), "ok")
                    self._set_item_status(idx, ST_OK)
            else:
                if tmp_path.exists(): tmp_path.unlink()
                if not self.cancel_flag.is_set():
                    self._log("ERRO: {} - falha na compressao".format(name), "err")
                    self._set_item_status(idx, ST_ERR)

            self._set_total_progress((idx+1)/total*100)

        self.last_output_dirs = list(output_dirs)
        self.root.after(0, self._on_done)

    def _resolve_output(self, src, mode):
        p = Path(src)
        if mode == "subfolder":
            d = p.parent / "comprimidos"
            d.mkdir(exist_ok=True)
            return d / p.name
        if mode == "choose":
            return Path(self.dest_folder) / p.name
        if mode == "replace":
            return p.parent / p.name
        return None

    def _get_cpu_threads(self):
        cpu_count = os.cpu_count() or 4
        mode = self.cpu_mode_var.get()
        key  = next((k for l,k in self.CPU_MODES if l == mode), "normal")
        if key == "economico": return max(1, cpu_count // 2)
        if key == "minimo":    return max(1, cpu_count // 4)
        return 0

    def _set_proc_priority(self, pid):
        mode = self.cpu_mode_var.get()
        key  = next((k for l,k in self.CPU_MODES if l == mode), "normal")
        if key == "normal": return
        try:
            import psutil
            p = psutil.Process(pid)
            if key == "economico":
                p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if os.name=="nt" else 10)
            elif key == "minimo":
                p.nice(psutil.IDLE_PRIORITY_CLASS if os.name=="nt" else 19)
        except Exception:
            pass

    def _run_ffmpeg(self, src, dst, crf, preset, duration, file_idx, file_total, cpu_threads=0):
        thread_args = ["-threads", str(cpu_threads)] if cpu_threads > 0 else []
        cmd = ["ffmpeg", "-y", "-i", src] + thread_args + [
               "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
               "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
               "-progress", "pipe:1", dst]
        try:
            self.current_proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, bufsize=1, **_no_window())
            self._set_proc_priority(self.current_proc.pid)
            for line in self.current_proc.stdout:
                if self.cancel_flag.is_set():
                    self.current_proc.terminate()
                    return False
                if duration and line.startswith("out_time_ms="):
                    try:
                        ms = int(line.split("=")[1].strip())
                        fp = min(ms/(duration*1000000)*100, 100)
                        self._set_file_progress(fp)
                        self._set_total_progress((file_idx + fp/100)/file_total*100)
                    except ValueError:
                        pass
            self.current_proc.wait()
            ok = self.current_proc.returncode == 0
            self.current_proc = None
            return ok
        except Exception as exc:
            self._log("Erro ffmpeg: "+str(exc), "err")
            return False

    def _on_done(self):
        self.is_running = False
        self.is_paused  = False
        self.btn_start.configure(state="normal")
        self.btn_pause.configure(state="disabled", text="Pausar", bg=ORANGE)
        self.btn_cancel.configure(state="disabled")
        if self.cancel_flag.is_set():
            self._set_status("Cancelado.")
            self._set_file_prog("")
        else:
            self._set_total_progress(100)
            self._set_file_progress(100)
            self._set_status("Concluido!")
            self._set_file_prog("{} video(s) processado(s).".format(len(self.files)))
            if self.last_output_dirs:
                self.btn_show_folder.configure(state="normal")
            threading.Thread(target=play_done_sound, daemon=True).start()

    def _cancel(self):
        if self.is_paused and self.current_proc:
            resume_proc(self.current_proc.pid)
            self.is_paused = False
        self.cancel_flag.set()
        if self.current_proc:
            try: self.current_proc.terminate()
            except: pass
        self._set_status("Cancelando...")

    # ------------------------------------------------------------------
    # Thread-safe setters
    # ------------------------------------------------------------------

    def _set_total_progress(self, pct):
        pct = min(max(pct,0),100)
        self.root.after(0, lambda: (
            self.progress_total.configure(value=pct),
            self.lbl_pct_total.configure(text="{}%".format(int(pct)))
        ))

    def _set_file_progress(self, pct):
        pct = min(max(pct,0),100)
        self.root.after(0, lambda: (
            self.progress_file.configure(value=pct),
            self.lbl_pct_file.configure(text="{}%".format(int(pct)))
        ))

    def _set_status(self, msg):
        self.root.after(0, lambda: self.lbl_status.configure(text=msg))

    def _set_file_prog(self, msg):
        self.root.after(0, lambda: self.lbl_file_prog.configure(text=msg))

    # ------------------------------------------------------------------
    # Sistema de atualizacao
    # ------------------------------------------------------------------

    def _silent_update_check(self):
        remote = fetch_remote_version()
        if remote and _ver_tuple(remote) > _ver_tuple(APP_VERSION):
            self._pending_version = remote
            self.root.after(0, lambda: self._show_update_badge(remote))

    def _show_update_badge(self, version):
        self.lbl_update_badge.configure(text="Nova versao {} disponivel!".format(version))

    def _show_update_dialog(self):
        version = self._pending_version
        if not version: return
        resp = messagebox.askyesno(
            "Atualizacao disponivel",
            "Versao {} disponivel (atual: {}).\n\n"
            "Deseja baixar e instalar agora?\n"
            "O programa sera reiniciado automaticamente.".format(version, APP_VERSION))
        if resp:
            self._do_update(version)

    def _do_update(self, version):
        dlg = tk.Toplevel(self.root)
        dlg.title("Atualizando...")
        dlg.geometry("360x120")
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.grab_set()

        tk.Label(dlg, text="Baixando versao {}...".format(version),
                 font=("Segoe UI",10), bg=BG, fg=TEXT).pack(pady=(20,8))
        bar = ttk.Progressbar(dlg, mode="determinate", maximum=100, length=300)
        bar.pack()
        lbl_pct = tk.Label(dlg, text="0%", font=("Segoe UI",9), bg=BG, fg=TEXT_DIM)
        lbl_pct.pack(pady=4)

        def _progress(pct):
            self.root.after(0, lambda v=pct: (
                bar.configure(value=v),
                lbl_pct.configure(text="{}%".format(int(v)))
            ))

        def _run():
            try:
                download_new_script(_progress)
                save_version_cache(version)
                self.root.after(0, lambda: (
                    dlg.destroy(),
                    self._offer_restart()
                ))
            except Exception as exc:
                self.root.after(0, lambda: (
                    dlg.destroy(),
                    messagebox.showerror("Erro no download", str(exc))
                ))

        threading.Thread(target=_run, daemon=True).start()

    def _offer_restart(self):
        resp = messagebox.askyesno(
            "Atualizacao concluida",
            "Atualizacao baixada com sucesso!\n\nReiniciar o programa agora?")
        if resp:
            restart_launcher()

    def _manual_update_check(self):
        self.btn_check_update.configure(state="disabled", text="Verificando...")

        def _run():
            remote = fetch_remote_version()
            def _ui():
                self.btn_check_update.configure(state="normal", text="Verificar atualizacoes")
                if remote and _ver_tuple(remote) > _ver_tuple(APP_VERSION):
                    self._pending_version = remote
                    self._show_update_badge(remote)
                    self._show_update_dialog()
                else:
                    messagebox.showinfo("Atualizacoes",
                                        "Voce ja esta na versao mais recente!\nVersao atual: "+APP_VERSION)
            self.root.after(0, _ui)

        threading.Thread(target=_run, daemon=True).start()

    # ------------------------------------------------------------------
    # FFmpeg
    # ------------------------------------------------------------------

    def _check_ffmpeg_on_start(self):
        if not check_ffmpeg():
            messagebox.showerror(
                "FFmpeg nao encontrado",
                "O FFmpeg nao foi encontrado no seu sistema.\n\n"
                "Instale via winget (Prompt de Comando):\n"
                "  winget install ffmpeg\n\n"
                "Ou baixe em: https://ffmpeg.org/download.html")


# ------------------------------------------------------------------
# Estilos
# ------------------------------------------------------------------

def apply_styles(root):
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure("Treeview",
                background=BG2, foreground=TEXT,
                fieldbackground=BG2, rowheight=24, borderwidth=0)
    s.configure("Treeview.Heading",
                background=BG3, foreground=ACCENT,
                relief="flat", font=("Segoe UI",8,"bold"))
    s.map("Treeview",
          background=[("selected", ACCENT)],
          foreground=[("selected", "white")])
    s.configure("TScrollbar",
                background=BG3, troughcolor=BG2,
                arrowcolor=TEXT_DIM, bordercolor=BG2)
    s.configure("TCombobox",
                fieldbackground=BG3, background=BG3,
                foreground=TEXT, arrowcolor=TEXT, selectbackground=ACCENT)
    s.map("TCombobox", fieldbackground=[("readonly", BG3)])
    s.configure("Horizontal.TProgressbar",
                troughcolor=BG3, background=ACCENT,
                bordercolor=BG2, lightcolor=ACCENT, darkcolor=ACCENT)


# ------------------------------------------------------------------
# Entrada
# ------------------------------------------------------------------

if __name__ == "__main__":
    root = tk.Tk()
    apply_styles(root)
    app = VideoCompressorApp(root)
    root.mainloop()
