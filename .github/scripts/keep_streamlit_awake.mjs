import { chromium } from 'playwright';

const targetUrl = process.env.STREAMLIT_APP_URL;
const appHeadingPattern = /영화 리뷰 감성 분석/;
const wakeButtonPattern = /(?:yes,?\s*)?(?:get this app back up|wake (?:this app )?up)/i;
const loadTimeoutMs = 120_000;

if (!targetUrl) {
  throw new Error('STREAMLIT_APP_URL 환경 변수가 필요합니다.');
}

function assertPublicApp(page) {
  const currentUrl = new URL(page.url());
  const isAuthPage =
    (currentUrl.hostname === 'share.streamlit.io' &&
      currentUrl.pathname.includes('/auth/')) ||
    currentUrl.pathname.startsWith('/-/login');

  if (isAuthPage) {
    throw new Error(
      `Streamlit 인증 페이지로 이동했습니다: ${logSafeUrl(currentUrl)}\n` +
        'keep-alive를 실행하려면 Streamlit Community Cloud에서 앱을 Public으로 설정해야 합니다.',
    );
  }
}

function logSafeUrl(url) {
  const parsedUrl = url instanceof URL ? url : new URL(url);
  return `${parsedUrl.origin}${parsedUrl.pathname}`;
}

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

try {
  console.log(`Streamlit 앱 접속: ${logSafeUrl(targetUrl)}`);
  await page.goto(targetUrl, {
    waitUntil: 'domcontentloaded',
    timeout: 60_000,
  });

  const appFrame = page.frameLocator('iframe[title="streamlitApp"]');
  const topLevelContainer = page.locator('[data-testid="stAppViewContainer"]').first();
  const topLevelHeading = page.getByRole('heading', { name: appHeadingPattern }).first();
  const iframeHeading = appFrame.getByRole('heading', { name: appHeadingPattern }).first();
  const wakeButton = page.getByRole('button', { name: wakeButtonPattern }).first();
  const deadline = Date.now() + loadTimeoutMs;
  let wakeClicked = false;
  let readyMode = null;

  async function detectReadyMode() {
    const [hasTopLevelContainer, hasTopLevelHeading] = await Promise.all([
      topLevelContainer.isVisible().catch(() => false),
      topLevelHeading.isVisible().catch(() => false),
    ]);

    if (hasTopLevelContainer && hasTopLevelHeading) {
      return 'top-level';
    }

    if (await iframeHeading.isVisible().catch(() => false)) {
      return 'iframe';
    }

    return null;
  }

  while (Date.now() < deadline) {
    assertPublicApp(page);
    readyMode = await detectReadyMode();

    if (readyMode) {
      console.log(`앱 정상 로딩 확인(${readyMode}): ${logSafeUrl(page.url())}`);
      break;
    }

    if (!wakeClicked && (await wakeButton.isVisible().catch(() => false))) {
      console.log('sleep 화면을 감지해 wake 버튼을 클릭합니다.');
      await wakeButton.click();
      wakeClicked = true;
    }

    await page.waitForTimeout(2_000);
  }

  assertPublicApp(page);

  if (!readyMode) {
    throw new Error(
      `${loadTimeoutMs / 1000}초 안에 앱 정상 로딩을 확인하지 못했습니다. 최종 URL: ${logSafeUrl(page.url())}`,
    );
  }
} finally {
  await browser.close();
}
