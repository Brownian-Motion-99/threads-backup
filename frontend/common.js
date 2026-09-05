function renderMedia(url) {
  if (url.endsWith(".mp4")) {
    return `<video src="${url}" controls class="post-media"></video>`;
  } else {
    return `<img src="${url}" class="post-media">`;
  }
}

function renderMediaList(urls) {
  return urls.map(renderMedia).join("");
}

function getThumbnailUrl(images) {
  if (images.length === 0) {
    return "default.jpg"
  };
  const first = images[0];
  if (first.endsWith(".mp4")) {
    return first.replace(".mp4", ".jpg");
  }
  return first;
}

function renderThumbnail(images) {
  const url = getThumbnailUrl(images);
  return `<img src="${url}" class="post-thumbnail">`;
}

function renderFooter() {
  return `
    <footer class="site-footer">
      <div class="footer-links">
        <a href="https://www.threads.com/@brownian.motion.99" target="_blank">Threads</a>
        <a href="mailto:chunhaoc777@gmail.com">Email</a>
        <a href="#" class="footer-link-disabled" title="尚未公開">GitHub</a>
      </div>
      <p class="footer-meta">© 2026 brownian.motion.99 · v2026.08</p>
    </footer>
  `;
}