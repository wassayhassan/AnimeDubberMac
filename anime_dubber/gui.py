from __future__ import annotations

import json
import queue
import re
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

APP_BG = "#F5F5F7"
CARD_BG = "#FFFFFF"
TEXT_PRIMARY = "#1D1D1F"
TEXT_SECONDARY = "#6E6E73"
BORDER = "#D2D2D7"
ACCENT = "#0A84FF"
LOG_BG = "#151517"
LOG_FG = "#F2F2F7"


def configure_styles(root):
    style = ttk.Style(root)
    if "aqua" in style.theme_names():
        try:
            style.theme_use("aqua")
        except tk.TclError:
            pass
    style.configure("Accent.TButton", font=("Helvetica Neue", 12, "bold"), padding=(16, 9))
    style.configure("Secondary.TButton", font=("Helvetica Neue", 11), padding=(12, 7))
    style.configure("Danger.TButton", font=("Helvetica Neue", 11), padding=(12, 7))
    style.configure("Section.TLabel", font=("Helvetica Neue", 13, "bold"))
    style.configure("Field.TLabel", font=("Helvetica Neue", 11, "bold"))
    style.configure("Hint.TLabel", font=("Helvetica Neue", 10))
    style.configure("Status.TLabel", font=("Helvetica Neue", 11))
    style.configure("TNotebook", tabmargins=(0, 4, 0, 0))
    style.configure("TNotebook.Tab", padding=(14, 8), font=("Helvetica Neue", 11))


from .core import (
    Config,
    CommandRunner,
    analyze_only,
    doctor,
    list_macos_voices,
    run_pipeline,
    source_key,
)


