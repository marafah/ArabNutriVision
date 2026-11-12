/* ArabNutriVision static edition: Supabase connection and sign-in state.
   The project URL and the public (anon / publishable) key are injected at build time from the
   repository variables SUPABASE_URL and SUPABASE_ANON_KEY. They are public by design; every table is
   protected by row-level security so a researcher can only read and write their own rows. */
(function () {
  const C = window.ANV_CFG || {};
  const configured = !!(C.url && C.key && window.supabase);
  const sb = configured ? window.supabase.createClient(C.url, C.key, {auth: {persistSession: true, storageKey: "anv-auth"}}) : null;

  /** Short display name: the registered full name, else the e-mail's local part ("mohammad_arafah" -> "Mohammad Arafah"). */
  function displayName(user) {
    if (!user) return "";
    const full = user.user_metadata && user.user_metadata.full_name;
    if (full) return full.trim();
    return (user.email || "").split("@")[0].replace(/[._-]+/g, " ").replace(/\b\w/g, c => c.toUpperCase()).trim();
  }
  const initials = n => n.split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join("").toUpperCase();

  function show(user) {
    document.querySelectorAll("[data-auth]").forEach(el => {
      el.hidden = (el.dataset.auth === "in") !== !!user;
    });
    const u = document.getElementById("anvUser");
    if (u) { const n = displayName(user); u.textContent = initials(n); u.title = user ? `${n} · ${user.email}` : ""; u.setAttribute("aria-label", u.title); }
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

  window.ANVCloud = {sb, configured, ready, requireUser, cfg: C, displayName};
})();
