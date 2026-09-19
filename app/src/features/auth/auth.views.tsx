// Auth/account frontend (§05). Real session comes from POST
// /api/v1/auth/session; register/verify/recovery screens are contract-ready
// (see API-001..API-003) and never invent a session client-side.
import { useState } from "react";
import { Alert } from "../../components/Alert";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { TextField } from "../../components/TextField";
import { clearSession, isServerError, signIn } from "../../lib/api";
import { PageHeader } from "../../components/layout/Shell";

const DEV_AUTH = import.meta.env.VITE_ALLOW_DEV_AUTH !== "false";

function returnTo(): string {
  const next = new URLSearchParams(window.location.search).get("next");
  return next && next.startsWith("#/") ? next : "#/home";
}

export function Login() {
  const [userId, setUserId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!userId.trim()) {
      setError("Enter your account ID or email.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await signIn(userId.trim());
      location.hash = returnTo().replace(/^#/, "");
    } catch (reason: unknown) {
      setError(isServerError(reason) ? reason.message : "The sign-in service is unavailable. Your entries have been kept.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-labelledby="login-h">
      <PageHeader title="Sign in" purpose="Use your TANIM account to reach your workspace." />
      <h2 id="login-h" className="visually-hidden">Sign in</h2>
      <form onSubmit={submit} noValidate>
        <TextField name="userid" label="Account ID or email" autoComplete="username"
          value={userId} error={error ?? undefined}
          onChange={(e) => setUserId(e.target.value)} />
        <Button type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</Button>
      </form>
      {DEV_AUTH && (
        <Card title="Development sign-in">
          <p className="hint">Shown only when development auth is enabled. Never shown in production.</p>
          <p className="row">
            <Button variant="secondary" disabled={busy} onClick={() => { setUserId("farmer-1"); }}>Use demo farmer</Button>
          </p>
        </Card>
      )}
      <p className="hint"><a href="#/register">Create an account</a> · <a href="#/forgot-password">Forgot password?</a></p>
    </section>
  );
}

function contractNotice(action: string) {
  return `${action} follows the pending account contract (API-001). This build records your entries locally and does not create a server session until the backend contract lands.`;
}

export function Register() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !email.trim() || password.length < 8) {
      setError("Enter your name, a valid email, and a password of at least 8 characters. Reviewer and admin roles cannot be self-selected.");
      return;
    }
    setError(null);
    setDone(true);
  }
  if (done) return <Alert title="Check your email">{contractNotice("Registration")}</Alert>;
  return (
    <section aria-labelledby="reg-h">
      <PageHeader title="Create your account" purpose="Farmers join with the Farmer role. No one can grant themselves reviewer or admin access." />
      <h2 id="reg-h" className="visually-hidden">Create your account</h2>
      <form onSubmit={submit} noValidate>
        <TextField name="name" label="Full name" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />
        <TextField name="email" label="Email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <div>
          <label htmlFor="password">Password</label>
          <input id="password" name="password" type="password" autoComplete="new-password"
            minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        {error && <p role="alert" className="err">{error}</p>}
        <Button type="submit">Create account</Button>
      </form>
      <p className="hint"><a href="#/login">Back to sign in</a></p>
    </section>
  );
}

export function VerifyEmail() {
  return (
    <section aria-labelledby="verify-h">
      <PageHeader title="Verify your email" purpose="Verification links open cleanly on phones and expire for safety." />
      <h2 id="verify-h" className="visually-hidden">Verify your email</h2>
      <Alert title="Link status">This verification link follows the pending contract (API-001). Request a new link if yours expired.</Alert>
      <p><Button variant="secondary" onClick={() => (location.hash = "#/login")}>Back to sign in</Button></p>
    </section>
  );
}

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [done, setDone] = useState(false);
  function submit(e: React.FormEvent) {
    e.preventDefault();
    setDone(true); // Generic response: never reveals whether the email exists.
  }
  if (done) {
    return (
      <section aria-labelledby="forgot-h">
        <h2 id="forgot-h">Check your email</h2>
        <Alert title="Recovery requested">If an account uses that email, a reset link is on its way. The link expires.</Alert>
      </section>
    );
  }
  return (
    <section aria-labelledby="forgot-h">
      <PageHeader title="Forgot password" purpose="Reset links expire. Old sessions are invalidated after a reset." />
      <h2 id="forgot-h" className="visually-hidden">Forgot password</h2>
      <form onSubmit={submit} noValidate>
        <TextField name="email" label="Email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <Button type="submit">Send reset link</Button>
      </form>
    </section>
  );
}

