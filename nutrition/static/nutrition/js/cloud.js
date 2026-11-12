/* ArabNutriVision static edition: Supabase connection and sign-in state.
   The project URL and the public (anon / publishable) key are injected at build time from the
   repository variables SUPABASE_URL and SUPABASE_ANON_KEY. They are public by design; every table is
   protected by row-level security so a researcher can only read and write their own rows. */
(function () {
  const C = window.ANV_CFG || {};
  const configured = !!(C.url && C.key && window.supabase);
  const sb = configured ? window.supabase.createClient(C.url, C.key, {auth: {persistSession: true, storageKey: "anv-auth"}}) : null;

  function show(user) {
    document.querySelectorAll("[data-auth]").forEach(el => {
      el.hidden = (el.dataset.auth === "in") !== !!user;
    });
    const u = document.getElementById("anvUser");
    if (u) u.textContent = user ? user.email : "";
  }

  const ready = (async () => {
    if (!sb) { show(null); return null; }
    const {data} = await sb.auth.getSession();
    const user = data.session ? data.session.user : null;
    show(user);
    return user;
  })();

  if (sb) sb.auth.onAuthStateChange((_e, session) => show(session ? session.user : null));

  const out = document.getElementById("anvSignOut");
  if (out) out.onclick = async () => { if (sb) await sb.auth.signOut(); location.href = C.home; };

  /** Pages that need a researcher: send anonymous visitors to the sign-in page. */
  async function requireUser() {
    const user = await ready;
    if (!user) {
      const next = location.pathname + location.search;
      location.replace(C.login + "?next=" + encodeURIComponent(next));
      throw new Error("not signed in");
    }
    return user;
  }

  window.ANVCloud = {sb, configured, ready, requireUser, cfg: C};
})();
