import { Resend } from "resend"

const resend = new Resend(process.env.RESEND_API_KEY)
const mailDomain = process.env.EMAIL_DOMAIN

/*
|--------------------------------------------------------------------------
| BRAND EMAIL SYSTEM
|--------------------------------------------------------------------------
| One shared, email-safe (table + inline-styles) shell so every message
| looks like IntelShift: navy header with the white logo tile + "IntelShift
| AI" wordmark, brand colours, and a consistent footer. Outlook-friendly.
*/

const BRAND = {
    navy: "#1a1a2e",
    navy2: "#242442",
    coral: "#ff6b6b",
    coralDark: "#ee5a6f",
    danger: "#fc5c65",
    teal: "#4ecdc4",
    tealDark: "#3bb3ab",
    bg: "#f8f9fa",
    card: "#ffffff",
    text: "#2d3436",
    textLight: "#636e72",
    muted: "#8a8a99",
    border: "#e8eaed",
}

const FONT = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif"

const APP_URL = String(process.env.CLIENT_URL || "https://app.intelshift.ai").replace(/\/+$/, "")
const SITE_URL = "https://intelshift.ai"
// Public URL of the logo mark (the same logo.png the app uses). Override with
// EMAIL_LOGO_URL if it's hosted elsewhere. Alt text falls back to the wordmark
// when a client blocks images.
const LOGO_URL = process.env.EMAIL_LOGO_URL || `${SITE_URL}/logo.png`

/* Brand lockup: white round tile + logo mark + "IntelShift AI" (white text). */
const header = () => `
  <tr>
    <td style="background:${BRAND.navy};border-radius:16px 16px 0 0;padding:22px 28px;">
      <table role="presentation" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="vertical-align:middle;">
            <div style="width:44px;height:44px;border-radius:50%;background:#ffffff;text-align:center;mso-line-height-rule:exactly;line-height:44px;box-shadow:0 1px 3px rgba(0,0,0,0.12);">
              <img src="${LOGO_URL}" width="30" height="30" alt="IntelShift AI" style="width:30px;height:30px;vertical-align:middle;border:0;display:inline-block;" />
            </div>
          </td>
          <td style="vertical-align:middle;padding-left:11px;">
            <span style="font-family:${FONT};font-size:19px;font-weight:800;letter-spacing:-0.03em;color:#ffffff;">IntelShift AI</span>
          </td>
        </tr>
      </table>
    </td>
  </tr>`

const footer = () => `
  <tr>
    <td style="background:${BRAND.card};border-radius:0 0 16px 16px;border-top:1px solid ${BRAND.border};padding:22px 28px;text-align:center;">
      <p style="margin:0 0 10px;font-family:${FONT};font-size:12px;color:${BRAND.textLight};">
        <a href="${APP_URL}/dashboard" style="color:${BRAND.tealDark};text-decoration:none;font-weight:600;">Dashboard</a>
        &nbsp;·&nbsp;
        <a href="${APP_URL}/settings" style="color:${BRAND.tealDark};text-decoration:none;font-weight:600;">Settings</a>
        &nbsp;·&nbsp;
        <a href="mailto:support@intelshift.ai" style="color:${BRAND.tealDark};text-decoration:none;font-weight:600;">Support</a>
      </p>
      <p style="margin:0;font-family:${FONT};font-size:11px;color:${BRAND.muted};line-height:1.6;">
        © ${new Date().getFullYear()} IntelShift AI — AI competitor intelligence for ecommerce &amp; SaaS.<br/>
        You're receiving this because you have an IntelShift account.
      </p>
    </td>
  </tr>`

/* Bulletproof-ish button. color defaults to the coral primary. */
const button = (label, url, color = BRAND.coral) => `
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:26px 0 6px;">
    <tr>
      <td align="center" style="border-radius:10px;background:${color};">
        <a href="${url}" style="display:inline-block;padding:13px 28px;font-family:${FONT};font-size:14px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:10px;">${label}</a>
      </td>
    </tr>
  </table>`

/* Full branded document. */
const shell = ({ heading, preheader = "", bodyHtml, ctaHtml = "" }) => `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="color-scheme" content="light" />
  <title>IntelShift AI</title>
</head>
<body style="margin:0;padding:0;background:${BRAND.bg};">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">${preheader}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:${BRAND.bg};">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:600px;max-width:600px;">
          ${header()}
          <tr>
            <td style="background:${BRAND.card};padding:34px 28px 30px;">
              <h1 style="margin:0 0 14px;font-family:${FONT};font-size:22px;font-weight:800;letter-spacing:-0.02em;color:${BRAND.navy};">${heading}</h1>
              <div style="font-family:${FONT};font-size:15px;line-height:1.65;color:${BRAND.text};">${bodyHtml}</div>
              ${ctaHtml}
            </td>
          </tr>
          ${footer()}
        </table>
      </td>
    </tr>
  </table>
</body>
</html>`

