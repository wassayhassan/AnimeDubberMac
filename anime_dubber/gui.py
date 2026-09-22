from __future__ import annotations

import json
import queue
import re
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

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
        self.title("Character / Voice Manager")
        self.geometry("1040x610")
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
        self.root=root; root.title("AI Anime English Dubber v3"); root.geometry("940x800"); root.minsize(820,700)
        self.q: queue.Queue[str]=queue.Queue(); self.runner=None; self.worker=None; self.last_character_map=None
        outer=ttk.Frame(root,padding=18); outer.pack(fill="both",expand=True)
        ttk.Label(outer,text="AI Anime English Dubber v3",font=("",21,"bold")).pack(anchor="w")
        ttk.Label(outer,text="Multi-character English dubbing with speaker-aware voices, shouting/whispering style, and preserved music/SFX.").pack(anchor="w",pady=(2,12))
        form=ttk.Frame(outer); form.pack(fill="x")

        self.source=tk.StringVar(value="https://youtu.be/WH9x3hYwPj0")
        self.output=tk.StringVar(value=str(Path.home()/"Movies"/"AnimeDubber"))
        self.series_id=tk.StringVar(value="10000-years-cultivation")
        self.mode=tk.StringVar(value="dub"); self.translation=tk.StringVar(value="llm"); self.tts=tk.StringVar(value="macos")
        self.voice=tk.StringVar(value=""); self.rate=tk.IntVar(value=210); self.resume=tk.BooleanVar(value=True); self.ducking=tk.BooleanVar(value=True); self.multi=tk.BooleanVar(value=True)
        self.bg_volume=tk.DoubleVar(value=1.0); self.dub_volume=tk.DoubleVar(value=1.15); self.max_speakers=tk.IntVar(value=12); self.speaker_threshold=tk.DoubleVar(value=0.0); self.speaker_backend=tk.StringVar(value="auto")
        self.eleven_key=tk.StringVar(value=""); self.eleven_voice=tk.StringVar(value="JBFqnCBsd6RMkjVDRZzb")
        self.context=tk.StringVar(value="Chinese xianxia/xuanhuan cultivation animation. Keep names, sects, realms, system terms, and cultivation terminology consistent.")
        self.voices=list_macos_voices()

        def row(label):
            r=ttk.Frame(form); r.pack(fill="x",pady=4); ttk.Label(r,text=label,width=20).pack(side="left",anchor="w"); return r
        r=row("YouTube / video"); ttk.Entry(r,textvariable=self.source).pack(side="left",fill="x",expand=True); ttk.Button(r,text="Browse…",command=self.browse_video).pack(side="left",padx=(7,0))
        r=row("Output folder"); ttk.Entry(r,textvariable=self.output).pack(side="left",fill="x",expand=True); ttk.Button(r,text="Browse…",command=self.browse_output).pack(side="left",padx=(7,0))
        r=row("Series ID"); ttk.Entry(r,textvariable=self.series_id).pack(side="left",fill="x",expand=True); ttk.Label(r,text="same ID = persistent character voices").pack(side="left",padx=8)
        r=row("Output mode"); ttk.Radiobutton(r,text="English dub + SRT",value="dub",variable=self.mode).pack(side="left"); ttk.Radiobutton(r,text="Subtitles only",value="subtitles",variable=self.mode).pack(side="left",padx=14)
        r=row("Translation"); ttk.Radiobutton(r,text="Local LLM (recommended)",value="llm",variable=self.translation).pack(side="left"); ttk.Radiobutton(r,text="Whisper direct",value="whisper",variable=self.translation).pack(side="left",padx=14)
        r=row("Character dubbing"); ttk.Checkbutton(r,text="Detect separate characters and assign voices",variable=self.multi).pack(side="left"); ttk.Label(r,text="male/female-style · child/adult/older · lead/side · shout/whisper").pack(side="left",padx=8)
        r=row("Speaker analysis"); ttk.Label(r,text="Backend").pack(side="left"); ttk.Combobox(r,textvariable=self.speaker_backend,values=["auto","ecapa","acoustic"],state="readonly",width=10).pack(side="left",padx=(4,10)); ttk.Label(r,text="Max").pack(side="left"); ttk.Spinbox(r,from_=2,to=30,width=6,textvariable=self.max_speakers).pack(side="left",padx=(4,12)); ttk.Label(r,text="Threshold (0=auto)").pack(side="left"); ttk.Spinbox(r,from_=0,to=.99,increment=.02,width=7,textvariable=self.speaker_threshold).pack(side="left",padx=4)
        r=row("TTS"); ttk.Radiobutton(r,text="macOS local/free",value="macos",variable=self.tts,command=self.refresh_visibility).pack(side="left"); ttk.Radiobutton(r,text="ElevenLabs",value="elevenlabs",variable=self.tts,command=self.refresh_visibility).pack(side="left",padx=14)

        self.tts_options=ttk.Frame(form); self.tts_options.pack(fill="x",pady=4)
        self.local_frame=ttk.Frame(self.tts_options); ttk.Label(self.local_frame,text="Fallback voice",width=20).pack(side="left"); ttk.Combobox(self.local_frame,textvariable=self.voice,values=[""]+self.voices,state="normal").pack(side="left",fill="x",expand=True); ttk.Label(self.local_frame,text="Rate").pack(side="left",padx=(10,4)); ttk.Spinbox(self.local_frame,from_=120,to=350,increment=5,width=7,textvariable=self.rate).pack(side="left")
        self.el_frame=ttk.Frame(self.tts_options); r1=ttk.Frame(self.el_frame); r1.pack(fill="x",pady=2); ttk.Label(r1,text="ElevenLabs API key",width=20).pack(side="left"); ttk.Entry(r1,textvariable=self.eleven_key,show="•").pack(side="left",fill="x",expand=True); r2=ttk.Frame(self.el_frame); r2.pack(fill="x",pady=2); ttk.Label(r2,text="Default voice ID",width=20).pack(side="left"); ttk.Entry(r2,textvariable=self.eleven_voice).pack(side="left",fill="x",expand=True); ttk.Label(self.el_frame,text="For true multi-voice ElevenLabs dubbing, set per-character voice IDs in the character-map JSON; local macOS mode auto-assigns multiple voices.",wraplength=820).pack(anchor="w",padx=(160,0))

        r=row("Series context"); ttk.Entry(r,textvariable=self.context).pack(side="left",fill="x",expand=True)
        r=row("Audio mix"); ttk.Checkbutton(r,text="Duck background during English dialogue",variable=self.ducking).pack(side="left"); ttk.Checkbutton(r,text="Resume cached work",variable=self.resume).pack(side="left",padx=14)
        r=row("Volumes"); ttk.Label(r,text="Music/SFX").pack(side="left"); ttk.Spinbox(r,from_=.2,to=2,increment=.05,width=7,textvariable=self.bg_volume).pack(side="left",padx=(4,12)); ttk.Label(r,text="English voice").pack(side="left"); ttk.Spinbox(r,from_=.2,to=2,increment=.05,width=7,textvariable=self.dub_volume).pack(side="left",padx=4)

        buttons=ttk.Frame(outer); buttons.pack(fill="x",pady=(14,8))
        self.start_btn=ttk.Button(buttons,text="Generate dub",command=self.start); self.start_btn.pack(side="left")
        self.analyze_btn=ttk.Button(buttons,text="Analyze characters first",command=self.analyze); self.analyze_btn.pack(side="left",padx=7)
        ttk.Button(buttons,text="Character manager",command=self.open_manager).pack(side="left")
        self.stop_btn=ttk.Button(buttons,text="Stop",command=self.stop,state="disabled"); self.stop_btn.pack(side="left",padx=7)
        ttk.Button(buttons,text="System check",command=self.show_doctor).pack(side="left")

        self.pb=ttk.Progressbar(outer,mode="indeterminate",maximum=100); self.pb.pack(fill="x")
        self.progress_text=tk.StringVar(value="")
        self.status=tk.StringVar(value="Ready")
        status_row=ttk.Frame(outer); status_row.pack(fill="x",pady=(6,4))
        ttk.Label(status_row,textvariable=self.status).pack(side="left",anchor="w")
        ttk.Label(status_row,textvariable=self.progress_text).pack(side="right",anchor="e")
        self.log=tk.Text(outer,height=15,wrap="word"); self.log.pack(fill="both",expand=True)
        self.refresh_visibility(); root.after(120,self.poll)

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

    def poll(self):
        try:
            while True:
                msg=self.q.get_nowait()
                if msg.startswith("__DOWNLOAD_PROGRESS__|"):
                    self._handle_download_progress(msg)
                    continue
                if not msg.startswith("Downloading source video"):
                    self._set_stage_spinner()
                self.status.set(msg)
                self.log.insert("end",msg+"\\n")
                self.log.see("end")
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
        self.progress_text.set(""); self.log.delete("1.0","end")
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
