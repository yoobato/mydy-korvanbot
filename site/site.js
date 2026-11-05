(() => {
  const current = document.documentElement.lang;
  const base = new URL('.', document.currentScript.src);
  const url = new URL(window.location.href);
  const requested = url.searchParams.get('lang');
  const explicit = requested === 'ko' || requested === 'en';
  let saved = null;
  try {
    if (explicit) localStorage.setItem('korvanbot-language', requested);
    saved = localStorage.getItem('korvanbot-language');
  } catch { /* Manual links remain usable when storage is unavailable. */ }
  const system = (navigator.languages?.[0] || navigator.language || 'en').toLowerCase().startsWith('ko') ? 'ko' : 'en';
  // Direct /en/ links stay English. At the root, use an explicit choice, saved choice, then browser language.
  const preferred = explicit ? requested : current === 'en' ? 'en' : (saved === 'ko' || saved === 'en' ? saved : system);
  if (preferred !== current) {
    const destination = new URL(preferred === 'en' ? 'en/' : './', base);
    destination.search = url.search;
    destination.hash = url.hash;
    window.location.replace(destination.href);
    return;
  }
  if (explicit) {
    url.searchParams.delete('lang');
    history.replaceState(null, '', url.pathname + url.search + url.hash);
  }
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.telegram-embed').forEach(embed => {
      const preview = embed.closest('.telegram-preview');
      let renderedPost = null;
      let refreshing = false;
      const validPost = post => typeof post === 'string' && /^korea_vancouver\/[1-9]\d{0,15}$/.test(post);
      const updateLinks = post => {
        preview.querySelectorAll('a[data-preview-link]').forEach(link => {
          link.href = 'https://t.me/' + post;
        });
      };
      const render = post => {
        if (!validPost(post) || renderedPost === post) return;
        renderedPost = post;
        updateLinks(post);
        const fallback = document.createElement('blockquote');
        fallback.className = 'telegram-post';
        fallback.dataset.telegramPost = post;
        fallback.dataset.width = '100%';
        fallback.dataset.userpic = 'false';
        const link = preview.querySelector('a[data-preview-link]').cloneNode(true);
        fallback.append(link);
        const script = document.createElement('script');
        script.async = true;
        script.src = 'https://telegram.org/js/telegram-widget.js?22';
        script.onerror = () => { renderedPost = null; };
        embed.replaceChildren(fallback, script);
      };
      const labelFrame = () => {
        const frame = embed.querySelector('iframe');
        if (frame) frame.title = embed.dataset.frameTitle;
      };
      const observer = new MutationObserver(labelFrame);
      observer.observe(embed, { childList: true });
      const refresh = async () => {
        if (refreshing) return;
        refreshing = true;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 4000);
        try {
          const response = await fetch(embed.dataset.latestUrl, {
            cache: 'no-store', credentials: 'omit', signal: controller.signal
          });
          if (!response.ok) throw new Error('Preview unavailable');
          const data = await response.json();
          if (!validPost(data.post)) throw new Error('Invalid public post');
          render(data.post);
        } catch {
          if (!renderedPost) render(embed.dataset.fallbackPost);
        } finally {
          clearTimeout(timeout);
          refreshing = false;
        }
      };
      refresh();
      setInterval(() => {
        if (document.visibilityState === 'visible') refresh();
      }, 60000);
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') refresh();
      });
    });
    document.querySelectorAll('.technical-details').forEach(details => {
      const summary = details.querySelector('summary');
      let animation = null;
      let targetOpen = details.open;
      summary.addEventListener('click', event => {
        event.preventDefault();
        targetOpen = !(animation ? targetOpen : details.open);
        const start = details.getBoundingClientRect().height;
        if (animation) animation.cancel();
        animation = null;
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches || !details.animate) {
          details.open = targetOpen;
          details.style.overflow = '';
          return;
        }
        details.open = true;
        const style = getComputedStyle(details);
        const border = parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth);
        const end = targetOpen ? details.scrollHeight + border : summary.getBoundingClientRect().height + border;
        details.style.overflow = 'hidden';
        const active = details.animate([{ height: start + 'px' }, { height: end + 'px' }], {
          duration: 300, easing: 'cubic-bezier(.2,.7,.3,1)', fill: 'both'
        });
        animation = active;
        active.onfinish = () => {
          if (animation !== active) return;
          details.open = targetOpen;
          active.cancel();
          animation = null;
          details.style.overflow = '';
        };
      });
    });
    if (!('IntersectionObserver' in window) || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    document.documentElement.classList.add('enhanced-motion');
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      }
    }, { threshold: 0.12 });
    document.querySelectorAll('.reveal').forEach(element => observer.observe(element));
  });
})();