const send = async ({ from = `IntelShift AI <support@${mailDomain}>`, to, subject, html }) => {
    try {
        const { error } = await resend.emails.send({ from, to, subject, html })
        if (error) console.error(`Email error [${subject}]:`, error)
    } catch (e) {
        console.error(`Email error [${subject}]:`, e.message)
    }
}

const fmt = (d) => (d ? new Date(d).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" }) : "")

/*
|--------------------------------------------------------------------------
| TEST
|--------------------------------------------------------------------------
*/
export const sendMail = (to) =>
    send({
        to,
        subject: "IntelShift test email",
        html: shell({
            heading: "It works! 🎉",
            preheader: "Your IntelShift email setup is working.",
            bodyHtml: `<p style="margin:0;">This is a test email from IntelShift AI. If you can see the branded header and this card, your email pipeline is set up correctly.</p>`,
        }),
    })

/*
|--------------------------------------------------------------------------
| PASSWORD RESET
|--------------------------------------------------------------------------
*/
export const sendPasswordResetMail = (to, link) =>
    send({
        to,
        subject: "Reset your IntelShift password",
        html: shell({
            heading: "Reset your password",
            preheader: "Use the button below to set a new password.",
            bodyHtml: `
              <p style="margin:0 0 12px;">We received a request to reset the password for your IntelShift account. Click the button below to choose a new one.</p>
              <p style="margin:0;color:${BRAND.textLight};font-size:13.5px;">This link expires in 1 hour. If you didn't request a reset, you can safely ignore this email — your password won't change.</p>`,
            ctaHtml: button("Reset password", link),
        }),
    })

/*
|--------------------------------------------------------------------------
| EMAIL VERIFICATION
|--------------------------------------------------------------------------
*/
export const sendEmailVerificationMail = (to, userName, link, expIn) =>
    send({
        to,
        subject: "Verify your email address",
        html: shell({
            heading: "Confirm your email",
            preheader: "One quick step to activate your IntelShift account.",
            bodyHtml: `
              <p style="margin:0 0 12px;">Hi ${userName || "there"}, welcome to IntelShift AI! Please confirm your email address to activate your account and start tracking competitors.</p>
              <p style="margin:0;color:${BRAND.textLight};font-size:13.5px;">This link expires in ${expIn || "24 hours"}. If you didn't create an account, you can ignore this email.</p>`,
            ctaHtml: button("Verify email", link, BRAND.teal),
        }),
    })

/*
|--------------------------------------------------------------------------
| WELCOME
|--------------------------------------------------------------------------
*/
export const sendWelcomeMail = async (to, userName) => {
    // Must return the promise: register() chains `.catch()` on the result.
    await send({
        from: `IntelShift AI <onboarding@${mailDomain}>`,
        to,
        subject: "Welcome to IntelShift AI 🎉",
        html: shell({
            heading: "Welcome aboard 🎉",
            preheader: "Your IntelShift workspace is ready.",
            bodyHtml: `
              <p style="margin:0 0 12px;">Hi ${userName || "there"}, we're thrilled to have you. Your account is set up and ready to go.</p>
              <p style="margin:0 0 12px;">IntelShift watches your competitors' sites for you — pricing moves, messaging shifts, and feature changes — then turns them into clear, AI-powered recommendations.</p>
              <p style="margin:0;">Jump in and add your first competitor to see it in action.</p>`,
            ctaHtml: button("Open your workspace", `${APP_URL}/dashboard`),
        }),
    })
}

/*
|--------------------------------------------------------------------------
| CHANGE ALERT DIGEST
|--------------------------------------------------------------------------
*/
export const sendChangeAlertMail = async (to, userName, workspaceName, items = [], dashboardUrl = "") => {
    const sev = (s) => {
        const v = String(s || "").toLowerCase()
        if (v === "critical") return BRAND.danger
        if (v === "high") return BRAND.coral
        if (v === "medium") return "#f7b731"
        return BRAND.muted
    }

    const rows = items.map((i) => `
        <tr>
          <td style="padding:14px 16px;border-bottom:1px solid ${BRAND.border};">
            <strong style="color:${BRAND.navy};font-size:14px;">${i.domain}</strong>
            <span style="display:inline-block;margin-left:8px;padding:2px 9px;border-radius:999px;background:${sev(i.severity)};color:#fff;font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.02em;">${i.severity || "change"}</span>
            <div style="color:${BRAND.textLight};font-size:13px;margin-top:5px;line-height:1.5;">${i.totalChanges} change${i.totalChanges === 1 ? "" : "s"} detected${i.topChanges && i.topChanges.length ? ` — ${i.topChanges.filter(Boolean).slice(0, 2).join("; ")}` : ""}</div>
          </td>
        </tr>`).join("")

    await send({
        from: `IntelShift AI <alerts@${mailDomain}>`,
        to,
        subject: `${items.length} competitor${items.length === 1 ? "" : "s"} changed — ${workspaceName || "your workspace"}`,
        html: shell({
            heading: "Competitor changes detected",
            preheader: `${items.length} competitor${items.length === 1 ? "" : "s"} changed in ${workspaceName || "your workspace"}.`,
            bodyHtml: `
              <p style="margin:0 0 18px;">Hi ${userName || "there"}, our latest monitoring scan found high-impact changes across your tracked competitors:</p>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid ${BRAND.border};border-radius:12px;overflow:hidden;">${rows}</table>`,
            ctaHtml: dashboardUrl ? button("View details", dashboardUrl) : "",
        }),
    })
}

/*
|--------------------------------------------------------------------------
| ACCOUNT LIFECYCLE
|--------------------------------------------------------------------------
*/
export const sendDeletionVerificationMail = (to, name, link) =>
    send({
        to,
        subject: "Confirm you want to close your IntelShift account",
        html: shell({
            heading: "Confirm account closure",
            preheader: "Nothing changes until you confirm.",
            bodyHtml: `
              <p style="margin:0 0 12px;">Hi ${name || "there"}, we received a request to close your IntelShift account.</p>
              <p style="margin:0;">To confirm, click the button below. Nothing changes until you do — this link expires in 3 days. If you didn't request this, you can safely ignore it.</p>`,
            ctaHtml: button("Confirm account closure", link, BRAND.danger),
        }),
    })

export const sendDeletionScheduledMail = (to, name, accessEndsAt, deleteAt) =>
    send({
        to,
        subject: "Your IntelShift account is scheduled to close",
        html: shell({
            heading: "Account closure scheduled",
            preheader: "Here's what happens next.",
            bodyHtml: `
              <p style="margin:0 0 12px;">Hi ${name || "there"}, your account closure is confirmed.</p>
              <ul style="margin:0 0 12px;padding-left:20px;color:${BRAND.text};">
                <li style="margin-bottom:6px;">You keep full access until <strong>${fmt(accessEndsAt)}</strong> (the end of your paid period).</li>
                <li>Your data is permanently deleted on <strong>${fmt(deleteAt)}</strong>.</li>
              </ul>
              <p style="margin:0;">Changed your mind? You can reactivate anytime before ${fmt(accessEndsAt)} from Settings → Workspace.</p>`,
            ctaHtml: button("Reactivate my account", `${APP_URL}/settings`, BRAND.teal),
        }),
    })

export const sendDeletionReminderMail = (to, name, accessEndsAt, kind) =>
    send({
        to,
        subject: `Reminder: your IntelShift account closes ${kind === "1d" ? "tomorrow" : "soon"}`,
        html: shell({
            heading: "Your account is closing soon",
            preheader: `Access ends on ${fmt(accessEndsAt)}.`,
            bodyHtml: `
              <p style="margin:0 0 12px;">Hi ${name || "there"}, a reminder that your account access ends on <strong>${fmt(accessEndsAt)}</strong>.</p>
              <p style="margin:0;">If you'd like to keep it, reactivate from Settings → Workspace before then.</p>`,
            ctaHtml: button("Keep my account", `${APP_URL}/settings`, BRAND.teal),
        }),
    })

export const sendAccountDeactivatedMail = (to, name, deleteAt) =>
    send({
        to,
        subject: "Your IntelShift account has been deactivated",
        html: shell({
            heading: "Account deactivated",
            preheader: "Your paid period has ended.",
            bodyHtml: `
              <p style="margin:0 0 12px;">Hi ${name || "there"}, your paid period has ended and your account is now deactivated.</p>
              <p style="margin:0;">Your data will be permanently deleted on <strong>${fmt(deleteAt)}</strong>. Until then, contact support if you'd like to restore it.</p>`,
        }),
    })

export const sendAccountDeletedMail = (to, name) =>
    send({
        to,
        subject: "Your IntelShift account has been deleted",
        html: shell({
            heading: "Account deleted",
            preheader: "Your data has been permanently removed.",
            bodyHtml: `
              <p style="margin:0 0 12px;">Hi ${name || "there"}, your IntelShift account and all associated data have been permanently deleted, as requested.</p>
              <p style="margin:0;">We're sorry to see you go — you're always welcome back.</p>`,
        }),
    })

export const sendReactivatedMail = (to, name) =>
    send({
        to,
        subject: "Welcome back — your IntelShift account is active",
        html: shell({
            heading: "Account reactivated",
            preheader: "Nothing was lost.",
            bodyHtml: `
              <p style="margin:0 0 12px;">Hi ${name || "there"}, your account closure has been cancelled and your account is active again. Nothing was lost.</p>`,
            ctaHtml: button("Back to dashboard", `${APP_URL}/dashboard`),
        }),
    })
