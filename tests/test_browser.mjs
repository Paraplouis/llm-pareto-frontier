/**
 * Headless browser test for the LLM Pareto Frontier site.
 * Requires: puppeteer and Google Chrome
 * Usage: node tests/test_browser.mjs
 */

import puppeteer from 'puppeteer';

const BASE_URL = 'http://localhost:8000';
const results = { passed: 0, failed: 0, errors: [] };
const delay = (ms) => new Promise((r) => setTimeout(r, ms));

function assert(condition, message) {
  if (condition) {
    results.passed++;
    console.log(`  ✓ ${message}`);
  } else {
    results.failed++;
    results.errors.push(message);
    console.log(`  ✗ ${message}`);
  }
}

async function run() {
  const browser = await puppeteer.launch({
    headless: true,
    executablePath: '/usr/bin/google-chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });

  const consoleErrors = [];
  const consoleWarnings = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
    if (msg.type() === 'warning') consoleWarnings.push(msg.text());
  });

  const pageErrors = [];
  page.on('pageerror', (err) => pageErrors.push(err.message));

  const failedRequests = [];
  page.on('requestfailed', (req) =>
    failedRequests.push(`${req.url()} - ${req.failure().errorText}`)
  );

  console.log('\n=== Loading page ===');
  await page.goto(BASE_URL, { waitUntil: 'networkidle0', timeout: 15000 });

  console.log('\n--- Page Load ---');
  const title = await page.title();
  assert(title.length > 0, `Page has title: "${title}"`);

  console.log('\n--- Console Errors ---');
  assert(consoleErrors.length === 0, `No console errors (found ${consoleErrors.length})`);
  for (const err of consoleErrors) console.log(`    ERROR: ${err}`);

  assert(pageErrors.length === 0, `No uncaught exceptions (found ${pageErrors.length})`);
  for (const err of pageErrors) console.log(`    EXCEPTION: ${err}`);

  assert(failedRequests.length === 0, `No failed network requests (found ${failedRequests.length})`);
  for (const req of failedRequests) console.log(`    FAILED: ${req}`);

  console.log('\n--- Chart Rendering ---');
  const svgExists = await page.$('svg');
  assert(svgExists !== null, 'SVG chart element exists');

  const circleCount = await page.$$eval('svg circle', (els) => els.length);
  assert(circleCount > 10, `Chart has data points rendered (${circleCount} circles)`);

  const axisLabels = await page.$$eval('svg .axis-title', (els) => els.map((e) => e.textContent));
  assert(axisLabels.length >= 2, `Axis labels present (${axisLabels.join(', ')})`);

  const paretoPath = await page.$('svg .frontier-line');
  assert(paretoPath !== null, 'Pareto frontier line rendered');

  console.log('\n--- UI Elements ---');
  const orgOptions = await page.$$eval('.org-option', (els) => els.length);
  assert(orgOptions > 5, `Organization filter has entries (${orgOptions} items)`);

  const frontierModels = await page.$$eval('.frontier-item', (els) => els.length);
  assert(frontierModels > 0, `Frontier models listed (${frontierModels} models)`);

  const tableRows = await page.$$eval('#model-table tbody tr', (els) => els.length);
  assert(tableRows > 10, `Model table has rows (${tableRows} rows)`);

  const inputTokens = await page.$('#input-tokens');
  assert(inputTokens !== null, 'Input tokens control exists');

  const outputTokens = await page.$('#output-tokens');
  assert(outputTokens !== null, 'Output tokens control exists');

  const presetButtons = await page.$$eval('.preset-button', (els) => els.length);
  assert(presetButtons >= 4, `Preset buttons present (${presetButtons} buttons)`);

  const themeToggle = await page.$('.theme-toggle-button');
  assert(themeToggle !== null, 'Theme toggle button exists');

  console.log('\n--- Interactions ---');
  const firstPreset = await page.$('.preset-button');
  if (firstPreset) {
    await firstPreset.click();
    await delay(500);
    const circlesAfterPreset = await page.$$eval('svg circle', (els) => els.length);
    assert(circlesAfterPreset > 0, `Chart still renders after preset click (${circlesAfterPreset} circles)`);
  }

  if (themeToggle) {
    await themeToggle.click();
    await delay(300);
    const theme = await page.$eval('html', (el) => el.dataset.theme);
    assert(theme === 'dark' || theme === 'light', `Theme toggle works (theme: ${theme})`);

    await themeToggle.click();
    await delay(300);
  }

  await page.click('.org-filter summary');
  const firstOrgCheckbox = await page.$('.org-option input');
  if (firstOrgCheckbox) {
    const circlesBefore = await page.$$eval('svg circle', (els) => els.length);
    await firstOrgCheckbox.click();
    await delay(500);
    const circlesAfterToggle = await page.$$eval('svg circle', (els) => els.length);
    assert(
      circlesAfterToggle < circlesBefore,
      `Organization filter works (${circlesBefore} → ${circlesAfterToggle} circles)`
    );

    await firstOrgCheckbox.click();
    await delay(500);
  }
  await page.click('.org-filter summary');

  await page.type('#model-search', 'gemini');
  await delay(300);
  const matchCount = await page.$$eval('svg .dot.match', (els) => els.length);
  assert(matchCount > 0, `Search highlights matching models (${matchCount} matches)`);
  await page.$eval('#model-search', (el) => {
    el.value = '';
    el.dispatchEvent(new Event('input'));
  });

  const firstCircle = await page.$('svg .dot');
  if (firstCircle) {
    await firstCircle.hover();
    await delay(300);
    const tooltipVisible = await page.$eval('#tooltip', (el) => !el.hidden);
    assert(tooltipVisible, 'Tooltip appears on hover');
  }

  console.log('\n--- Responsive ---');
  await page.setViewport({ width: 375, height: 667 });
  await delay(500);
  const mobileSvg = await page.$('svg');
  assert(mobileSvg !== null, 'Chart renders at mobile viewport (375px)');

  const mobileCircles = await page.$$eval('svg circle', (els) => els.length);
  assert(mobileCircles > 0, `Mobile chart has data points (${mobileCircles} circles)`);

  await page.setViewport({ width: 1280, height: 900 });
  await delay(500);

  await page.screenshot({ path: 'tests/screenshot_test.png', fullPage: true });
  console.log('\n  📸 Screenshot saved to tests/screenshot_test.png');

  if (consoleWarnings.length > 0) {
    console.log(`\n--- Console Warnings (${consoleWarnings.length}) ---`);
    for (const w of consoleWarnings) console.log(`    WARN: ${w}`);
  }

  console.log('\n============================');
  console.log(`  PASSED: ${results.passed}`);
  console.log(`  FAILED: ${results.failed}`);
  console.log('============================\n');

  if (results.failed > 0) {
    console.log('Failed tests:');
    for (const e of results.errors) console.log(`  ✗ ${e}`);
  }

  await browser.close();
  process.exit(results.failed > 0 ? 1 : 0);
}

run().catch((err) => {
  console.error('Test runner error:', err);
  process.exit(1);
});
