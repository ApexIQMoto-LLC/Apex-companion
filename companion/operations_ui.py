"""APEX Operations desktop console; all actions are bounded and explicit."""
from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog,messagebox,scrolledtext

BG="#080F1A"; CARD="#102034"; EDGE="#244256"; INK="#E7F6FF"; MUTED="#92AABB"; CYAN="#68E7DC"; FONT="Segoe UI"


def open_operations_panel(app):
    win=tk.Toplevel(app.root)
    win.title("APEX / OPERATIONS ENGINE 0.8")
    win.configure(bg=BG)
    win.geometry(f"{min(940,max(710,app.root.winfo_screenwidth()-100))}x{min(740,max(555,app.root.winfo_screenheight()-95))}")
    win.minsize(700,540)
    panel=tk.Frame(win,bg=BG,padx=22,pady=16);panel.pack(fill="both",expand=True)
    tk.Label(panel,text="A P E X   /   A U T O N O M O U S   O P E R A T I O N S",font=(FONT,16,"bold"),
             fg=CYAN,bg=BG).pack(anchor="w")
    tk.Label(panel,text="Approved Unity project only  •  local audit  •  no spending, deployment, or arbitrary commands",
             font=(FONT,10),fg=MUTED,bg=BG).pack(anchor="w",pady=(0,14))

    def button(parent,label,fn):
        x=tk.Button(parent,text=label,command=fn,font=(FONT,9,"bold"),fg=INK,bg=CARD,
                    activebackground="#204560",activeforeground=INK,relief="flat",padx=10,pady=9)
        return x

    controls=tk.Frame(panel,bg=BG);controls.pack(fill="x",pady=(2,9))
    def enq(kind):
        task=app.enqueue_operation(kind)
        if task:messagebox.showinfo("Task queued",kind.replace('_',' ').title()+"\nJob ID: "+task,parent=win)
        refresh()
    button(controls,"SCAN UNITY LOGS",lambda:enq("unity_diagnostics")).pack(side="left",padx=(0,7))
    button(controls,"INSPECT GIT",lambda:enq("git_health")).pack(side="left",padx=(0,7))
    button(controls,"RUN EDIT MODE TESTS",lambda:enq("unity_editmode_tests")).pack(side="left",padx=(0,7))
    button(controls,"VIEW ACTIVE WINDOW",lambda:enq("desktop_inspect")).pack(side="left",padx=(0,7))

    pathbar=tk.Frame(panel,bg=BG);pathbar.pack(fill="x",pady=(2,8))
    selected=tk.StringVar(value="Unity executable: "+(Path(str(app.settings.get("unity_editor_path", ""))).name if app.settings.get("unity_editor_path") else "not configured"))
    tk.Label(pathbar,textvariable=selected,bg=BG,fg=MUTED,font=(FONT,10)).pack(side="left")
    def choose_editor():
        f=filedialog.askopenfilename(title="Select Unity.exe from your installed Unity Editor",filetypes=[("Unity executable","Unity.exe"),("Executable","*.exe")],parent=win)
        if not f:return
        from .operations_unity import safe_unity_executable
        try:exe=safe_unity_executable(f)
        except (ValueError,OSError) as ex:
            messagebox.showerror("Unity path",str(ex),parent=win);return
        if app._persist_setting("unity_editor_path",str(exe)):
            selected.set("Unity executable: "+exe.name)
            refresh()
    button(pathbar,"CHOOSE UNITY.EXE",choose_editor).pack(side="right")

    status=tk.StringVar(value="Initializing operations status...")
    tk.Label(panel,textvariable=status,bg=BG,fg=CYAN,font=(FONT,10,"bold"),anchor="w").pack(fill="x",pady=(0,8))

    toggles=tk.Frame(panel,bg=BG);toggles.pack(fill="x",pady=(0,10))
    def checkbox(parent,caption,key):
        v=tk.BooleanVar(value=bool(app.settings.get(key,False)))
        def changed():
            app._persist_setting(key,v.get());refresh()
        w=tk.Checkbutton(parent,text=caption,variable=v,command=changed,bg=BG,fg=INK,
                activebackground=BG,activeforeground=INK,selectcolor=CARD,font=(FONT,10))
        w.pack(side="left",padx=(0,16))
    checkbox(toggles,"Auto-queue away checks","ops_auto_away")
    checkbox(toggles,"Allow Unity EditMode tests","ops_allow_unity_tests")
    checkbox(toggles,"Enable private Telegram commands","ops_phone_commands")

    line=tk.Frame(panel,bg=BG);line.pack(fill="x",pady=(0,12))
    def pause():
        app.ops_queue.set_paused(not app.ops_queue.paused());refresh()
    button(line,"PAUSE / RESUME",pause).pack(side="left",padx=(0,8))
    def cancel():
        task=app.ops_queue.recent(1)
        if task and task[0]["status"]=="queued":app.ops_queue.cancel(task[0]["task_id"])
        refresh()
    button(line,"CANCEL LATEST QUEUED",cancel).pack(side="left",padx=(0,8))
    button(line,"REFRESH QUEUE",lambda:refresh()).pack(side="left",padx=(0,8))
    def open_project():
        if not app.approved_project:
            messagebox.showwarning("No project","Approve a Unity project first in Intelligence.",parent=win);return
        if not messagebox.askyesno("Open folder","Open approved project folder in Windows Explorer?",parent=win):return
        import os,sys
        if sys.platform=="win32":os.startfile(str(app.approved_project))
        else:messagebox.showinfo("Windows only","Open Folder works on Windows.",parent=win)
    button(line,"OPEN APPROVED PROJECT",open_project).pack(side="left",padx=(0,8))

    desktopbar=tk.Frame(panel,bg=BG);desktopbar.pack(fill="x",pady=(0,10))
    def choose_window(capture=False):
        if not app.personal.permitted("computer","local"):
            messagebox.showwarning("Permission","Enable COMPUTER / LOCAL in DATA PERMISSIONS first.",parent=win);return
        choices=app.ops_desktop.list_windows(permitted=True)
        if not choices:
            messagebox.showinfo("Windows","No visible windows found (or not running on Windows).",parent=win);return
        selector=tk.Toplevel(win);selector.title("APEX / Choose window to inspect")
        selector.geometry("690x400");selector.configure(bg=BG)
        tk.Label(selector,text="Select an open window. Nothing is clicked or sent to the AI.",bg=BG,fg=INK,font=(FONT,11)).pack(pady=10)
        items=tk.Listbox(selector,bg=CARD,fg=INK,selectbackground="#205470",font=(FONT,10),height=12)
        items.pack(fill="both",expand=True,padx=12,pady=8)
        for rec in choices:items.insert("end",rec["title"])
        def act():
            row=items.curselection()
            if not row:return
            choice=choices[row[0]]
            selector.destroy()
            try:
                if capture:
                    if not messagebox.askyesno("Local screenshot", "Save a PNG of this specific window locally? It may contain private information. APEX will NOT upload it or send it to your phone.",parent=win):return
                    result=app.ops_desktop.capture_window(choice["handle"],permitted=True,consented=True)
                    messagebox.showinfo("Saved locally",result["image"]+"\n\nReview or delete manually.",parent=win)
                    if (app.personal.permitted("computer","ai") and
                        messagebox.askyesno("Optional AI vision / API charge",
                            "Send THIS screenshot once to your OpenAI API model for visual analysis? "
                            "This can expose visible personal information and costs API credit. "
                            "It is never done automatically.",parent=win)):
                        app.analyze_screenshot(result["image"])
                else:
                    data=app.ops_desktop.inspect_window(choice["handle"],permitted=True,read_controls=True)
                    controls="\n".join((x.get("type","")+": "+x.get("text","")) for x in data.get("controls",[])[:25])
                    messagebox.showinfo("Window accessibility", "Window: "+str(data.get("window_title",""))+"\n\n"+controls[:1700]+"\n\nNo UI actions performed.",parent=win)
            except (PermissionError,OSError,ValueError,RuntimeError) as e:
                messagebox.showerror("Inspection",str(e)[:240],parent=win)
        button(selector,"INSPECT SELECTION" if not capture else "CAPTURE LOCALLY",act).pack(pady=8)
    button(desktopbar,"CHOOSE WINDOW / INSPECT UIA",lambda:choose_window(False)).pack(side="left",padx=(0,8))
    button(desktopbar,"LOCAL WINDOW SCREENSHOT",lambda:choose_window(True)).pack(side="left",padx=(0,8))
    def launch_unity():
        if not app.approved_project or not app.settings.get("unity_editor_path"):
            messagebox.showwarning("Unity","Choose an approved project and Unity.exe first.",parent=win);return
        if not messagebox.askyesno("Launch approved Unity", "Open this approved project using the configured Unity Editor? This starts the application, but does not modify source or build the game.",parent=win):return
        from .operations_unity import safe_unity_executable,approved_unity_root
        try:
            project=approved_unity_root(app.approved_project)
            exe=safe_unity_executable(app.settings["unity_editor_path"])
            import subprocess
            subprocess.Popen([str(exe),"-projectPath",str(project)],shell=False,
                             stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            messagebox.showinfo("Unity launched","Approved Unity Editor launch requested.",parent=win)
        except (OSError,RuntimeError,PermissionError,ValueError) as e:
            messagebox.showerror("Unity launch",str(e)[:220],parent=win)
    button(desktopbar,"OPEN UNITY PROJECT",launch_unity).pack(side="left",padx=(0,8))

    tk.Label(panel,text="PERSISTENT TASK HISTORY / EVIDENCE",font=(FONT,11,"bold"),bg=BG,fg=CYAN).pack(anchor="w")
    log=scrolledtext.ScrolledText(panel,height=15,font=("Consolas",10),bg=CARD,fg=INK,
                                   insertbackground=CYAN,wrap="word",relief="flat",state="disabled")
    log.pack(fill="both",expand=True,pady=(6,10))
    tk.Label(panel,text="Phone commands: /status  /queue  /scan  /git  /pause  /resume  /help",
             bg=BG,fg=MUTED,font=(FONT,10)).pack(anchor="w")
    tk.Label(panel,text="Phone cannot approve code edits, run tests, spend money, or enter shell commands."
             " UI inspection is local only; screenshots require separate consent.",
             bg=BG,fg=MUTED,font=(FONT,9),wraplength=860,justify="left").pack(anchor="w",pady=(5,0))

    def refresh():
        try:
            records=app.ops_queue.recent(28)
            counts=app.ops_queue.counts()
            pending=counts.get("queued",0)
            paused=app.ops_queue.paused()
            status.set(("PAUSED" if paused else "ACTIVE")+f"  /  {pending} queued  /  {counts.get('completed',0)} completed  /  {counts.get('failed',0)} failed"
                       +("  /  UNITY EDIT MODE READY" if app.settings.get("unity_editor_path") else "  /  CHOOSE UNITY.EXE FOR TESTS"))
            parts=[]
            for x in records:
                stamp=x["created_utc"][:19].replace("T"," ")
                parts.append(f"{stamp}  {x['kind'].upper():24} {x['status']:11} {x['origin']}  [{x['task_id'][:8]}]")
                outcome=x.get("result") or {}
                if outcome:
                    for k in ("state","reason","tests_verified","total","passed","failed","tracked_changes","sampled_errors","sampled_warnings"):
                        if k in outcome:parts.append(f"      {k}: {str(outcome[k])[:170]}")
                if x.get("error_code"):parts.append("      error: "+str(x["error_code"]))
            log.configure(state="normal");log.delete("1.0","end")
            log.insert("end","\n".join(parts) if parts else "No operations yet. Add a diagnostics task to begin.")
            log.configure(state="disabled")
        except (OSError,ValueError):
            status.set("Operations database is currently unavailable")
    refresh()
    return win
