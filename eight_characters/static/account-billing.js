// Private sandbox controls. The server owns offer terms, payment and renewal state.
(() => {
  const TIERS = ['free', 'basic', 'plus', 'pro'];
  const STATES = ['free', 'paid', 'pending', 'held', 'expired', 'deleting', 'deleted'];
  const PERIODS = ['monthly', 'yearly'];
  const offerOf = (offer) => offer !== null && typeof offer === 'object'
    && TIERS.slice(1).includes(offer.plan) && PERIODS.includes(offer.period)
    && offer.currency === 'usd' && Number.isSafeInteger(offer.amount_minor) && offer.amount_minor > 0;
  const create = ({ dialog, translate: t, language, act, call, moment, getAccount, refusedHere, elsewhere }) => {
    const part = (id) => {
      const value = dialog.querySelector(`#account-billing${id}`);
      if (!value) throw new Error(`Missing billing control: ${id}`);
      return value;
    };
    const enabled = dialog.dataset.billingEnabled;
    if (!['true', 'false'].includes(enabled)) throw new Error('Missing billing availability.');
    const open = part('-open'), panel = part(''), summary = part('-summary');
    const offers = part('-offers'), period = part('-period'), cancel = part('-cancel');
    const result = part('-result'), renewal = part('-renewal'), pending = part('-pending');
    const resume = part('-resume');
    const choices = [...panel.querySelectorAll('[data-billing-plan]')];
    const controls = [open, period, ...choices, resume, cancel];
    let key = null, view = null, generation = 0;
    let returnRequested = enabled === 'true' && location.hash === '#plan';
    const date = (value) => new Intl.DateTimeFormat(language(), { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' })
      .format(new Date(value * 1000));
    const quote = (offer) => t('billing_buy', {
      tier: t(`billing_tier_${offer.plan}`),
      price: new Intl.NumberFormat(language(), { style: 'currency', currency: offer.currency, currencyDisplay: 'code' }).format(offer.amount_minor / 100),
      period: t(`billing_per_${offer.period}`),
    });
    const canBuy = () => view !== null && ['free', 'expired'].includes(view.status)
      && view.renewal === 'none' && view.pending === null;
    const canResume = () => view !== null && view.pending !== null && !['deleting', 'deleted'].includes(view.status);
    const render = () => {
      summary.textContent = view === null ? '' : t('billing_summary', {
        tier: t(`billing_tier_${view.tier}`), status: t(`billing_state_${view.status}`),
      });
      if (view?.paid_through != null) summary.textContent += ` · ${t('billing_paid_through', { date: date(view.paid_through) })}`;
      renewal.textContent = view === null ? '' : t(`billing_renewal_${view.renewal}`);
      pending.textContent = view?.pending ? `${quote(view.pending)} · ${t('billing_pending_until', { date: date(view.pending.expires_at) })}` : '';
      offers.hidden = !canBuy();
      resume.hidden = !canResume();
      cancel.hidden = view?.renewal !== 'active';
      choices.forEach((button) => {
        const offer = view?.offers.find((offer) => offer.plan === button.dataset.billingPlan && offer.period === period.value);
        button.textContent = offer ? quote(offer) : '';
      });
    };
    const clear = () => {
      generation += 1;
      view = null;
      panel.hidden = true;
      open.setAttribute('aria-expanded', 'false');
      result.textContent = '';
      render();
    };
    const sync = (account) => {
      if (key !== (account?.key ?? null)) { key = account?.key ?? null; clear(); }
      open.hidden = enabled !== 'true' || account === null;
      render();
    };
    const current = (named, revision) => generation === revision && getAccount()?.key === named;
    const receive = async (response, named, at, revision) => {
      if (!current(named, revision)) return null;
      if (response.status === 401) { await refusedHere(at); return null; }
      if (!response.ok) throw new Error(t('account_server_error', { status: response.status }));
      const value = await response.json();
      if (!current(named, revision)) return null;
      if (value === null || typeof value !== 'object' || typeof value.key !== 'string' || !/^[0-9a-f]{64}$/.test(value.key)) {
        throw new Error(t('billing_bad_response'));
      }
      if (value.key !== named) { await elsewhere(at); return null; }
      if (!TIERS.includes(value.tier) || !STATES.includes(value.status)
        || !(value.paid_through === null || (Number.isSafeInteger(value.paid_through) && value.paid_through > 0 && value.paid_through <= 8640000000000))
        || !['active', 'stopping', 'none', 'unverified'].includes(value.renewal)
        || !Array.isArray(value.offers) || value.offers.length !== 6 || !value.offers.every(offerOf)
        || new Set(value.offers.map((offer) => `${offer.plan}/${offer.period}`)).size !== 6
        || !(value.pending === null || (offerOf(value.pending) && Number.isSafeInteger(value.pending.expires_at)
          && value.pending.expires_at > 0 && value.pending.expires_at <= 8640000000000))) {
        throw new Error(t('billing_bad_response'));
      }
      return value;
    };
    const load = async () => {
      const named = key, revision = generation, at = moment();
      view = null;
      result.textContent = '';
      panel.hidden = false;
      open.setAttribute('aria-expanded', 'true');
      render();
      const response = await call('GET', '/api/account/billing');
      const value = await receive(response, named, at, revision);
      if (value !== null) { view = value; render(); }
      return value;
    };
    open.addEventListener('click', () => act(open, load));
    period.addEventListener('change', render);
    dialog.addEventListener('close', clear);
    const checkout = async (offer) => {
      const named = key, revision = generation, at = moment();
      const response = await call('POST', '/api/account/billing/checkout', { key: named, plan: offer.plan, period: offer.period });
      if (!current(named, revision)) return;
      if (response.status === 401) return refusedHere(at);
      if (response.status === 409) {
        if (await load() !== null) result.textContent = t('billing_existing');
        return;
      }
      if (!response.ok) throw new Error(t('account_server_error', { status: response.status }));
      const value = await response.json();
      if (!current(named, revision)) return;
      if (['complete', 'expired'].includes(value.status)) {
        if (await load() !== null) result.textContent = t(`billing_checkout_${value.status}`);
        return;
      }
      let destination;
      try { destination = new URL(value.checkout_url); } catch { throw new Error(t('billing_bad_response')); }
      if (value.status !== 'open' || destination.protocol !== 'https:' || destination.host !== 'checkout.stripe.com' || destination.username || destination.password) {
        throw new Error(t('billing_bad_response'));
      }
      window.location.assign(destination.href);
    };
    choices.forEach((button) => button.addEventListener('click', () => act(button, async () => {
      if (!canBuy()) return;
      const offer = view.offers.find((offer) => offer.plan === button.dataset.billingPlan && offer.period === period.value);
      if (!offer) throw new Error(t('billing_bad_response'));
      await checkout(offer);
    })));
    resume.addEventListener('click', () => act(resume, async () => {
      if (canResume()) await checkout(view.pending);
    }));
    cancel.addEventListener('click', () => act(cancel, async () => {
      if (view?.renewal !== 'active') return;
      const named = key, revision = generation, at = moment();
      const response = await call('POST', '/api/account/billing/cancel', { key: named });
      const value = await receive(response, named, at, revision);
      if (value !== null) {
        view = value; render();
        if (!['stopping', 'none'].includes(view.renewal)) throw new Error(t('billing_bad_response'));
        result.textContent = t('billing_cancelled');
      }
    }));
    return {
      sync, controls, wantsReturn: () => returnRequested,
      resumeReturn: () => {
        if (returnRequested && getAccount() !== null) { returnRequested = false; open.click(); }
      },
    };
  };
  window.EC_ACCOUNT_BILLING = { create };
})();
