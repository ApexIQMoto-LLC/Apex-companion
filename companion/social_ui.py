"""Business Studio account connections: consent is always owner-initiated."""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, simpledialog
import webbrowser

from .social_auth import (
    AuthError, PLATFORMS, WindowsVault, desktop_authorize, external_start,
    TIKTOK_CALLBACK,
)

BG, CARD, CARD2 = "#080F1A", "#101F30", "#13283B"
CYAN, INK, MUTED, AMBER = "#67E8DB", "#E8F5FC", "#91A8B9", "#F3BE6D"


def build_accounts_tab(tab, win):
    """Add provider connection rows; no network requests occur on opening."""
    title = tk.Label(tab, text="CONNECTED MARKETING ACCOUNTS", bg=BG, fg=CYAN,
                     font=("Segoe UI", 14, "bold"))
    title.pack(anchor="w", pady=(1, 4))
    intro = tk.Label(tab, text=(
        "Provider consent is separate from A.R.I.S. Cloud login. All tokens and app secrets stay "
        "in Windows Credential Manager. No publishing, ad spending, or outreach is enabled."),
        bg=BG, fg=MUTED, font=("Segoe UI", 9), wraplength=980, justify="left")
    intro.pack(anchor="w", pady=(0, 12))

    try:
        vault = WindowsVault()
        unavailable = None
    except AuthError as exc:
        vault, unavailable = None, str(exc)

    status = tk.StringVar(value=(
        "Available for owner-approved OAuth on Windows" if vault else
        "OAuth unavailable here: " + str(unavailable)))
    tk.Label(tab, textvariable=status, bg=BG, fg=AMBER, font=("Segoe UI", 9),
             wraplength=980, justify="left").pack(anchor="w", pady=(0, 8))

    canvas = tk.Canvas(tab, bg=BG, bd=0, highlightthickness=0)
    scrollbar = tk.Scrollbar(tab, command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    rows = tk.Frame(canvas, bg=BG)
    window_id = canvas.create_window((0, 0), window=rows, anchor="nw")
    rows.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))

    pending = {p: False for p in PLATFORMS}
    vars = {}
    widgets = {}

    def notice(msg):
        status.set(str(msg)[:250])

    def refresh():
        for p in PLATFORMS:
            vars[p].set("WORKING — browser consent" if pending[p] else (
                vault.status(p) if vault else "WINDOWS REQUIRED"))
            for control in widgets[p]:
                control.configure(state="disabled" if (pending[p] or not vault) else "normal")

    def field_dialog(platform, field):
        if not vault:
            return
        shared = " (shared by YouTube, GA4 and Google Ads)" if PLATFORMS[platform].vendor == "google" else ""
        labels = {
            "client_id": "Developer app/client ID" + shared,
            "client_secret": "Developer app secret" + shared,
            "redirect_uri": "Registered HTTPS redirect URI",
            "auth_url": "TikTok Business portal advertiser authorization URL",
            "developer_token": "Google Ads developer token",
        }
        hidden = field in ("client_secret", "developer_token")
        value = simpledialog.askstring(
            "APEX / Account Settings", f"{PLATFORMS[platform].label}\n{labels[field]}\n\n"
            "Stored in Windows Credential Manager; never paste credentials into chat.",
            parent=win, show="*" if hidden else None)
        if value is None:
            return
        try:
            if field == "client_id":
                vault.set_client_id(platform, value)
            elif field == "client_secret":
                vault.set_secret(platform, value)
            else:
                vault.save(platform, field, value)
            notice(f"Saved {labels[field]} securely for {PLATFORMS[platform].label}")
        except (AuthError, ValueError) as exc:
            messagebox.showerror("Connection configuration", str(exc), parent=win)
        refresh()

    def connect(platform):
        if not vault or pending[platform]:
            return
        spec = PLATFORMS[platform]
        if not messagebox.askyesno("Authorize read-only marketing access",
            f"Connect {spec.label}?\n\nRequested permissions:\n" +
            ("\n".join(spec.scope) if spec.scope else "TikTok Business portal-selected reporting permissions") +
            ("\n\nNOTE: Google Ads OAuth uses a broad adwords scope. "
             "APEX implements reporting only; the provider token is not intrinsically read-only." if platform == "google_ads" else "") +
            "\n\nYou will sign in directly with the provider. No account passwords are entered in APEX.",
            parent=win):
            return
        try:
            if spec.mode == "external_https":
                flow, url = external_start(platform, vault)
                if not webbrowser.open(url):
                    raise AuthError("Could not open your browser")
                messagebox.showinfo("HTTPS callback required",
                    "Complete provider consent. The registered HTTPS callback must display its full "
                    "redirect URL. Copy that URL and paste it into APEX. This one-time code is "
                    "sensitive: never send it in chat or screenshots. A first-party secured "
                    "callback relay is preferable for production use.", parent=win)
                returned = simpledialog.askstring("Complete account connection",
                    "Paste the FULL redirected HTTPS URL from the browser address bar:\n"
                    "(includes code and state; processed locally and not logged)", parent=win)
                if not returned:
                    notice("Authorization cancelled")
                    return
                fn = lambda: flow.complete(returned.strip())
            else:
                fn = lambda: desktop_authorize(platform, vault)
        except (AuthError, ValueError) as exc:
            messagebox.showerror("Connection", str(exc), parent=win)
            return
        pending[platform] = True
        refresh()
        notice(f"Authorization in progress: {spec.label}")

        def run():
            try:
                result = fn()
                response = (True, f"Connected {spec.label}; permissions: {result['scopes']}")
            except (AuthError, ValueError, OSError) as exc:
                response = (False, str(exc))
            except Exception:
                response = (False, "Authorization failed; see provider setup guide")

            def show():
                pending[platform] = False
                refresh()
                notice(response[1])
                (messagebox.showinfo if response[0] else messagebox.showerror)(
                    "APEX account connection", response[1], parent=win)
            try:
                win.after(0, show)
            except RuntimeError:
                return
        threading.Thread(target=run, daemon=True, name=f"APEX-OAuth-{platform}").start()

    def disconnect(platform):
        if not vault:
            return
        if messagebox.askyesno("Disconnect", "Forget local access/refresh tokens for "
                               f"{PLATFORMS[platform].label}?\n\n"
                               "This does NOT revoke provider authorization. Revoke it in the "
                               "provider account settings if access must be removed.", parent=win):
            vault.disconnect(platform)
            refresh()
            notice(f"Forgot local connection for {PLATFORMS[platform].label}")

    def action(parent, text, fn):
        ctl = tk.Button(parent, text=text, command=fn, bg=CARD2, fg=INK,
                        activebackground=CYAN, activeforeground=BG,
                        font=("Segoe UI", 8, "bold"), padx=8, pady=5,
                        relief="flat", cursor="hand2", borderwidth=0)
        ctl.pack(side="left", padx=(0, 5))
        return ctl

    for platform, spec in PLATFORMS.items():
        row = tk.Frame(rows, bg=CARD, padx=12, pady=10, highlightbackground="#233B50", highlightthickness=1)
        row.pack(fill="x", padx=(0, 10), pady=(0, 8))
        top = tk.Frame(row, bg=CARD)
        top.pack(fill="x")
        tk.Label(top, text=spec.label, bg=CARD, fg=CYAN, font=("Segoe UI", 10, "bold")).pack(side="left")
        sv = tk.StringVar(); vars[platform] = sv
        tk.Label(top, textvariable=sv, bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(side="right")
        hint = "Google OAuth Desktop client" if spec.vendor == "google" else (
            "Register http://127.0.0.1:8769/callback in TikTok Login Kit Desktop" if platform == "tiktok" else
            "Requires a registered first-party HTTPS callback and provider app approval")
        tk.Label(row, text=hint, bg=CARD, fg=MUTED, font=("Segoe UI", 8),
                 wraplength=940, justify="left").pack(anchor="w", pady=(3, 7))
        bar = tk.Frame(row, bg=CARD); bar.pack(fill="x")
        ctrls = []
        ctrls.append(action(bar, "APP ID", lambda p=platform: field_dialog(p, "client_id")))
        if spec.needs_secret or spec.vendor == "google":
            ctrls.append(action(bar, "APP SECRET", lambda p=platform: field_dialog(p, "client_secret")))
        if spec.mode == "external_https":
            ctrls.append(action(bar, "HTTPS CALLBACK", lambda p=platform: field_dialog(p, "redirect_uri")))
        if platform == "tiktok_ads":
            ctrls.append(action(bar, "AUTH URL", lambda p=platform: field_dialog(p, "auth_url")))
        if platform == "google_ads":
            ctrls.append(action(bar, "DEV TOKEN", lambda p=platform: field_dialog(p, "developer_token")))
        ctrls.append(action(bar, "CONNECT", lambda p=platform: connect(p)))
        ctrls.append(action(bar, "FORGET TOKEN", lambda p=platform: disconnect(p)))
        ctrls.append(action(bar, "DEVELOPER PORTAL", lambda u=spec.portal: webbrowser.open(u)))
        widgets[platform] = ctrls
    refresh()
