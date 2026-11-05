# APEX v0.9 — Marketing Account Authorization

**Scope:** Seven provider connection profiles, owner-driven OAuth, credential storage and local connection status. **This release does not yet schedule social analytics imports or publish content.** Business Studio still supports CSV imports, campaign tracking, content drafts and creator tracking.

## Start here

1. Install the APEX update, start the desktop app and open **BUSINESS STUDIO > ACCOUNTS**.
2. Each provider has **APP ID**, **APP SECRET** where required, **HTTPS CALLBACK** if required, **CONNECT**, **FORGET TOKEN**, and **DEVELOPER PORTAL** controls. Google services share a single Google Desktop OAuth client but receive separate authorizations/tokens.
3. Create the provider application in *your* developer account, enable required APIs/permissions, and complete any platform review and account verification.
4. Save the client ID and, where needed, client secret **inside the APEX Accounts screen**. The values are kept in Windows Credential Manager; they do not belong in chat, screenshots, `.env`, `config.json`, or source code.
5. Click **CONNECT** and complete the account-provider consent in your browser. APEX never needs or stores your social media passwords.
6. Check the connection status. A connected token means the provider supplied credentials; it does **not** establish that advanced analytics scopes, app review, ad-account access or daily sync is ready. Do not confuse authorization with data ingestion.

Do not send full redirect URLs, token responses, app secrets or authorization codes to ChatGPT, Telegram or a support ticket.

## 1. YouTube and YouTube Analytics — best starting point