class CharacterManager(tk.Toplevel):
    def __init__(self, parent, path: Path, voices):
        super().__init__(parent)
        self.path = path
        self.voices = list(voices)
        configure_styles(self)
        self.configure(bg=APP_BG)
        self.title("Character Voices")
        self.geometry("1080x640")
        self.minsize(900, 520)
        try:
            self.data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            messagebox.showerror("Character map", f"Could not read {path}\n\n{e}", parent=self)
            self.destroy(); return
        self.rows = {str(x.get("id")): x for x in self.data.get("characters", [])}

        top = ttk.Frame(self, padding=12); top.pack(fill="both", expand=True)
        ttk.Label(top, text="Detected characters", font=("", 17, "bold")).pack(anchor="w")
        ttk.Label(
            top,
            text="Automatic male/female-style, child/adult/older, and role labels are acoustic/prominence estimates. Edit anything that sounds wrong; saved edits are reused.",
            wraplength=980,
        ).pack(anchor="w", pady=(2, 8))

        cols=("id","role","voice_class","age","lines","share","style","voice")
        self.tree=ttk.Treeview(top, columns=cols, show="headings", height=12)
        labels={"id":"Character","role":"Role","voice_class":"Voice type","age":"Age","lines":"Lines","share":"Speech share","style":"Style counts","voice":"macOS voice"}
        widths={"id":115,"role":100,"voice_class":95,"age":80,"lines":65,"share":90,"style":200,"voice":120}
        for c in cols:
            self.tree.heading(c,text=labels[c]); self.tree.column(c,width=widths[c],anchor="w")
        self.tree.pack(fill="both",expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        editor=ttk.LabelFrame(top,text="Selected character",padding=10); editor.pack(fill="x",pady=(10,0))
        self.name=tk.StringVar(); self.role=tk.StringVar(); self.voice_class=tk.StringVar(); self.age=tk.StringVar(); self.voice=tk.StringVar(); self.rate=tk.IntVar(value=205); self.pitch=tk.DoubleVar(value=0); self.gain=tk.DoubleVar(value=1.0)
        fields=[
            ("Name",ttk.Entry(editor,textvariable=self.name,width=20)),
            ("Role",ttk.Combobox(editor,textvariable=self.role,values=["lead","major","supporting","minor"],state="readonly",width=12)),
            ("Voice type",ttk.Combobox(editor,textvariable=self.voice_class,values=["male","female","neutral"],state="readonly",width=10)),
            ("Age",ttk.Combobox(editor,textvariable=self.age,values=["child","adult","older"],state="readonly",width=9)),
            ("macOS voice",ttk.Combobox(editor,textvariable=self.voice,values=[""]+self.voices,state="normal",width=16)),
            ("Rate",ttk.Spinbox(editor,from_=120,to=330,increment=5,textvariable=self.rate,width=7)),
            ("Pitch",ttk.Spinbox(editor,from_=-8,to=8,increment=.25,textvariable=self.pitch,width=7)),
            ("Gain",ttk.Spinbox(editor,from_=0.4,to=2.0,increment=.05,textvariable=self.gain,width=7)),
        ]
        for i,(lab,w) in enumerate(fields):
            ttk.Label(editor,text=lab).grid(row=0,column=i,padx=3,sticky="w")
            w.grid(row=1,column=i,padx=3,sticky="ew")
        editor.columnconfigure(0,weight=1)
        b=ttk.Frame(top); b.pack(fill="x",pady=(9,0))
        ttk.Button(b,text="Apply to selected",command=self.apply_selected).pack(side="left")
        ttk.Button(b,text="Preview voice",command=self.preview).pack(side="left",padx=7)
        ttk.Button(b,text="Save character map",command=self.save).pack(side="left")
        ttk.Button(b,text="Close",command=self.destroy).pack(side="right")
        self.populate()

    def style_summary(self,row):
        d=row.get("style_counts",{}) or {}
        return f"normal {d.get('normal',0)} · shout {d.get('shouting',0)} · whisper {d.get('whispering',0)}"

    def populate(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        chars=sorted(self.rows.values(), key=lambda x: float(x.get("speaking_share",0)), reverse=True)
        for row in chars:
            cid=str(row.get("id",""))
            self.tree.insert("", "end", iid=cid, values=(
                row.get("display_name",cid), row.get("role",""), row.get("voice_class",""), row.get("age_group",""),
                row.get("line_count",0), f"{100*float(row.get('speaking_share',0)):.1f}%", self.style_summary(row), row.get("macos_voice","")
            ))
        if chars:
            cid=str(chars[0].get("id")); self.tree.selection_set(cid); self.on_select()

    def selected(self):
        sel=self.tree.selection(); return self.rows.get(sel[0]) if sel else None

    def on_select(self, _event=None):
        row=self.selected()
        if not row: return
        self.name.set(row.get("display_name",row.get("id",""))); self.role.set(row.get("role","minor")); self.voice_class.set(row.get("voice_class","neutral")); self.age.set(row.get("age_group","adult")); self.voice.set(row.get("macos_voice","")); self.rate.set(int(row.get("tts_rate",205))); self.pitch.set(float(row.get("pitch_semitones",0))); self.gain.set(float(row.get("voice_gain",1.0)))

    def apply_selected(self):
        row=self.selected()
        if not row: return
        row.update({"display_name":self.name.get().strip() or row.get("id"),"role":self.role.get(),"voice_class":self.voice_class.get(),"age_group":self.age.get(),"macos_voice":self.voice.get().strip(),"tts_rate":int(self.rate.get()),"pitch_semitones":float(self.pitch.get()),"voice_gain":float(self.gain.get()),"manual":True})
        self.populate()
        self.tree.selection_set(str(row.get("id")))

    def preview(self):
        voice=self.voice.get().strip(); text=f"This is {self.name.get() or 'the selected character'} speaking in English."
        cmd=["say","-r",str(int(self.rate.get()))]
        if voice: cmd += ["-v",voice]
        cmd += [text]
        try: subprocess.Popen(cmd)
        except Exception as e: messagebox.showerror("Preview",str(e),parent=self)

    def save(self):
        self.apply_selected()
        self.data["characters"]=list(self.rows.values())
        self.path.write_text(json.dumps(self.data,ensure_ascii=False,indent=2),encoding="utf-8")
        # Push manual voice choices into the series database so the same character can
        # keep the same English voice across separate episode files.
        series_id=str(self.data.get("series_id","")).strip()
        if series_id:
            safe=re.sub(r"[^A-Za-z0-9._-]+","_",series_id).strip("._-") or "series"
            db=self.path.parent/".anime_dubber_series"/f"{safe}.json"
            if db.exists():
                try:
                    d=json.loads(db.read_text(encoding="utf-8")); by={str(x.get("id")):x for x in d.get("characters",[]) if isinstance(x,dict)}
                    fields=("display_name","role","voice_class","age_group","macos_voice","tts_rate","pitch_semitones","voice_gain","notes","manual")
                    for row in self.rows.values():
                        old=by.get(str(row.get("id")))
                        if old is not None and row.get("manual"):
                            for k in fields:
                                if k in row: old[k]=row[k]
                    d["characters"]=list(by.values()); db.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
                except Exception:
                    pass
        messagebox.showinfo("Saved",f"Saved character overrides to:\n{self.path}",parent=self)


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        configure_styles(root)
        root.title("AnimeDubber")
        root.geometry("1120x860")
        root.minsize(940, 720)
        root.configure(bg=APP_BG)

        self.q: queue.Queue[str] = queue.Queue()
        self.runner = None
        self.worker = None
        self.last_character_map = None

        self.source = tk.StringVar(value="https://youtu.be/WH9x3hYwPj0")
        self.output = tk.StringVar(value=str(Path.home() / "Movies" / "AnimeDubber"))
        self.series_id = tk.StringVar(value="10000-years-cultivation")
        self.mode = tk.StringVar(value="dub")
        self.translation = tk.StringVar(value="llm")
        self.tts = tk.StringVar(value="macos")
        self.voice = tk.StringVar(value="")
        self.rate = tk.IntVar(value=210)
        self.resume = tk.BooleanVar(value=True)
        self.ducking = tk.BooleanVar(value=False)
        self.multi = tk.BooleanVar(value=True)
        self.bg_volume = tk.DoubleVar(value=1.0)
        self.dub_volume = tk.DoubleVar(value=1.15)
        self.max_speakers = tk.IntVar(value=12)
        self.speaker_threshold = tk.DoubleVar(value=0.0)
        self.speaker_backend = tk.StringVar(value="auto")
        self.eleven_key = tk.StringVar(value="")
        self.eleven_voice = tk.StringVar(value="JBFqnCBsd6RMkjVDRZzb")
        self.context = tk.StringVar(
            value="Chinese xianxia/xuanhuan cultivation animation. Keep names, sects, realms, system terms, and cultivation terminology consistent."
        )
        self.voices = list_macos_voices()

        shell = tk.Frame(root, bg=APP_BG)
        shell.pack(fill="both", expand=True, padx=24, pady=20)

        header = tk.Frame(shell, bg=APP_BG)
        header.pack(fill="x", pady=(0, 14))
        title_box = tk.Frame(header, bg=APP_BG)
        title_box.pack(side="left", fill="x", expand=True)
        tk.Label(
            title_box, text="AnimeDubber", bg=APP_BG, fg=TEXT_PRIMARY,
            font=("Helvetica Neue", 28, "bold")
        ).pack(anchor="w")
        tk.Label(
            title_box,
            text="Local, speaker-aware English dubbing for Apple silicon.",
            bg=APP_BG, fg=TEXT_SECONDARY, font=("Helvetica Neue", 12)
        ).pack(anchor="w", pady=(2, 0))
        ttk.Button(
            header, text="System Check", style="Secondary.TButton", command=self.show_doctor
        ).pack(side="right", anchor="n", pady=4)

        project_card = tk.Frame(
            shell, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1,
            padx=18, pady=16
        )
        project_card.pack(fill="x", pady=(0, 12))
        tk.Label(
            project_card, text="Project", bg=CARD_BG, fg=TEXT_PRIMARY,
            font=("Helvetica Neue", 15, "bold")
        ).pack(anchor="w", pady=(0, 10))

        def project_row(label, variable, browse=None, hint=""):
            row = tk.Frame(project_card, bg=CARD_BG)
            row.pack(fill="x", pady=5)
            left = tk.Frame(row, bg=CARD_BG, width=165)
            left.pack(side="left", fill="y")
            left.pack_propagate(False)
            tk.Label(
                left, text=label, bg=CARD_BG, fg=TEXT_PRIMARY,
                font=("Helvetica Neue", 11, "bold")
            ).pack(anchor="w", pady=7)
            ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
            if browse:
                ttk.Button(row, text="Choose…", style="Secondary.TButton", command=browse).pack(
                    side="left", padx=(8, 0)
                )
            if hint:
                tk.Label(
                    row, text=hint, bg=CARD_BG, fg=TEXT_SECONDARY,
                    font=("Helvetica Neue", 10)
                ).pack(side="left", padx=(10, 0))
            return row

        project_row("Source", self.source, self.browse_video)
        project_row("Output folder", self.output, self.browse_output)
        project_row("Series ID", self.series_id, hint="Reuses character voices across episodes")

        settings_card = tk.Frame(
            shell, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1,
            padx=14, pady=12
        )
        settings_card.pack(fill="x", pady=(0, 12))
        self.notebook = ttk.Notebook(settings_card)
        self.notebook.pack(fill="x")

        project_tab = ttk.Frame(self.notebook, padding=(16, 14))
        voice_tab = ttk.Frame(self.notebook, padding=(16, 14))
        audio_tab = ttk.Frame(self.notebook, padding=(16, 14))
        self.notebook.add(project_tab, text="General")
        self.notebook.add(voice_tab, text="Voices")
        self.notebook.add(audio_tab, text="Audio")

        def setting_row(parent, label):
            row = ttk.Frame(parent)
            row.pack(fill="x", pady=6)
            ttk.Label(row, text=label, style="Field.TLabel", width=19).pack(
                side="left", anchor="w"
            )
            return row

        r = setting_row(project_tab, "Output")
        ttk.Radiobutton(r, text="English dub + subtitles", value="dub", variable=self.mode).pack(side="left")
        ttk.Radiobutton(r, text="Subtitles only", value="subtitles", variable=self.mode).pack(
            side="left", padx=(16, 0)
        )

        r = setting_row(project_tab, "Translation")
        ttk.Radiobutton(r, text="Local LLM", value="llm", variable=self.translation).pack(side="left")
        ttk.Radiobutton(r, text="Whisper direct", value="whisper", variable=self.translation).pack(
            side="left", padx=(16, 0)
        )
        ttk.Label(r, text="Local LLM is recommended", style="Hint.TLabel").pack(side="left", padx=(12, 0))

        r = setting_row(project_tab, "Characters")
        ttk.Checkbutton(
            r, text="Detect speakers and assign separate voices", variable=self.multi
        ).pack(side="left")

        r = setting_row(project_tab, "Speaker analysis")
        ttk.Label(r, text="Backend").pack(side="left")
        ttk.Combobox(
            r, textvariable=self.speaker_backend, values=["auto", "ecapa", "acoustic"],
            state="readonly", width=10
        ).pack(side="left", padx=(5, 14))
        ttk.Label(r, text="Max speakers").pack(side="left")
        ttk.Spinbox(r, from_=2, to=30, width=6, textvariable=self.max_speakers).pack(
            side="left", padx=(5, 14)
        )
        ttk.Label(r, text="Threshold").pack(side="left")
        ttk.Spinbox(
            r, from_=0, to=.99, increment=.02, width=7, textvariable=self.speaker_threshold
        ).pack(side="left", padx=(5, 0))
        ttk.Label(r, text="0 = automatic", style="Hint.TLabel").pack(side="left", padx=(8, 0))

        r = setting_row(project_tab, "Series context")
        ttk.Entry(r, textvariable=self.context).pack(side="left", fill="x", expand=True)

        r = setting_row(voice_tab, "Provider")
        ttk.Radiobutton(
            r, text="macOS local", value="macos", variable=self.tts, command=self.refresh_visibility
        ).pack(side="left")
        ttk.Radiobutton(
            r, text="ElevenLabs", value="elevenlabs", variable=self.tts, command=self.refresh_visibility
        ).pack(side="left", padx=(16, 0))

        self.tts_options = ttk.Frame(voice_tab)
        self.tts_options.pack(fill="x", pady=(8, 0))

        self.local_frame = ttk.Frame(self.tts_options)
        local_row = setting_row(self.local_frame, "Fallback voice")
        ttk.Combobox(
            local_row, textvariable=self.voice, values=[""] + self.voices, state="normal"
        ).pack(side="left", fill="x", expand=True)
        ttk.Label(local_row, text="Rate").pack(side="left", padx=(14, 5))
        ttk.Spinbox(
            local_row, from_=120, to=350, increment=5, width=7, textvariable=self.rate
        ).pack(side="left")

        self.el_frame = ttk.Frame(self.tts_options)
        r = setting_row(self.el_frame, "API key")
        ttk.Entry(r, textvariable=self.eleven_key, show="•").pack(side="left", fill="x", expand=True)
        r = setting_row(self.el_frame, "Default voice ID")
        ttk.Entry(r, textvariable=self.eleven_voice).pack(side="left", fill="x", expand=True)
        ttk.Label(
            self.el_frame,
            text="Per-character ElevenLabs voice IDs can still be edited in Character Voices.",
            style="Hint.TLabel"
        ).pack(anchor="w", padx=(150, 0), pady=(4, 0))

        r = setting_row(audio_tab, "Mix")
        ttk.Checkbutton(
            r, text="Duck background under English dialogue", variable=self.ducking
        ).pack(side="left")
        ttk.Checkbutton(r, text="Resume cached work", variable=self.resume).pack(
            side="left", padx=(18, 0)
        )

        r = setting_row(audio_tab, "Music / SFX")
        ttk.Spinbox(
            r, from_=.2, to=2, increment=.05, width=8, textvariable=self.bg_volume
        ).pack(side="left")
        ttk.Label(r, text="English voice", style="Field.TLabel").pack(side="left", padx=(24, 8))
        ttk.Spinbox(
            r, from_=.2, to=2, increment=.05, width=8, textvariable=self.dub_volume
        ).pack(side="left")
        ttk.Label(
            audio_tab,
            text="The original soundtrack is preserved outside dialogue regions; Demucs is used only around source speech.",
            style="Hint.TLabel"
        ).pack(anchor="w", pady=(8, 0))

        action_row = ttk.Frame(shell)
        action_row.pack(fill="x", pady=(0, 12))
        self.start_btn = ttk.Button(
            action_row, text="Generate Dub", style="Accent.TButton", command=self.start
        )
        self.start_btn.pack(side="left")
        self.analyze_btn = ttk.Button(
            action_row, text="Analyze Characters", style="Secondary.TButton", command=self.analyze
        )
        self.analyze_btn.pack(side="left", padx=(8, 0))
        ttk.Button(
            action_row, text="Character Voices", style="Secondary.TButton", command=self.open_manager
        ).pack(side="left", padx=(8, 0))
        self.stop_btn = ttk.Button(
            action_row, text="Stop", style="Danger.TButton", command=self.stop, state="disabled"
        )
        self.stop_btn.pack(side="right")

        status_card = tk.Frame(
            shell, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1,
            padx=16, pady=12
        )
        status_card.pack(fill="x", pady=(0, 12))
        self.progress_text = tk.StringVar(value="")
        self.status = tk.StringVar(value="Ready")
        status_top = tk.Frame(status_card, bg=CARD_BG)
        status_top.pack(fill="x", pady=(0, 7))
        tk.Label(
            status_top, textvariable=self.status, bg=CARD_BG, fg=TEXT_PRIMARY,
            font=("Helvetica Neue", 11, "bold"), anchor="w"
        ).pack(side="left", fill="x", expand=True)
        tk.Label(
            status_top, textvariable=self.progress_text, bg=CARD_BG, fg=TEXT_SECONDARY,
            font=("Helvetica Neue", 10), anchor="e"
        ).pack(side="right")
        self.pb = ttk.Progressbar(status_card, mode="indeterminate", maximum=100)
        self.pb.pack(fill="x")

        log_card = tk.Frame(
            shell, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1,
            padx=0, pady=0
        )
        log_card.pack(fill="both", expand=True)
        log_header = tk.Frame(log_card, bg=CARD_BG)
        log_header.pack(fill="x", padx=14, pady=(11, 8))
        tk.Label(
            log_header, text="Activity", bg=CARD_BG, fg=TEXT_PRIMARY,
            font=("Helvetica Neue", 13, "bold")
        ).pack(side="left")
        ttk.Button(
            log_header, text="Clear", style="Secondary.TButton", command=self.clear_log
        ).pack(side="right")

        log_body = tk.Frame(log_card, bg=LOG_BG)
        log_body.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(log_body, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        self.log = tk.Text(
            log_body,
            height=11,
            wrap="word",
            bg=LOG_BG,
            fg=LOG_FG,
            insertbackground=LOG_FG,
            selectbackground="#3A3A3C",
            relief="flat",
            borderwidth=0,
            padx=14,
            pady=12,
            font=("Menlo", 10),
            spacing1=1,
            spacing3=2,
            yscrollcommand=scrollbar.set,
        )
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=self.log.yview)
        self.log.tag_configure("error", foreground="#FF6961")
        self.log.tag_configure("muted", foreground="#A1A1A6")
        self.log.configure(state="disabled")

        self.refresh_visibility()
        root.after(120, self.poll)

    def browse_video(self):
        p=filedialog.askopenfilename(filetypes=[("Video files","*.mp4 *.mkv *.mov *.webm *.m4v"),("All files","*")]);
        if p:self.source.set(p)
    def browse_output(self):
        p=filedialog.askdirectory(initialdir=self.output.get());
        if p:self.output.set(p)
    def refresh_visibility(self):
        self.local_frame.pack_forget(); self.el_frame.pack_forget(); (self.el_frame if self.tts.get()=="elevenlabs" else self.local_frame).pack(fill="x")
    def emit(self,msg): self.q.put(msg)

    def _set_stage_spinner(self):
        if str(self.pb.cget("mode")) != "indeterminate":
            self.pb.stop()
            self.pb.configure(mode="indeterminate", maximum=100)
            self.pb["value"] = 0
            self.pb.start(10)
        self.progress_text.set("")

    def _handle_download_progress(self,msg):
        parts=msg.split("|")
        try: pct=float(parts[1])
        except Exception: pct=0.0
        speed=parts[2] if len(parts)>2 else ""
        eta=parts[3] if len(parts)>3 else ""
        total=parts[4] if len(parts)>4 else ""
        attempt=parts[5] if len(parts)>5 else "1"
        attempts=parts[6] if len(parts)>6 else "1"

        self.pb.stop()
        self.pb.configure(mode="determinate",maximum=100)
        self.pb["value"]=pct

        details=[]
        if speed and speed not in {"Unknown","N/A","done"}: details.append(speed)
        if eta and eta not in {"Unknown","N/A","0","00:00"}: details.append(f"ETA {eta}")
        if total and total not in {"Unknown","N/A","complete"}: details.append(total)

        self.status.set(f"Downloading video — attempt {attempt}/{attempts}")
        label=f"{pct:5.1f}%"
        if details: label += "  ·  " + "  ·  ".join(details)
        self.progress_text.set(label)

    def clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _append_log(self, message):
        text = str(message).replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
        if not text:
            return
        self.log.configure(state="normal")
        tag = "error" if text.startswith("ERROR:") else None
        self.log.insert("end", text + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def poll(self):
        try:
            while True:
                msg=self.q.get_nowait()
                if msg.startswith("__DOWNLOAD_PROGRESS__|"):
                    self._handle_download_progress(msg)
                    continue
                if not msg.startswith("Downloading source video"):
                    self._set_stage_spinner()
                status_lines = [
                    x.strip()
                    for x in str(msg).replace("\r\n", "\n").replace("\r", "\n").split("\n")
                    if x.strip()
                ]
                clean_status = status_lines[-1] if status_lines else "Working…"
                self.status.set(clean_status)
                self._append_log(msg)
        except queue.Empty:
            pass
        self.root.after(120,self.poll)
    def show_doctor(self):
        ok,lines=doctor(); messagebox.showinfo("System check" if ok else "System check: action needed","\n".join(lines))

    def make_config(self):
        return Config(source=self.source.get().strip(),output_dir=Path(self.output.get()).expanduser(),mode=self.mode.get(),translation=self.translation.get(),tts_engine=self.tts.get(),voice=self.voice.get().strip(),tts_rate=int(self.rate.get()),context=self.context.get().strip(),resume=bool(self.resume.get()),ducking=bool(self.ducking.get()),background_volume=float(self.bg_volume.get()),dub_volume=float(self.dub_volume.get()),elevenlabs_api_key=self.eleven_key.get().strip(),elevenlabs_voice_id=self.eleven_voice.get().strip(),multi_character=bool(self.multi.get()),max_speakers=max(2,int(self.max_speakers.get())),speaker_threshold=max(0,float(self.speaker_threshold.get())),series_id=self.series_id.get().strip(),speaker_backend=self.speaker_backend.get())

    def validate(self,config,analysis=False):
        if not config.source: messagebox.showerror("Missing source","Paste a YouTube URL or choose a video."); return False
        if (not analysis) and config.tts_engine=="elevenlabs" and config.mode=="dub" and not config.elevenlabs_api_key: messagebox.showerror("Missing API key","Enter an ElevenLabs API key or choose macOS local/free TTS."); return False
        return True

    def _begin(self):
        self.start_btn.config(state="disabled"); self.analyze_btn.config(state="disabled"); self.stop_btn.config(state="normal")
        self.pb.configure(mode="indeterminate",maximum=100); self.pb["value"]=0; self.pb.start(10)
        self.progress_text.set(""); self.clear_log()
    def _end(self):
        self.pb.stop(); self.pb.configure(mode="determinate",maximum=100); self.pb["value"]=0
        self.progress_text.set("")
        self.start_btn.config(state="normal"); self.analyze_btn.config(state="normal"); self.stop_btn.config(state="disabled")

    def config_or_error(self):
        try:
            return self.make_config()
        except Exception as e:
            messagebox.showerror("Invalid setting",f"Check the numeric settings.\n\n{e}")
            return None
    def start(self):
        cfg=self.config_or_error()
        if cfg is None or not self.validate(cfg): return
        self.runner=CommandRunner(self.emit); self._begin(); self.worker=threading.Thread(target=self._work,args=(cfg,False),daemon=True); self.worker.start()
    def analyze(self):
        cfg=self.config_or_error()
        if cfg is None or not self.validate(cfg,analysis=True): return
        cfg.mode="dub"; cfg.multi_character=True
        self.runner=CommandRunner(self.emit); self._begin(); self.worker=threading.Thread(target=self._work,args=(cfg,True),daemon=True); self.worker.start()
    def _work(self,cfg,analysis):
        try:
            results=analyze_only(cfg,self.emit,self.runner) if analysis else run_pipeline(cfg,self.emit,self.runner)
            if results.get("character_map"): self.last_character_map=Path(results["character_map"])
            final=results.get("character_map") if analysis else (results.get("dubbed_video") or results.get("english_srt"))
            self.root.after(0,lambda:messagebox.showinfo("Finished",f"Finished successfully.\n\n{final}"))
            if analysis and self.last_character_map: self.root.after(50,self.open_manager)
        except Exception as e:
            self.emit(f"ERROR: {e}"); self.root.after(0,lambda e=e:messagebox.showerror("Error",str(e)))
        finally:self.root.after(0,self._end)
    def expected_character_map(self):
        src=self.source.get().strip()
        if not src:return None
        return Path(self.output.get()).expanduser()/f"{source_key(src)}_characters.json"
    def open_manager(self):
        p=self.last_character_map or self.expected_character_map()
        if not p or not p.exists(): messagebox.showinfo("Character manager","Run “Analyze characters first” once so v3 can detect the cast."); return
        CharacterManager(self.root,p,self.voices)
    def stop(self):
        if self.runner:self.emit("Stopping…"); self.runner.cancel()


def main():
    root=tk.Tk(); App(root); root.mainloop()

if __name__=="__main__": main()
