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
        || !LANGUAGES.includes(value.language) || typeof value.plan !== 'string') {
        throw new Error(`Not an account: ${JSON.stringify(value)}`);
      }
      return value;
    };

    let account = state === null ? null : accountOf(state);
    // Which session the page holds: it moves on with every sign-in, sign-out and
    // session found ended, so an answer about an earlier one is told apart and
    // changes nothing.
    let held = 0;
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
      account = accountOf(value);
      held += 1;
      asked = null;
      noticeKey = null;
      step = 'start';
      code.value = '';
      // The account's language is the page's from now on, until the reader changes it.
      onLanguage(account.language);
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
        signedIn(await response.json());
      } catch (err) {
        console.error(err);
        setStatus(codeStatus, err.message);
      } finally {
        setBusy(verify, false, 'account_continue');
      }
    });

    // A new code, for this address or another.
    restart.addEventListener('click', () => {
      asked = null;
      step = 'start';
      setStartError('');
      refresh();
      showCheck();
      email.focus();
    });

    // What the server says of the account the session belongs to. Another account,
    // signed in to in another tab (the tabs share the session cookie), is taken as a
    // sign-in here: the page takes its language, and answers about the earlier session
    // change nothing. The same account keeps what the page knows of it, which may be
    // newer than the answer (a language set meanwhile).
    const identify = (value) => {
      const told = accountOf(value);
      if (account !== null && told.email === account.email) return;
      account = told;
      held += 1;
      onLanguage(account.language);
      refresh();
    };
    // The same, asked when no change of the page's own can be on its way (as the menu
    // opens, its actions waiting): the answer is newer than anything the page knows,
    // so the same account is taken whole, with a language another tab set.
    const learn = (value) => {
      const told = accountOf(value);
      if (account === null || told.email !== account.email) {
        identify(value);
        return;
      }
      account = told;
      refresh();
    };
    // A request was refused for want of a session, perhaps one sent before another tab
    // signed in. Before the page lets its session go, it asks whether the browser holds
    // one now: if so, the page takes it (learn) and answers true; if not, `letGo` ends
    // it here, and the answer is false.
    const refusedNow = async (letGo) => {
      const session = held;
      const response = await call('GET', '/api/account');
      if (session !== held) return account !== null;
      if (response.status === 401) {
        letGo();
        return false;
      }
      if (!response.ok) throw new Error(t('account_server_error', { status: response.status }));
      const value = await response.json();
      if (session !== held) return account !== null;
      learn(value);
      return true;
    };

    // ── The account ──
    // The account's session ended meanwhile (signed out elsewhere, or deleted): the
    // dialog asks for a sign-in instead.
    const ended = () => {
      account = null;
      held += 1;
      mode = 'sign_in';
      step = 'start';
      noticeKey = 'account_session_ended';
      refresh();
      showCheck();
      email.focus();
    };
    // Signed out on purpose: nothing of the account stays on screen.
    const signedOut = (key) => {
      account = null;
      held += 1;
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
    // the session the page holds as it starts; `still` says whether the page still
    // holds it as the answer comes. If not (signed in to another account in another
    // tab, or found ended), the answer was about the earlier session: it changes
    // nothing, and the menu says so.
    const act = async (control, run) => {
      if (busy) return;
      busy = true;
      control.disabled = true;
      setStatus(status, '');
      const session = held;
      const still = () => {
        if (session === held) return true;
        setStatus(status, t('account_changed'));
        return false;
      };
      try {
        await run(still);
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
    // The session belongs to another account than the menu names (another tab signed
    // in to it): nothing was done. The menu says so, and asks who the session is.
    const elsewhere = () => {
      setStatus(status, t('account_changed'));
      confirmSession();
    };
    // Refused for want of a session: if the browser holds one after all (another tab
    // signed in), nothing was done, and the menu says so.
    const refusedHere = async () => {
      if (await refusedNow(ended)) setStatus(status, t('account_changed'));
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
      const session = held;
      actions().forEach((control) => { control.disabled = true; });
      let known = false;
      try {
        const response = await call('GET', '/api/account');
        if (session !== held) {
          known = true;
          return;
        }
        if (response.status === 401) {
          known = true;
          await refusedNow(ended);
          return;
        }
        if (!response.ok) throw refused(response);
        const value = await response.json();
        known = true;
        if (session === held) learn(value);
      } catch (err) {
        console.error(err);
        setStatus(status, err.message);
      } finally {
        busy = false;
        if (known) actions().forEach((control) => { control.disabled = false; });
        askedMeanwhile();
      }
    };

    languageSwitch.addEventListener('click', (event) => {
      const choice = event.target.closest('button[data-account-lang]');
      if (!choice || choice.getAttribute('aria-pressed') === 'true') return;
      act(choice, async (still) => {
        const response = await call('PATCH', '/api/account', {
          language: choice.dataset.accountLang, email: account.email,
        });
        if (!still()) return;
        if (response.status === 409) return elsewhere();
        if (response.status === 401) return refusedHere();
        if (!response.ok) throw refused(response);
        const value = await response.json();
        if (!still()) return;
        account = accountOf(value);
        onLanguage(account.language);
        refresh();
        setStatus(status, t('account_saved'), false);
      });
    });

    exportButton.addEventListener('click', () => act(exportButton, async (still) => {
      const response = await call('POST', '/api/account/export', { email: account.email });
      if (!still()) return;
      if (response.status === 409) return elsewhere();
      if (response.status === 401) return refusedHere();
      if (!response.ok) throw refused(response);
      const file = await response.blob();
      if (!still()) return;
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
    }));

    signOutButton.addEventListener('click', () => act(signOutButton, async () => {
      const response = await call('DELETE', '/api/account/session');
      if (!response.ok) throw refused(response);
      signedOut('account_signed_out');
    }));

    // A sign-out or a deletion that went through removed the browser's session cookie
    // with its answer, whichever account it held by then: the page is signed out.
    signOutEverywhereButton.addEventListener('click', () => act(signOutEverywhereButton, async (still) => {
      const response = await call('DELETE', '/api/account/sessions', { email: account.email });
      if (!still()) return;
      if (response.status === 409) return elsewhere();
      if (response.status === 401) return refusedHere();
      if (!response.ok) throw refused(response);
      signedOut('account_signed_out_everywhere');
    }));

    deleteOpen.addEventListener('click', () => {
      const opening = deleteForm.classList.contains('hidden');
      deleteForm.classList.toggle('hidden', !opening);
      deleteOpen.setAttribute('aria-expanded', String(opening));
      if (opening) deleteEmail.focus();
    });

    deleteForm.addEventListener('submit', (event) => {
      event.preventDefault();
      act(deleteConfirm, async (still) => {
        const typed = deleteEmail.value.trim();
        if (typed.toLowerCase() !== account.email) {
          setStatus(deleteStatus, t('account_delete_mismatch'));
          deleteEmail.focus();
          return;
        }
        setStatus(deleteStatus, '');
        const response = await call('DELETE', '/api/account', { email: typed });
        if (!still()) return;
        // The address typed is the one the menu names (checked above): refused, it is
        // not the session's account, which another tab has signed in to since.
        if (response.status === 400) return elsewhere();
        if (response.status === 401) return refusedHere();
        if (!response.ok) throw refused(response);
        signedOut('account_deleted');
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
    // no longer wanted (`wanted` says), or about a session the page no longer holds,
    // changes nothing, so a sign-in made meanwhile stays; the caller goes no further.
    // Of the account itself, only who it is is taken from the answer (identify): the
    // page knows the rest from the start page and its own changes, which an answer
    // asked for before one of them would undo.
    const stillSignedIn = async (wanted) => {
      if (!account) return false;
      const session = held;
      const response = await call('GET', '/api/account');
      if (!wanted() || session !== held) return false;
      if (response.status === 401) return refusedNow(forget);
      if (!response.ok) throw new Error(t('account_server_error', { status: response.status }));
      const value = await response.json();
      if (!wanted() || session !== held) return false;
      identify(value);
      return true;
    };
    // The server answered that no one is signed in: the session ended meanwhile.
    const forget = () => {
      account = null;
      held += 1;
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
      // A chart refused for want of a session: whether the browser holds one now.
      recheck: () => refusedNow(forget),
      signIn,
      open,
      isOpen: () => dialog.open,
      refresh,
    };
  };
  window.EC_ACCOUNT = { create };
})();
