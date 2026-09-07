const API_BASE_URL = "https://d6a26160fio9p.cloudfront.net"
// const API_BASE_URL = "http://127.0.0.1:8000"

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
        <a href="https://github.com/Brownian-Motion-99/threads-backup.git">GitHub</a>
      </div>
      <p class="footer-meta">© 2026 brownian.motion.99 · v2026.09</p>
    </footer>
  `;
}

/**
 * Return the HTML for the loading overlay used during initial data fetch.
 */
function renderLoadingOverlay() {
  return `
    <div id="loading-overlay" class="loading-overlay">
      <div class="loading-spinner"></div>
      <p id="loading-message" class="loading-message">載入中...</p>
    </div>
  `;
}

let loadingMessageTimer = null;

/**
 * Show the loading overlay and schedule a follow-up message in case
 * the wait is caused by a serverless database cold start.
 */
function showLoadingOverlay() {
  const overlay = document.getElementById("loading-overlay");
  if (!overlay) return;
  overlay.classList.remove("hidden");
  setLoadingMessage("載入中...");

  loadingMessageTimer = setTimeout(() => {
    setLoadingMessage("首次載入可能需要多等一下，資料庫正在啟動中...");
  }, 4000);
}

/**
 * Hide the loading overlay and cancel any pending message timer.
 */
function hideLoadingOverlay() {
  clearTimeout(loadingMessageTimer);
  const overlay = document.getElementById("loading-overlay");
  if (overlay) overlay.classList.add("hidden");
}

/**
 * Switch the overlay into an error state with a retry button.
 *
 * @param {Function} retryFn - called when the user clicks retry
 */
function showLoadingError(retryFn) {
  clearTimeout(loadingMessageTimer);
  setLoadingMessage("連線失敗，請確認網路狀況後重試。");
}

function setLoadingMessage(text) {
  const el = document.getElementById("loading-message");
  if (el) el.textContent = text;
}