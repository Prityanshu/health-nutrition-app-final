import React, { useState, useEffect, useRef } from 'react';
import {
  ArrowLeft, ArrowRight, Check, ChefHat, Eye, EyeOff,
  Loader2, Lock, Mail, Sparkles, Target, User as UserIcon, AlertCircle,
} from 'lucide-react';
import { browserTimezone, syncTimezone } from '../localDay';
import { ageFrom, isoYearsAgo } from '../age';
import Lotus from './Lotus';

/**
 * Sign in / create account.
 *
 * This is the first screen anyone sees, and it was the last one still on the
 * original light theme - a white page with three stacked inputs that then
 * dropped the user into a dark app. Now it uses the same surface, type and
 * motion language as the rest of Kayosha.
 *
 * Two decisions worth noting:
 *
 * 1. Registration is split into two steps. It collects eight fields, and a
 *    single column of eight inputs is the most reliable way to lose someone
 *    before they finish. Step one is the account, step two is the body data -
 *    which is also a natural place to explain *why* it is being asked for.
 *
 * 2. Activity level is now collected. It was already in the payload, silently
 *    defaulting to "moderately_active", and it multiplies BMR when targets are
 *    calculated - so a sedentary user was being handed roughly 300 kcal more
 *    than they should get, from their very first day.
 */

const ACTIVITY_LEVELS = [
  { key: 'sedentary', label: 'Sedentary', hint: 'Desk job, little exercise' },
  { key: 'lightly_active', label: 'Light', hint: 'Exercise 1–3 days a week' },
  { key: 'moderately_active', label: 'Moderate', hint: 'Exercise 3–5 days a week' },
  { key: 'very_active', label: 'Very active', hint: 'Hard exercise 6–7 days' },
  { key: 'extra_active', label: 'Athlete', hint: 'Physical job or twice daily' },
];

const SEXES = [
  { key: 'male', label: 'Male' },
  { key: 'female', label: 'Female' },
  { key: '', label: 'Prefer not to say' },
];

const HIGHLIGHTS = [
  { icon: Sparkles, title: 'One assistant, not six menus', body: 'Ask for a recipe, a workout, a week of meals — it remembers the conversation.' },
  { icon: Target, title: 'Targets worked out for you', body: 'Pick a goal. Calories and macros come from your own measurements, not a guess.' },
  { icon: ChefHat, title: 'Built around what you eat', body: 'Regional cuisines, your budget, and the ingredients already in your kitchen.' },
];

/* ---------------------------------------------------------------- field --
   A labelled input with the icon inside the control. Kept local because it
   is only used here and needs the auth-specific focus treatment.          */

function Field({
  icon: Icon, label, type = 'text', value, onChange, placeholder,
  required = true, autoComplete, hint, inputRef, suffix, ...rest
}) {
  const [reveal, setReveal] = useState(false);
  const isPassword = type === 'password';
  const resolvedType = isPassword && reveal ? 'text' : type;

  return (
    <label className="auth-field">
      <span className="auth-label">
        {label}
        {hint && <span className="auth-hint">{hint}</span>}
      </span>
      <span className="auth-control">
        {Icon && <Icon size={16} className="auth-control-icon" />}
        <input
          ref={inputRef}
          type={resolvedType}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          required={required}
          autoComplete={autoComplete}
          style={{ paddingLeft: Icon ? '2.4rem' : '0.9rem' }}
          {...rest}
        />
        {suffix && <span className="auth-suffix">{suffix}</span>}
        {isPassword && (
          <button
            type="button"
            className="auth-reveal"
            onClick={() => setReveal((r) => !r)}
            aria-label={reveal ? 'Hide password' : 'Show password'}
            tabIndex={-1}
          >
            {reveal ? <EyeOff size={15} /> : <Eye size={15} />}
          </button>
        )}
      </span>
    </label>
  );
}

/* ------------------------------------------------------------------ main -- */