- In [Google Cloud Console](https://console.cloud.google.com/apis/credentials), create/select your Google Cloud project; configure the OAuth consent screen and authorized test user if testing.
- Enable **YouTube Data API v3** and **YouTube Analytics API**.
- Create an **OAuth client ID, application type Desktop app**. Copy the client ID into APEX under YouTube > APP ID. APEX can also store the generated desktop client secret if supplied.
- APEX opens a local `http://127.0.0.1:<dynamic>/callback` receiver and uses PKCE with a random state. Desktop loopback redirect URIs are supported by Google; unlike a web OAuth client, the Desktop type does not require pre-registering every local port.
- APEX requests `youtube.readonly` and `yt-analytics.readonly`.
- Connect, choose your YouTube channel Google identity, and consent. Your channel must be associated with the account you authorize.
- Documentation: [Google installed-app OAuth](https://developers.google.com/youtube/reporting/guides/authorization/installed-apps).

## 2. Google Analytics 4 (GA4)

- Enable **Google Analytics Data API** (and optionally Admin API for property discovery) in the same Google Cloud project.
- Grant the authorizing Google account appropriate viewer access to your **GA4 property**.
- In Business Studio > Accounts > GA4, the Google Desktop client ID is shared with YouTube; click **CONNECT** separately to grant `analytics.readonly`.
- OAuth authorization does not auto-create GA4 tracking or goals. Install the GA4 tag on the ApexIQ website, configure the lead/conversion events, and identify the property ID before analytics can be imported.
- Documentation: [GA4 Data API](https://developers.google.com/analytics/devguides/reporting/data/v1).

## 3. TikTok organic account

- Create a developer app at [TikTok for Developers](https://developers.tiktok.com/), add Login Kit **Desktop** and, for video access, Display API and its permissions.
- Register the **exact** redirect URI `http://127.0.0.1:8769/callback` in TikTok's developer portal. APEX uses a fixed port for TikTok desktop login; ensure no other program owns port 8769.
- Save **Client Key** under APP ID and **Client Secret** under APP SECRET.
- APEX requests `user.info.basic` and `video.list` with a per-session **hex SHA-256 PKCE** challenge, as required by TikTok's Desktop Login Kit. You must have both scopes approved for the app; if video.list is not enabled, its authorization may fail.
- This does not grant TikTok Accounts API or Business API insight capabilities; those require separate TikTok approval.
- Documentation: [TikTok Desktop Login](https://developers.tiktok.com/docs/en/login-kit-desktop).

## 4. Instagram Insights

- Convert the account to **Business or Creator** status, then create a Meta developer app that supports **Instagram API with Instagram Login**.
- Request the appropriate `instagram_business_basic` and `instagram_business_manage_insights` permissions. Advanced access and Meta review may be required before connecting accounts beyond app roles.
- Instagram authorization uses a **pre-registered HTTPS callback**. It **cannot** directly redirect to APEX's arbitrary local loopback URL using the same supported desktop pattern as Google/TikTok.
- Configure a secure callback route **on a domain you control** (e.g. `https://apexiqmoto.com/oauth/companion/callback`) and register the exact URI in your Meta developer console. APEX provides an owner-only temporary **paste redirected HTTPS URL** completion path. Never paste this URL in chat, and ensure server/CDN logs redact the `code` parameter. Prefer a hardened first-party callback relay for daily production use.
- Save the Instagram app ID, app secret, and HTTPS callback in APEX, then click Connect, authorize in browser and paste the **full callback URL locally**. APEX validates one-time state, exchanges the code and attempts the official Instagram long-lived token exchange.
- Instagram Login does **not** authorize Meta advertising accounts. Connect Meta Ads separately.
- Documentation: [Instagram platform](https://developers.facebook.com/docs/instagram-platform/).

## 5. Meta Ads

- In [Meta for Developers](https://developers.facebook.com/), configure an appropriate Facebook Login for Business app and business permissions.
- APEX requests **`ads_read` only** through the account consent flow; avoid requesting `ads_management` if you only need reporting. Ads accounts must be visible to the connected identity, and production use may require Meta business verification/app review.
- Register a first-party **HTTPS redirect URI** on a domain you control. Store app ID, app secret and HTTPS callback in APEX. Approve in browser; paste the redirected URL **only inside APEX**.
- APEX currently stores the token for future read-only reporting; this release does not pull Meta ad reports or manipulate campaigns.
- See [Meta Marketing API](https://developers.facebook.com/docs/marketing-apis/).

## 6. TikTok Ads

- Create a **separate TikTok for Business developer application** at [TikTok API for Business](https://business-api.tiktok.com/portal/), then obtain appropriate advertising report permissions and approval.
- Use the advertiser authorization URL supplied by **that portal**, not the organic TikTok Login Kit URL. Store app ID, app secret, HTTPS callback, and portal AUTH URL in APEX.
- Authorize the advertiser, complete TikTok's verification prompt, then paste the full HTTPS callback URL locally. APEX validates state and exchanges the one-time `auth_code` using the Business API. The API's token lifecycle and advertiser access are distinct from organic TikTok.
- This stage is **configuration only**, pending live validation against your approved developer app. No ads are launched or modified.
- See [TikTok Business API authorization](https://business-api.tiktok.com/portal/).

## 7. Google Ads

- In Google Cloud, enable Google Ads API for the same project/client and obtain a **Google Ads developer token** from Google Ads API Center. The account must grant relevant access and the developer token must have an appropriate API access level.
- In Business Studio > Accounts > Google Ads, save the developer token with **DEV TOKEN**, and connect the Google OAuth Desktop app.
- Important: Google's available OAuth `adwords` scope is **not intrinsically read-only**. Although APEX intentionally contains no ad write, bidding, publishing or spending endpoints, the token may authorize wider access in third-party software. Only opt in if you accept that distinction.
- OAuth authorization without an approved developer token and accessible customer ID is insufficient for reports.
- See [Google Ads API authorization](https://developers.google.com/google-ads/api/rest/auth).

## Security and limitations

- All client secrets, refresh/access tokens, and optionally client IDs are kept in **Windows Credential Manager**, using the `keyring` library. The only state in source code is provider metadata and public OAuth endpoint URLs. No plaintext fallback exists on Linux/macOS.
- Owner-initiated consent. OAuth state and PKCE guard local flows; callbacks expire and are one-use. Local listener binds **127.0.0.1**, not the network interface.
- APEX uses separate OAuth scopes/tokens per provider. A single Google client ID can be reused for YouTube, GA4, and Ads, but the consent grants remain independent.
- Disconnecting removes local tokens only; for full revocation, remove the app's access through the provider's account security settings.
- The HTTPS callback paste option is for **single-owner initial setup**, not a scalable multi-user OAuth backend. When moving this to a broadly distributed product, implement a first-party HTTPS callback relay with one-time state proof, secure server-side exchange, and scrubbed access logs.
- Each platform controls eligibility, developer approval, available insight metrics, verification requirements and quotas. A green APEX authorization status is **not proof** that every requested metric is available or current.
- No auto-publishing, influencer messaging, unattended paid AI, ad spending or external database mutation is enabled by social authorization.
- Live account authentication and token refresh could not be verified in this build environment because no owner credentials or provider apps were supplied. Only offline flow/tests were run.