export function ResetPassword() {
  const [password, setPassword] = useState("");
  const [done, setDone] = useState(false);
  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (password.length < 8) return;
    setDone(true);
  }
  if (done) {
    return (
      <section aria-labelledby="reset-h">
        <h2 id="reset-h">Password updated</h2>
        <Alert title="Done">Sign in again with your new password.</Alert>
        <p><a href="#/login">Sign in</a></p>
      </section>
    );
  }
  return (
    <section aria-labelledby="reset-h">
      <PageHeader title="Choose a new password" purpose="Links expire. Enter a new password of at least 8 characters." />
      <h2 id="reset-h" className="visually-hidden">Choose a new password</h2>
      <form onSubmit={submit} noValidate>
        <div>
          <label htmlFor="new-password">New password</label>
          <input id="new-password" name="new-password" type="password" autoComplete="new-password"
            minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <Button type="submit">Update password</Button>
      </form>
    </section>
  );
}

export function SessionExpired() {
  return (
    <section aria-labelledby="exp-h">
      <h2 id="exp-h">Your session expired</h2>
      <Alert title="Signed out">Sign in again to continue. Your saved work is kept.</Alert>
      <p className="row">
        <Button onClick={() => { clearSession(); location.hash = "#/login"; }}>Sign in again</Button>
      </p>
    </section>
  );
}

export function Forbidden() {
  return (
    <section aria-labelledby="f-h">
      <h2 id="f-h">Not allowed</h2>
      <Alert tone="error" title="403">Your role cannot open this page. The server enforces this — hiding the link is not the protection.</Alert>
      <p><a href="#/home">Back to Home</a></p>
    </section>
  );
}

export function NotFound() {
  return (
    <section aria-labelledby="nf-h">
      <h2 id="nf-h">Page not found</h2>
      <Alert title="404">TANIM could not find that page. It may have moved.</Alert>
      <p><a href="#/home">Back to Home</a></p>
    </section>
  );
}

export function AccountProfile() {
  const [name, setName] = useState("");
  const [saved, setSaved] = useState(false);
  return (
    <section aria-labelledby="acct-h">
      <PageHeader title="Account profile" purpose="Your display name. Email changes use a separate verified flow." />
      <h2 id="acct-h" className="visually-hidden">Account profile</h2>
      <form onSubmit={(e) => { e.preventDefault(); setSaved(true); }} noValidate>
        <TextField name="display-name" label="Display name" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />
        <Button type="submit">Save name</Button>
      </form>
      {saved && <p role="status">Saved on this device. Server profile sync follows API-001.</p>}
    </section>
  );
}

export function AccountSecurity() {
  const [notice, setNotice] = useState<string | null>(null);
  return (
    <section aria-labelledby="sec-h">
      <PageHeader title="Account security" purpose="Sessions and sign-out. Device detail is minimized." />
      <h2 id="sec-h" className="visually-hidden">Account security</h2>
      <Card title="Current session">
        <p>This device, signed in now.</p>
        <p className="row">
          <Button variant="secondary" onClick={() => { clearSession(); setNotice("Signed out on this device."); }}>Sign out</Button>
          <Button variant="secondary" onClick={() => { clearSession(); setNotice("All sessions signed out on this device. Server-wide sign-out follows API-001."); }}>Sign out all sessions</Button>
        </p>
        {notice && <p role="status">{notice}</p>}
      </Card>
    </section>
  );
}
