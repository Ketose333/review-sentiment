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
    currentUrl.hostname === 'share.streamlit.io' &&
    currentUrl.pathname.includes('/auth/');

  if (isAuthPage) {
    throw new Error(
      `Streamlit 인증 페이지로 이동했습니다: ${currentUrl.href}\n` +
        'keep-alive를 실행하려면 Streamlit Community Cloud에서 앱을 Public으로 설정해야 합니다.',
    );
  }
}

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

try {
  console.log(`Streamlit 앱 접속: ${targetUrl}`);
  await page.goto(targetUrl, {
    waitUntil: 'domcontentloaded',
    timeout: 60_000,
  });

  const appFrame = page.frameLocator('iframe[title="streamlitApp"]');
  const heading = appFrame.getByRole('heading', { name: appHeadingPattern });
  const wakeButton = page.getByRole('button', { name: wakeButtonPattern }).first();
  const deadline = Date.now() + loadTimeoutMs;
  let wakeClicked = false;

  while (Date.now() < deadline) {
    assertPublicApp(page);

    if (await heading.isVisible().catch(() => false)) {
      console.log(`앱 정상 로딩 확인: ${page.url()}`);
      process.exitCode = 0;
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

  if (!(await heading.isVisible().catch(() => false))) {
    throw new Error(
      `${loadTimeoutMs / 1000}초 안에 앱 정상 로딩을 확인하지 못했습니다. 최종 URL: ${page.url()}`,
    );
  }
} finally {
  await browser.close();
}
