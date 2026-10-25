// Private sandbox controls. Payment and access remain the server's decision.
(() => {
  const TIERS = ['free', 'basic', 'plus', 'pro'];
  const STATES = ['free', 'paid', 'pending', 'held', 'expired', 'deleting', 'deleted'];
  const PRICES = { yearly: ['$59', '$129', '$249'], monthly: ['$6.99', '$14.99', '$29'] };

  const create = ({ dialog, translate: t, language, act, call, moment, getAccount, refusedHere, elsewhere }) => {
    const part = (id) => {
      const value = dialog.querySelector(`#account-billing${id}`);
      if (!value) throw new Error(`Missing billing control: ${id}`);
      return value;
    };
    const enabled = dialog.dataset.billingEnabled;
    if (!['true', 'false'].includes(enabled)) throw new Error('Missing billing availability.');
    const open = part('-open');
    const panel = part('');
    const summary = part('-summary');
    const offers = part('-offers');
    const period = part('-period');
    const cancel = part('-cancel');
    const result = part('-result');
    const choices = [...panel.querySelectorAll('[data-billing-plan]')];
    const controls = [open, period, ...choices, cancel];
    let key = null;
    let view = null;
    let generation = 0;

    const render = () => {
      summary.textContent = view === null ? '' : t('billing_summary', {
        tier: t(`billing_tier_${view.tier}`), status: t(`billing_state_${view.status}`),
      });
      if (view?.paid_through !== null && view?.paid_through !== undefined) {
        summary.textContent += ` · ${t('billing_paid_through', {
          date: new Intl.DateTimeFormat(language(), { dateStyle: 'medium', timeZone: 'UTC' })
            .format(new Date(view.paid_through * 1000)),
        })}`;
      }
      offers.hidden = view === null || !['free', 'expired'].includes(view.status);
      cancel.hidden = view === null || ['free', 'expired', 'deleting', 'deleted'].includes(view.status);
      choices.forEach((button, index) => {
        button.textContent = t('billing_buy', {
          tier: t(`billing_tier_${button.dataset.billingPlan}`),
          price: PRICES[period.value][index], period: t(`billing_${period.value}`),
        });
      });
    };
    const sync = (account) => {
      if (key !== (account?.key ?? null)) {
        key = account?.key ?? null;
        generation += 1;
        view = null;
        panel.hidden = true;
        open.setAttribute('aria-expanded', 'false');
        result.textContent = '';
      }
      open.hidden = enabled !== 'true' || account === null;
      render();
    };
    const receive = async (response, named, at, revision) => {
      if (revision !== generation || getAccount()?.key !== named) return null;
      if (response.status === 401) { await refusedHere(at); return null; }
      if (response.status === 409) { await elsewhere(at); return null; }
      if (!response.ok) throw new Error(t('account_server_error', { status: response.status }));
      const value = await response.json();
      if (revision !== generation || getAccount()?.key !== named) return null;
      if (value.key !== named) { await elsewhere(at); return null; }
      if (!TIERS.includes(value.tier) || !STATES.includes(value.status)
        || !(value.paid_through === null || (Number.isSafeInteger(value.paid_through)
          && value.paid_through > 0 && value.paid_through <= 8640000000000))) {
        throw new Error(t('billing_bad_response'));
      }
      return value;
    };
    open.addEventListener('click', () => act(open, async () => {
      const named = key;
      const revision = generation;
      const at = moment();
      view = null;
      result.textContent = '';
      panel.hidden = false;
      open.setAttribute('aria-expanded', 'true');
      render();
      const response = await call('GET', '/api/account/billing');
      const value = await receive(response, named, at, revision);
      if (value !== null) { view = value; render(); }
    }));
    period.addEventListener('change', render);
    choices.forEach((button) => button.addEventListener('click', () => act(button, async () => {
      if (view === null || !['free', 'expired'].includes(view.status)) return;
      const named = key;
      const revision = generation;
      const at = moment();
      const response = await call('POST', '/api/account/billing/checkout', {
        key: named, plan: button.dataset.billingPlan, period: period.value,
      });
      if (revision !== generation || getAccount()?.key !== named) return;
      if (response.status === 401) return refusedHere(at);
      if (response.status === 409) return elsewhere(at);
      if (!response.ok) throw new Error(t('account_server_error', { status: response.status }));
      const value = await response.json();
      if (revision !== generation || getAccount()?.key !== named) return;
      let destination;
      try { destination = new URL(value.checkout_url); } catch { throw new Error(t('billing_bad_response')); }
      if (value.status !== 'open' || destination.protocol !== 'https:'
        || destination.host !== 'checkout.stripe.com' || destination.username || destination.password) {
        throw new Error(t('billing_bad_response'));
      }
      window.location.assign(destination.href);
    })));
    cancel.addEventListener('click', () => act(cancel, async () => {
      if (view === null) return;
      const named = key;
      const revision = generation;
      const at = moment();
      const response = await call('POST', '/api/account/billing/cancel', { key: named });
      const value = await receive(response, named, at, revision);
      if (value !== null) {
        view = value;
        render();
        result.textContent = t('billing_cancelled');
      }
    }));
    return { sync, controls };
  };
  window.EC_ACCOUNT_BILLING = { create };
})();