export default function Auth({ apiBase, onAuthenticated, notice: initialNotice = '' }) {
  const [mode, setMode] = useState('login');     // 'login' | 'register'
  const [step, setStep] = useState(1);           // registration step
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  // Seeded by the caller when the user was bounced here - an expired session
  // needs explaining, or the login screen looks like a bug.
  const [notice, setNotice] = useState(initialNotice);
  const firstField = useRef(null);

  const [login, setLogin] = useState({ username: '', password: '' });
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotSent, setForgotSent] = useState('');
  const [reg, setReg] = useState({
    email: '', username: '', password: '', full_name: '',
    date_of_birth: '', weight: '', height: '',
    activity_level: 'moderately_active', sex: '',
  });

  // Dark surfaces are set on <body> so the ambient glow covers the viewport.
  // AppShell does the same once signed in; doing it here too means there is no
  // white flash between the two screens.
  useEffect(() => {
    document.body.classList.add('theme-dark');
    return () => document.body.classList.remove('theme-dark');
  }, []);

  // Moving between modes or steps should put the cursor where typing starts.
  useEffect(() => {
    const t = setTimeout(() => firstField.current?.focus(), 60);
    return () => clearTimeout(t);
  }, [mode, step]);

  const switchMode = (next) => {
    setMode(next);
    setStep(1);
    setError('');
    setNotice('');
    setForgotSent('');
  };

  const submitForgot = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${apiBase}/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: forgotEmail.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        // Whatever happened server-side, the answer is the same - see the
        // endpoint. Repeating it verbatim keeps the client from inventing a
        // more specific claim than the server was willing to make.
        setForgotSent(data.message || 'If that address has an account, a link is on its way.');
      } else {
        setError(readError(data.detail, 'Could not send a reset link. Try again shortly.'));
      }
    } catch {
      setError('Could not reach the server. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  // FastAPI validation errors arrive as a list of objects; rendering that
  // straight into the DOM produced "[object Object]" in the old screen.
  const readError = (detail, fallback) => {
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && detail.length) {
      const first = detail[0];
      const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : '';
      return field ? `${field}: ${first.msg}` : first.msg;
    }
    return fallback;
  };

  const submitLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      // The endpoint uses OAuth2PasswordRequestForm, which requires form
      // encoding rather than JSON.
      const body = new FormData();
      body.append('username', login.username.trim());
      body.append('password', login.password);

      const res = await fetch(`${apiBase}/auth/login`, { method: 'POST', body });
      const data = await res.json().catch(() => ({}));

      if (res.ok && data.access_token) {
        // Store first, then sync: syncTimezone reads the token from
        // localStorage, and onAuthenticated is what puts it there.
        localStorage.setItem('token', data.access_token);
        await syncTimezone(apiBase);
        onAuthenticated(data.access_token);
      } else {
        setError(readError(data.detail, 'That username or password was not recognised.'));
      }
    } catch {
      setError('Could not reach the server. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  const stepOneValid =
    reg.email.trim() && reg.username.trim() && reg.full_name.trim() && reg.password.length >= 6;

  const goToStepTwo = (e) => {
    e.preventDefault();
    if (!stepOneValid) {
      setError(
        reg.password.length < 6
          ? 'Choose a password of at least 6 characters.'
          : 'Fill in every field to continue.'
      );
      return;
    }
    setError('');
    setStep(2);
  };

  const submitRegister = async (e) => {
    e.preventDefault();

    // These start empty rather than pre-filled, so a blank field would send
    // NaN and come back as an opaque 422. `required` on the inputs normally
    // catches it; this is the backstop for autofill and browser quirks.
    const weight = parseFloat(reg.weight);
    const height = parseFloat(reg.height);
    if (!reg.date_of_birth || !Number.isFinite(weight) || !Number.isFinite(height)) {
      setError('Date of birth, weight and height are all needed to work out your targets.');
      return;
    }

    // Checked here as well as on the server, because a 422 listing a Pydantic
    // validation error is not a sentence anyone wants to read.
    const years = ageFrom(reg.date_of_birth);
    if (years === null) {
      setError('That date of birth does not look right.');
      return;
    }
    if (years < 13 || years > 100) {
      setError(`That works out as ${years}. This app is for ages 13 to 100.`);
      return;
    }

    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${apiBase}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...reg,
          email: reg.email.trim(),
          username: reg.username.trim(),
          full_name: reg.full_name.trim(),
          date_of_birth: reg.date_of_birth,
          weight,
          height,
          // So the very first day is theirs, not UTC's. Without this a user
          // registering at 01:00 IST would have their first meals filed
          // against the previous day.
          timezone: browserTimezone(),
        }),
      });
      const data = await res.json().catch(() => ({}));

      if (res.ok) {
        // Sign in straight away rather than bouncing back to a login form
        // with an alert(). The user just typed these credentials.
        const body = new FormData();
        body.append('username', reg.username.trim());
        body.append('password', reg.password);
        const loginRes = await fetch(`${apiBase}/auth/login`, { method: 'POST', body });
        const loginData = await loginRes.json().catch(() => ({}));

        if (loginRes.ok && loginData.access_token) {
          localStorage.setItem('token', loginData.access_token);
          await syncTimezone(apiBase);
          onAuthenticated(loginData.access_token);
          return;
        }
        // Account exists but auto sign-in failed - say so plainly.
        setMode('login');
        setStep(1);
        setLogin({ username: reg.username.trim(), password: '' });
        setNotice('Account created. Sign in to continue.');
      } else {
        // A duplicate email or username is a step-one problem; send them back
        // rather than showing the error under fields that are fine.
        const msg = readError(data.detail, 'Could not create the account.');
        setError(msg);
        if (/email|username/i.test(msg)) setStep(1);
      }
    } catch {
      setError('Could not reach the server. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  const busy = (labelIdle, labelBusy) =>
    loading ? (
      <>
        <Loader2 size={16} className="spin" /> {labelBusy}
      </>
    ) : (
      <>{labelIdle}</>
    );

  return (
    <div className="auth-page">
      {/* ---------------------------------------------------- brand side -- */}
      <aside className="auth-brand">
        <div className="auth-orb auth-orb-a" />
        <div className="auth-orb auth-orb-b" />

        <div className="auth-brand-inner">
          {/* Name first, mark to its right, motto beneath - the same order as
              the logo, so the sign-in page and the app agree. */}
          <div className="auth-logo" style={{ display: 'block' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <span className="auth-logo-text">Kayosha</span>
              <Lotus size={38} strokeWidth={3.4} />
            </div>
            <div
              style={{
                fontSize: '0.6875rem', letterSpacing: '0.2em', textTransform: 'uppercase',
                color: 'var(--brand-magenta)', fontWeight: 600, marginTop: 6,
              }}
            >
              Nourish. Move. Thrive.
            </div>
          </div>

          <h1 className="auth-headline">
            Eat and train from<br />
            <span className="auth-headline-accent">your</span> numbers.
          </h1>
          <p className="auth-sub">
            Nutrition and training that adapt to what you actually log — not a
            template someone else is following.
          </p>

          <ul className="auth-highlights">
            {HIGHLIGHTS.map(({ icon: Icon, title, body }) => (
              <li key={title}>
                <span className="auth-highlight-icon"><Icon size={15} /></span>
                <span>
                  <strong>{title}</strong>
                  <em>{body}</em>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      {/* ----------------------------------------------------- form side -- */}
      <main className="auth-form-side">
        <div className="auth-card">
          {/* Compact logo for the stacked mobile layout, where the brand
              panel is reduced to a strip. */}
          <div className="auth-logo auth-logo-compact" style={{ display: 'block' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className="auth-logo-text">Kayosha</span>
              <Lotus size={30} strokeWidth={3.6} />
            </div>
            <div
              style={{
                fontSize: '0.625rem', letterSpacing: '0.18em', textTransform: 'uppercase',
                color: 'var(--brand-magenta)', fontWeight: 600, marginTop: 4,
              }}
            >
              Nourish. Move. Thrive.
            </div>
          </div>

          <div className="segmented auth-segmented">
            <button
              type="button"
              className={mode === 'login' ? 'is-active' : ''}
              onClick={() => switchMode('login')}
            >
              Sign in
            </button>
            <button
              type="button"
              className={mode === 'register' ? 'is-active' : ''}
              onClick={() => switchMode('register')}
            >
              Create account
            </button>
          </div>

          {/* ------------------------------------------------------ login -- */}
          {mode === 'login' && (
            <form onSubmit={submitLogin} className="auth-form" key="login">
              <header className="auth-form-head">
                <h2>Welcome back</h2>
                <p>Pick up where you left off.</p>
              </header>

              {notice && (
                <div className={notice === initialNotice && initialNotice ? 'auth-error' : 'auth-notice'}>
                  {notice === initialNotice && initialNotice
                    ? <AlertCircle size={15} />
                    : <Check size={15} />}
                  <span>{notice}</span>
                </div>
              )}

              <Field
                icon={UserIcon}
                label="Email or username"
                value={login.username}
                inputRef={firstField}
                autoComplete="username"
                placeholder="you@example.com"
                onChange={(e) => setLogin({ ...login, username: e.target.value })}
              />
              <Field
                icon={Lock}
                label="Password"
                type="password"
                value={login.password}
                autoComplete="current-password"
                placeholder="••••••••"
                onChange={(e) => setLogin({ ...login, password: e.target.value })}
              />

              {error && (
                <div className="auth-error">
                  <AlertCircle size={15} /> <span>{error}</span>
                </div>
              )}

              <button type="submit" className="generate-btn" disabled={loading}>
                {busy('Sign in', 'Signing in…')}
              </button>

              <p className="auth-switch">
                <button type="button" onClick={() => switchMode('forgot')}>
                  Forgot your password?
                </button>
              </p>

              <p className="auth-switch">
                New here?{' '}
                <button type="button" onClick={() => switchMode('register')}>
                  Create an account
                </button>
              </p>
            </form>
          )}

          {/* ----------------------------------------------------- forgot -- */}
          {mode === 'forgot' && (
            <form onSubmit={submitForgot} className="auth-form">
              <p className="section-sub" style={{ marginBottom: '0.25rem' }}>
                Give the email address on your account and we will send a link
                to set a new password.
              </p>

              <Field
                icon={Mail}
                label="Email"
                type="email"
                value={forgotEmail}
                inputRef={firstField}
                autoComplete="email"
                placeholder="you@example.com"
                onChange={(e) => setForgotEmail(e.target.value)}
              />

              {/* The server answers identically whether or not the address
                  exists, so this is shown on success without claiming an
                  account was found. Saying "we sent it" would leak exactly
                  what the endpoint carefully does not. */}
              {forgotSent && (
                <div className="auth-notice">
                  <Check size={15} />
                  <span>{forgotSent}</span>
                </div>
              )}

              {error && (
                <div className="auth-error">
                  <AlertCircle size={15} /> <span>{error}</span>
                </div>
              )}

              <button type="submit" className="generate-btn" disabled={loading || !!forgotSent}>
                {busy('Send the link', 'Sending…')}
              </button>

              <p className="auth-switch">
                <button type="button" onClick={() => switchMode('login')}>
                  Back to sign in
                </button>
              </p>
            </form>
          )}

          {/* --------------------------------------------------- register -- */}
          {mode === 'register' && (
            <form
              onSubmit={step === 1 ? goToStepTwo : submitRegister}
              className="auth-form"
              key={`register-${step}`}
            >
              <header className="auth-form-head">
                <h2>{step === 1 ? 'Create your account' : 'A little about you'}</h2>
                <p>
                  {step === 1
                    ? 'Takes about a minute.'
                    : 'Used to work out your calories and macros. You can change any of it later.'}
                </p>
              </header>

              <div className="auth-steps" aria-label={`Step ${step} of 2`}>
                <span className={step >= 1 ? 'is-done' : ''} />
                <span className={step >= 2 ? 'is-done' : ''} />
              </div>

              {step === 1 ? (
                <>
                  <Field
                    icon={UserIcon}
                    label="Full name"
                    value={reg.full_name}
                    inputRef={firstField}
                    autoComplete="name"
                    placeholder="Prityanshu Yadav"
                    onChange={(e) => setReg({ ...reg, full_name: e.target.value })}
                  />
                  <Field
                    icon={Mail}
                    label="Email"
                    type="email"
                    value={reg.email}
                    autoComplete="email"
                    placeholder="you@example.com"
                    onChange={(e) => setReg({ ...reg, email: e.target.value })}
                  />
                  <Field
                    icon={UserIcon}
                    label="Username"
                    value={reg.username}
                    autoComplete="username"
                    placeholder="How you'll sign in"
                    onChange={(e) => setReg({ ...reg, username: e.target.value })}
                  />
                  <Field
                    icon={Lock}
                    label="Password"
                    type="password"
                    hint="6 characters or more"
                    value={reg.password}
                    autoComplete="new-password"
                    placeholder="••••••••"
                    onChange={(e) => setReg({ ...reg, password: e.target.value })}
                  />
                </>
              ) : (
                <>
                  <div className="auth-row">
                    {/* A birth date rather than an age. Age feeds the BMR
                        calculation, so a number typed once is wrong from the
                        next birthday onwards and drags every calorie target
                        with it. A date stays true. The bounds are dates rather
                        than years so the picker itself refuses an impossible
                        one. */}
                    <Field
                      label="Date of birth"
                      type="date"
                      min={isoYearsAgo(100)}
                      max={isoYearsAgo(13)}
                      value={reg.date_of_birth}
                      inputRef={firstField}
                      onChange={(e) => setReg({ ...reg, date_of_birth: e.target.value })}
                    />
                    <Field
                      label="Weight"
                      type="number"
                      min="25"
                      max="300"
                      step="0.1"
                      suffix="kg"
                      value={reg.weight}
                      placeholder="70"
                      onChange={(e) => setReg({ ...reg, weight: e.target.value })}
                    />
                    <Field
                      label="Height"
                      type="number"
                      min="100"
                      max="250"
                      suffix="cm"
                      value={reg.height}
                      placeholder="170"
                      onChange={(e) => setReg({ ...reg, height: e.target.value })}
                    />
                  </div>

                  <div className="auth-field">
                    <span className="auth-label">
                      Sex <span className="auth-hint">changes the BMR formula</span>
                    </span>
                    <div className="auth-chips">
                      {SEXES.map((s) => (
                        <button
                          key={s.label}
                          type="button"
                          className={`toggle-chip ${reg.sex === s.key ? 'is-active' : ''}`}
                          onClick={() => setReg({ ...reg, sex: s.key })}
                        >
                          {s.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="auth-field">
                    <span className="auth-label">
                      How active are you? <span className="auth-hint">outside deliberate exercise too</span>
                    </span>
                    <div className="auth-activity">
                      {ACTIVITY_LEVELS.map((a) => (
                        <button
                          key={a.key}
                          type="button"
                          className={`auth-activity-tile ${reg.activity_level === a.key ? 'is-active' : ''}`}
                          onClick={() => setReg({ ...reg, activity_level: a.key })}
                        >
                          <strong>{a.label}</strong>
                          <em>{a.hint}</em>
                        </button>
                      ))}
                    </div>
                  </div>
                </>
              )}

              {error && (
                <div className="auth-error">
                  <AlertCircle size={15} /> <span>{error}</span>
                </div>
              )}

              <div className="auth-actions">
                {step === 2 && (
                  <button
                    type="button"
                    className="ghost-btn"
                    onClick={() => { setStep(1); setError(''); }}
                    disabled={loading}
                  >
                    <ArrowLeft size={15} /> Back
                  </button>
                )}
                <button type="submit" className="generate-btn" disabled={loading}>
                  {step === 1
                    ? <>Continue <ArrowRight size={16} /></>
                    : busy('Create account', 'Creating…')}
                </button>
              </div>

              <p className="auth-switch">
                Already registered?{' '}
                <button type="button" onClick={() => switchMode('login')}>
                  Sign in
                </button>
              </p>
            </form>
          )}
        </div>

        <p className="auth-foot">
          Estimates are generated from the details you provide. Not medical advice.
        </p>
      </main>
    </div>
  );
}
