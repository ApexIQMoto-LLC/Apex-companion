# Pair APEX to your phone (opt-in Telegram)

This feature sends a **one-way private daily summary** (and optional narrow C# fix alerts). It does not receive commands from your phone.

1. In the Telegram phone app, find **@BotFather**, use `/newbot` and complete its instructions. **Never paste the bot token into ChatGPT.**
2. Open a private chat with your new bot and send `/start`.
3. On the Windows PC running APEX, go to your installed Companion folder and run **`Pair_Phone.cmd`**. Enter the token when prompted (hidden), then select your own private chat ID if more than one appears.
4. The pairing program saves both values using Windows Credential Manager and never prints the token or writes it into `config.json`.
5. Restart APEX. Open **PHONE BRIEFING**, turn it on, save, and click **SEND TEST**.
6. Open **DATA PERMISSIONS** and enable `OPERATIONS / PHONE` to include owner-visible cloud and Steam summaries. Enable `PROJECTS / PHONE` separately if you want alerts about automatically fixed C# warnings. Do not enable PHONE for health/finance if you don't want such content on Telegram's infrastructure.

A daily digest is attempted after 9 AM local by default, while Companion is running and has network connectivity. It is sent **at most once per date** after success, and a failed delivery can be attempted again. The digest is not sent retroactively while your PC is off. Auto-fix notifications are independently de-duplicated.

The app cannot send a briefing without Telegram bot/network connectivity. If you do not want a third party to process message metadata, keep phone briefings OFF. To unpair, disable PHONE BRIEFING and delete the two entries under `APEXIQ Companion Telegram` in Windows Credential Manager using a Windows credential-management tool or your installed keyring library.
