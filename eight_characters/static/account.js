// The account. Charts need one; the start page does not. There is no password: a code
// sent by email signs in, and the first code for a new address creates its account,
// in the language chosen for it. Signed in, the dialog is the account itself: its
// language, its data, signing out and deleting it.
//
// The session is a cookie the page's scripts cannot read. The page knows who is signed
// in from the server, which names the account when it serves the page, and from what
// signing in and out answer; a chart asked for after the session ended answers 401,
// and the page asks for a sign-in again.
(() => {
  const TURNSTILE_SCRIPT = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
  const LANGUAGES = ['fi', 'en'];
  // When an account last changed, as the server writes it: the fixed form orders as
  // text the way the moments do, and each change moves it on.
  const CHANGED = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
  // An account's key: the same for its whole life, and another for an account made again
  // with the same address.
  const KEY = /^[0-9a-f]{64}$/;
  // What a refused request for a code means, by its status.
  const CODE_REFUSALS = {
    400: 'account_bad_email',
    403: 'account_check_refused',
    429: 'account_too_many',
    502: 'account_mail_failed',
    503: 'account_check_down',
  };

  const create = ({ dialog, button, state, translate: t, language, embedded, onLanguage, onSignedOut }) => {
    if (!dialog || !button) throw new Error('The account dialog or its button is missing.');
    const part = (id) => {
      const element = dialog.querySelector(`#${id}`);
      if (!element) throw new Error(`The account dialog has no #${id}.`);
      return element;
    };
    const title = part('account-title');
    const start = part('account-start');
    const notice = part('account-notice');
    const lead = part('account-lead');
    const email = part('account-email');
    const emailStatus = part('account-email-status');
    const languages = part('account-language');
    const languageStatus = part('account-language-status');
    const check = part('account-check');
    const startError = part('account-start-error');
    const send = part('account-send');
    const modeSwitch = part('account-mode');
    const codeStep = part('account-code-step');
    const sent = part('account-sent');
    const code = part('account-code');
    const codeStatus = part('account-code-status');
    const verify = part('account-verify');
    const restart = part('account-restart');
    const menu = part('account-menu');
    const who = part('account-who');
    const plan = part('account-plan');
    const languageSwitch = part('account-language-switch');
    const exportButton = part('account-export');
    const signOutButton = part('account-sign-out');
    const signOutEverywhereButton = part('account-sign-out-everywhere');
    const deleteOpen = part('account-delete-open');
    const deleteForm = part('account-delete');
    const deleteEmail = part('account-delete-email');
    const deleteStatus = part('account-delete-status');
    const deleteConfirm = part('account-delete-confirm');
    const status = part('account-status');
    const siteKey = dialog.dataset.siteKey;
    if (!siteKey) throw new Error('The account dialog has no Turnstile site key.');

    // An account as the server describes it; anything else stops the page.
    const accountOf = (value) => {
      if (value === null || typeof value !== 'object' || typeof value.email !== 'string'
        || !LANGUAGES.includes(value.language) || typeof value.plan !== 'string'
        || typeof value.updated_at !== 'string' || !CHANGED.test(value.updated_at)
        || typeof value.key !== 'string' || !KEY.test(value.key)) {
        throw new Error(`Not an account: ${JSON.stringify(value)}`);
      }
      return value;
    };

    let account = state === null ? null : accountOf(state);
    // When the page learned who is signed in. It learns it from answers, each from a
    // moment, in the order the page sees them: a request that carries the session cookie
    // tells of the cookie the browser held as it was sent, and an answer that sets or
    // removes the cookie, of the cookie from when it comes. The page's account is what
    // the newest answer said, from moment `known` (the page as served is moment 0): an
    // answer from before it changes nothing, however late it comes.
    let moments = 0;
    let known = 0;
    const moment = () => ++moments;
    // 'create' or 'sign_in'; 'start', 'code' or 'menu'.
    let mode = 'create';
    let step = 'start';
    // The address a code was sent to, and what for.
    let asked = null;
    // Said at the top of the start step: why it shows (signed out, deleted, ended).
    let noticeKey = null;
    // A chart waiting for a sign-in: { promise, resolve, reject }.
    let waiting = null;
    let busy = false;
    // The menu opened while an action or a question was under way: who the session is
    // is asked again when that one ends.
    let confirmLater = false;
    // Turnstile's script, and its widget with the language it speaks.
    let turnstileLoad = null;
    let widget = null;
    let widgetLanguage = null;

    // A field's or the menu's message: what to fix, or what was done.
    const setStatus = (element, text, isError = true) => {
      element.textContent = text;
      element.classList.toggle('is-error', isError && Boolean(text));
    };
    // What stops a code being asked for. One about the check goes when the check
    // answers; any other stays until the next try.
    let checkSaidIt = false;
    const setStartError = (text, aboutTheCheck = false) => {
      startError.textContent = text;
      startError.classList.toggle('hidden', !text);
      checkSaidIt = aboutTheCheck && Boolean(text);
    };
    // A button at work says so and takes no second press.
    const setBusy = (control, value, key) => {
      busy = value;
      control.disabled = value;
      control.classList.toggle('is-pending', value);
      control.dataset.i18n = key;
      control.textContent = t(key);
    };

    // Everything the dialog and the button say that depends on the step, the mode or
    // the account, in the page's language.
    const refresh = () => {
      button.dataset.i18n = account ? 'account_title' : 'account_sign_in';
      button.textContent = t(button.dataset.i18n);
      start.classList.toggle('hidden', step !== 'start');
      codeStep.classList.toggle('hidden', step !== 'code');
      menu.classList.toggle('hidden', step !== 'menu');
      let heading = mode === 'create' ? 'account_create_title' : 'account_sign_in_title';
      if (step === 'code') heading = 'account_code_title';
      if (step === 'menu') heading = 'account_title';
      title.textContent = t(heading);
      notice.textContent = noticeKey ? t(noticeKey) : '';
      notice.classList.toggle('hidden', !noticeKey);
      lead.textContent = t(mode === 'create' ? 'account_create_lead' : 'account_sign_in_lead');
      // A new account's language is chosen; signing in uses the account's own.
      languages.classList.toggle('hidden', mode !== 'create');
      languages.disabled = mode !== 'create';
      modeSwitch.textContent = t(mode === 'create' ? 'account_have_one' : 'account_need_one');
      sent.textContent = asked === null ? ''
        : t(asked.purpose === 'create' ? 'account_code_sent' : 'account_code_sent_if', { email: asked.email });
      if (account) {
        who.textContent = t('account_signed_in_as', { email: account.email });
        plan.textContent = t('account_plan', { plan: t(`plan_${account.plan}`) });
        languageSwitch.querySelectorAll('button[data-account-lang]').forEach((choice) => {
          choice.setAttribute('aria-pressed', String(choice.dataset.accountLang === account.language));
        });
      }
    };

    // ── The check that a person asks for the code (Cloudflare Turnstile) ──
    // Its script loads when it is first needed, so the start page loads nothing from
    // another site. A failed load is said, and tried again at the next opening.
    const loadTurnstile = () => {
      turnstileLoad ??= new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = TURNSTILE_SCRIPT;
        script.async = true;
        script.addEventListener('load', () => {
          if (window.turnstile) resolve(window.turnstile);
          else reject(new Error('Turnstile loaded without its API.'));
        });
        script.addEventListener('error', () => reject(new Error(`${TURNSTILE_SCRIPT} did not load.`)));
        document.head.append(script);
      }).catch((err) => {
        turnstileLoad = null;
        throw err;
      });
      return turnstileLoad;
    };
    const showCheck = async () => {
      try {
        const turnstile = await loadTurnstile();
        if (widget !== null && widgetLanguage !== language()) {
          turnstile.remove(widget);
          widget = null;
        }
        if (widget !== null || !dialog.open) return;
        widgetLanguage = language();
        widget = turnstile.render(check, {
          sitekey: siteKey,
          language: widgetLanguage,
          theme: 'auto',
          size: 'flexible',
          'response-field': false,
          callback: () => {
            if (checkSaidIt) setStartError('');
          },
          'error-callback': (failure) => {
            setStartError(t('account_check_failed', { code: failure }), true);
          },
        });
      } catch (err) {
        console.error(err);
        setStartError(t('account_check_unloaded'), true);
      }
    };
    // Each answer of the check is good for one request.
    const checkAnswer = () => (widget === null ? '' : window.turnstile.getResponse(widget) || '');
    const resetCheck = () => {
      if (widget !== null) window.turnstile.reset(widget);
    };

    // A request to the account API. Browsers send the page's Origin with every request
    // that can change something, which the API requires.
    const call = async (method, url, body) => {
      try {
        return await fetch(url, body === undefined ? { method } : {
          method,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
      } catch (err) {
        throw new Error(t('account_offline'), { cause: err });
      }
    };

    // ── Opening and closing ──
    const focusStep = () => {
      if (step === 'start') email.focus();
      else if (step === 'code') code.focus();
    };
    // Deleting the account starts closed, and empty, each time.
    const closeDeleting = () => {
      deleteForm.classList.add('hidden');
      deleteOpen.setAttribute('aria-expanded', 'false');
      deleteEmail.value = '';
      setStatus(deleteStatus, '');
    };
    const open = () => {
      if (dialog.open) {
        // Already open: if the menu has just given way to signing in, that needs its
        // check.
        if (step === 'start') showCheck();
        return;
      }
      if (account) step = 'menu';
      else if (step === 'menu') step = 'start';
      closeDeleting();
      setStatus(status, '');
      refresh();
      dialog.showModal();
      if (step === 'start') showCheck();
      else if (step === 'menu') confirmSession();
      focusStep();
    };
    // Escape closes the dialog and nothing behind it, such as an open topic.
    dialog.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') event.stopPropagation();
    });
    dialog.addEventListener('click', (event) => {
      if (event.target.closest('[data-close-dialog]')) dialog.close();
    });
    // Closed before signing in: the chart that waited is not shown. A code already
    // sent stays asked for, and the dialog opens at it again.
    dialog.addEventListener('close', () => {
      noticeKey = null;
      if (!waiting) return;
      const { reject } = waiting;
      waiting = null;
      reject(new Error(t('account_needed')));
    });
    button.addEventListener('click', open);

    // ── Signing in ──
    const signedIn = (value) => {
      account = later(accountOf(value));
      // The account's language is the page's from now on, until the reader changes it.
      onLanguage(account.language);
      closeSignedIn();
    };
    // The dialog closes, signed in, and what waited for a sign-in goes on with the
    // account the page holds.
    const closeSignedIn = () => {
      asked = null;
      noticeKey = null;
      step = 'start';
      code.value = '';
      const pending = waiting;
      waiting = null;
      dialog.close();
      refresh();
      if (pending) pending.resolve(account);
    };

    modeSwitch.addEventListener('click', () => {
      mode = mode === 'create' ? 'sign_in' : 'create';
      setStatus(emailStatus, '');
      setStatus(languageStatus, '');
      setStartError('');
      refresh();
      email.focus();
    });

    start.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (busy) return;
      setStartError('');
      const address = email.value.trim();
      setStatus(emailStatus, !address ? t('account_need_email')
        : email.validity.typeMismatch ? t('account_bad_email') : '');
      const chosen = languages.querySelector('input:checked');
      setStatus(languageStatus, mode === 'create' && !chosen ? t('account_need_language') : '');
      if (emailStatus.textContent) {
        email.focus();
        return;
      }
      if (languageStatus.textContent) {
        languages.querySelector('input').focus();
        return;
      }
      const answer = checkAnswer();
      if (!answer) {
        // No widget: its script did not load, and is tried again.
        setStartError(t(widget === null ? 'account_check_unloaded' : 'account_need_check'), true);
        if (widget === null) showCheck();
        return;
      }
      // What is asked for is what the dialog showed when sent, even if it changes side
      // while the answer is on its way.
      const purpose = mode;
      setBusy(send, true, 'account_sending');
      try {
        const response = await call('POST', '/api/account/code', {
          email: address,
          purpose,
          language: purpose === 'create' ? chosen.value : null,
          page_language: language(),
          turnstile: answer,
        });
        if (response.status !== 202) {
          throw new Error(t(CODE_REFUSALS[response.status] ?? 'account_server_error', { status: response.status }));
        }
        asked = { email: address, purpose };
        noticeKey = null;
        step = 'code';
        code.value = '';
        setStatus(codeStatus, '');
        refresh();
        code.focus();
      } catch (err) {
        console.error(err);
        setStartError(err.message);
      } finally {
        resetCheck();
        setBusy(send, false, 'account_send');
      }
    });

    codeStep.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (busy) return;
      const typed = code.value.trim();
      setStatus(codeStatus, typed ? '' : t('account_need_code'));
      if (!typed) {
        code.focus();
        return;
      }
      setBusy(verify, true, 'account_checking');
      try {
        const response = await call('POST', '/api/account/session', { email: asked.email, code: typed });
        if (response.status === 400) {
          setStatus(codeStatus, t('account_wrong_code'));
          code.select();
          return;
        }
        if (!response.ok) throw new Error(t('account_server_error', { status: response.status }));
        // The answer has set the session cookie: from now, the browser holds this
        // session, and an answer about the cookie before it changes nothing.
        const at = moment();
        known = at;
        const value = await response.json();
        // The page learned of a newer session while the account was on its way: the one
        // the browser held after this answer set its cookie. The dialog closes signed in
        // to it, or, if there was none (signed out elsewhere since), asks for a sign-in
        // again.
        if (at < known) {
          merge(value);
          if (account !== null) closeSignedIn();
          else askAgain();
          return;
        }
        signedIn(value);
      } catch (err) {
        console.error(err);
        setStatus(codeStatus, err.message);
      } finally {
        setBusy(verify, false, 'account_continue');
      }
    });

    // A sign-in overtaken by the end of its session (signed out elsewhere): the dialog
    // asks for a sign-in again, and says why.
    const askAgain = () => {
      asked = null;
      step = 'start';
      code.value = '';
      refresh();
      showCheck();
      email.focus();
    };

    // A new code, for this address or another.
    restart.addEventListener('click', () => {
      asked = null;
      step = 'start';
      setStartError('');
      refresh();
      showCheck();
      email.focus();
    });

    // Whether an answer names the account the page holds: by its key, since an account
    // made again with the address is another.
    const same = (told) => account !== null && told.key === account.key;
    // Of two descriptions of one account, the later change's (`updated_at` moves on with
    // each); another account's is taken whole.
    const later = (told) => (same(told) && told.updated_at < account.updated_at ? account : told);
    // An answer older than what the page knows of whose the session is still tells of the
    // account it names: if that is the account the page holds, a later change of it is
    // kept.
    const merge = (value) => {
      const told = accountOf(value);
      if (!same(told) || told.updated_at <= account.updated_at) return;
      account = told;
      refresh();
    };
    // The newest answer of whose the session is, from moment `at`, names `value`'s
    // account, and the page takes it: an older answer, about the session as it was
    // before, changes nothing. Another account, signed in to in another tab (the tabs
    // share the session cookie), is taken as a sign-in here: the page takes its language,
    // and a dialog asking for a sign-in closes, signed in to it. Of the same account the
    // page keeps the later change's language and plan, which a check read before a
    // change of the reader's may not carry.
    const take = (at, value) => {
      const told = accountOf(value);
      const another = !same(told);
      known = at;
      account = later(told);
      if (another) onLanguage(account.language);
      if (another && dialog.open && step !== 'menu') closeSignedIn();
      else refresh();
    };
    // A request was refused for want of a session, perhaps one sent before another tab
    // signed in. Before the page lets its session go, it asks whether the browser holds
    // one now: if so, the page takes it and answers true; if not, `letGo` ends it here,
    // and the answer is false. An answer no longer wanted (`wanted`), or older than what
    // the page has learned since, changes nothing of who is signed in, and the page
    // answers with what it knows; a later change of the account it holds is kept.
    const refusedNow = async (letGo, { wanted = () => true } = {}) => {
      const at = moment();
      const response = await call('GET', '/api/account');
      const late = () => !wanted() || at < known;
      if (late() && !response.ok) return account !== null;
      if (response.status === 401) {
        known = at;
        letGo();
        return false;
      }
      if (!response.ok) throw new Error(t('account_server_error', { status: response.status }));
      const value = await response.json();
      if (late()) {
        merge(value);
        return account !== null;
      }
      take(at, value);
      return true;
    };

    // ── The account ──
    // The account's session ended meanwhile (signed out elsewhere, or deleted): the
    // dialog asks for a sign-in instead.
    const ended = () => {
      account = null;
      mode = 'sign_in';
      step = 'start';
      noticeKey = 'account_session_ended';
      refresh();
      showCheck();
      email.focus();
    };
    // Signed out on purpose: nothing of the account stays on screen. The answer removed
    // the session cookie: from now, the browser holds none.
    const signedOut = (key) => {
      known = moment();
      account = null;
      mode = 'sign_in';
      step = 'start';
      noticeKey = key;
      closeDeleting();
      onSignedOut();
      refresh();
      showCheck();
      email.focus();
    };
    // A menu action: one at a time, and what went wrong said under the menu. It is for
    // the account the menu names as it starts, which it names to the server too, and
    // its answer is about the session cookie the browser held as it was sent.
    const act = async (control, run) => {
      if (busy) return;
      busy = true;
      control.disabled = true;
      setStatus(status, '');
      try {
        await run();
      } catch (err) {
        console.error(err);
        setStatus(status, err.message);
      } finally {
        busy = false;
        control.disabled = false;
        askedMeanwhile();
      }
    };
    // An action or a question ended: if the menu opened again meanwhile, who the
    // session is is asked now, since the answer may have changed since.
    const askedMeanwhile = () => {
      if (!confirmLater) return;
      confirmLater = false;
      if (dialog.open && step === 'menu') confirmSession();
    };
    const refused = (response) => new Error(t('account_server_error', { status: response.status }));
    // Nothing was done for the account the menu named, and the menu says so.
    const changed = () => setStatus(status, t('account_changed'));
    // An action's answer, newer than anything the page has learned, says the session is
    // not the account the page holds: the page asks whose it is now, and the action waits
    // for the answer, whatever the dialog shows by then.
    const askWho = () => refusedNow(ended);
    // The session belonged to another account than the action named (another tab signed
    // in to it): nothing was done. The menu says so, and, unless the page has learned
    // since, asks whose the session is.
    const elsewhere = async (at) => {
      changed();
      if (at > known) await askWho();
    };
    // Refused for want of a session. Unless the page has learned since, it asks whether
    // the browser holds one after all (another tab signed in): if so, nothing was done,
    // and the menu says so, as it does if the page has learned since.
    const refusedHere = async (at) => {
      if (at < known || await refusedNow(ended)) changed();
    };
    // The menu's actions, which wait while the page asks who the session belongs to.
    const actions = () => [
      ...languageSwitch.querySelectorAll('button[data-account-lang]'),
      exportButton, signOutButton, signOutEverywhereButton, deleteOpen, deleteConfirm,
    ];
    // Who the session belongs to now, asked as the menu opens: another tab may have
    // signed out, or in to another account. Until the answer, the menu does nothing;
    // without one, it says why, and asks again at the next opening. Opened again while
    // an action or this question is under way, it asks once that one ends.
    const confirmSession = async () => {
      if (busy) {
        confirmLater = true;
        return;
      }
      busy = true;
      const at = moment();
      actions().forEach((control) => { control.disabled = true; });
      let answered = false;
      try {
        const response = await call('GET', '/api/account');
        if (at < known && !response.ok) {
          answered = true;
          return;
        }
        if (response.status === 401) {
          answered = true;
          await refusedNow(ended);
          return;
        }
        if (!response.ok) throw refused(response);
        const value = await response.json();
        answered = true;
        if (at < known) merge(value);
        else take(at, value);
      } catch (err) {
        console.error(err);
        setStatus(status, err.message);
      } finally {
        busy = false;
        if (answered) actions().forEach((control) => { control.disabled = false; });
        askedMeanwhile();
      }
    };

    languageSwitch.addEventListener('click', (event) => {
      const choice = event.target.closest('button[data-account-lang]');
      if (!choice || choice.getAttribute('aria-pressed') === 'true') return;
      act(choice, async () => {
        const at = moment();
        const response = await call('PATCH', '/api/account', {
          language: choice.dataset.accountLang, key: account.key,
        });
        if (response.status === 409) return elsewhere(at);
        if (response.status === 401) return refusedHere(at);
        if (!response.ok) throw refused(response);
        const value = accountOf(await response.json());
        // Set for the account named, in the session as it was sent. If the page has
        // learned nothing since, that is the session, and the page takes the account (as
        // a sign-in, if it held another or none). Of the account, the page keeps the later
        // change: the language is saved if that is this one; if another, a tab's since,
        // nothing was done.
        if (at > known) take(at, value);
        if (!same(value)) return changed();
        account = later(value);
        if (account.updated_at !== value.updated_at) return changed();
        onLanguage(account.language);
        refresh();
        setStatus(status, t('account_saved'), false);
      });
    });

    exportButton.addEventListener('click', () => act(exportButton, async () => {
      const { key } = account;
      const at = moment();
      const response = await call('POST', '/api/account/export', { key });
      if (response.status === 409) return elsewhere(at);
      if (response.status === 401) return refusedHere(at);
      if (!response.ok) throw refused(response);
      const file = await response.blob();
      // Made for the account named, in the session as it was sent. The file is the
      // reader's if the page still names that account, or if the page has learned
      // nothing since: then what it holds is older, and it asks whose the session is.
      const holds = account !== null && account.key === key;
      if (!holds && at < known) return changed();
      if (holds && at > known) known = at;
      const url = URL.createObjectURL(file);
      // Inside the dialog: while it is open, the rest of the page is inert.
      const link = document.createElement('a');
      link.href = url;
      link.download = 'bazi-account.json';
      link.hidden = true;
      dialog.append(link);
      link.click();
      link.remove();
      // Some browsers read the file after the click returns.
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      setStatus(status, t('account_exported'), false);
      if (!holds) await askWho();
    }));

    signOutButton.addEventListener('click', () => act(signOutButton, async () => {
      const response = await call('DELETE', '/api/account/session');
      if (!response.ok) throw refused(response);
      signedOut('account_signed_out');
    }));

    // A sign-out or a deletion that went through removed the browser's session cookie
    // with its answer, whichever account it held by then: the page is signed out, even
    // if it has taken another session meanwhile.
    signOutEverywhereButton.addEventListener('click', () => act(signOutEverywhereButton, async () => {
      const at = moment();
      const response = await call('DELETE', '/api/account/sessions', { key: account.key });
      if (response.ok) return signedOut('account_signed_out_everywhere');
      if (response.status === 409) return elsewhere(at);
      if (response.status === 401) return refusedHere(at);
      throw refused(response);
    }));

    deleteOpen.addEventListener('click', () => {
      const opening = deleteForm.classList.contains('hidden');
      deleteForm.classList.toggle('hidden', !opening);
      deleteOpen.setAttribute('aria-expanded', String(opening));
      if (opening) deleteEmail.focus();
    });

    deleteForm.addEventListener('submit', (event) => {
      event.preventDefault();
      act(deleteConfirm, async () => {
        const typed = deleteEmail.value.trim();
        if (typed.toLowerCase() !== account.email) {
          setStatus(deleteStatus, t('account_delete_mismatch'));
          deleteEmail.focus();
          return;
        }
        setStatus(deleteStatus, '');
        const at = moment();
        const response = await call('DELETE', '/api/account', { email: typed, key: account.key });
        if (response.ok) return signedOut('account_deleted');
        if (response.status === 409) return elsewhere(at);
        if (response.status === 401) return refusedHere(at);
        throw refused(response);
      });
    });

    // ── What the page asks ──
    // Resolves with the account once one is signed in; rejects when the dialog closes
    // first. In a comparison's frame, the page around it asks instead.
    const signIn = () => {
      if (account) return Promise.resolve(account);
      if (embedded) return Promise.reject(new Error(t('account_needed')));
      if (!waiting) {
        let resolve;
        let reject;
        const promise = new Promise((res, rej) => {
          resolve = res;
          reject = rej;
        });
        waiting = { promise, resolve, reject };
      }
      open();
      return waiting.promise;
    };
    // Whether the session still holds, as the server says: one that ended since the page
    // was served (signed out elsewhere, or unused for 30 days) is forgotten. An answer
    // no longer wanted (`wanted` says), or older than what the page has learned since,
    // changes nothing of who is signed in, so a sign-in made meanwhile stays, and the
    // caller goes no further; a later change of the account the page holds is kept.
    // The newest answer is taken whole; one asked for before a language the reader set
    // since is older, and changes nothing.
    const stillSignedIn = async (wanted) => {
      if (!account) return false;
      const at = moment();
      const response = await call('GET', '/api/account');
      const late = () => !wanted() || at < known;
      if (late() && !response.ok) return false;
      if (response.status === 401) return refusedNow(forget, { wanted });
      if (!response.ok) throw new Error(t('account_server_error', { status: response.status }));
      const value = await response.json();
      if (late()) {
        merge(value);
        return false;
      }
      take(at, value);
      return true;
    };
    // The server answered that no one is signed in: the session ended meanwhile.
    const forget = () => {
      account = null;
      mode = 'sign_in';
      if (step === 'menu') step = 'start';
      noticeKey = 'account_session_ended';
      refresh();
      // An open dialog that showed the account asks for a sign-in now, with its check.
      if (dialog.open && step === 'start') {
        showCheck();
        email.focus();
      }
    };

    return {
      signedIn: () => account !== null,
      stillSignedIn,
      // A chart refused for want of a session: whether the browser holds one now, while
      // the chart is still the one wanted.
      recheck: (wanted) => refusedNow(forget, { wanted }),
      signIn,
      open,
      isOpen: () => dialog.open,
      refresh,
    };
  };
  window.EC_ACCOUNT = { create };
})();
