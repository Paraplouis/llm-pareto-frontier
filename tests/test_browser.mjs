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

  // Collect console errors
  const consoleErrors = [];
  const consoleWarnings = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
    if (msg.type() === 'warning') consoleWarnings.push(msg.text());
  });

  // Collect page errors (uncaught exceptions)
  const pageErrors = [];
  page.on('pageerror', (err) => pageErrors.push(err.message));

  // Collect failed network requests
  const failedRequests = [];
  page.on('requestfailed', (req) =>
    failedRequests.push(`${req.url()} - ${req.failure().errorText}`)
  );

  console.log('\n=== Loading page ===');
  await page.goto(BASE_URL, { waitUntil: 'networkidle0', timeout: 15000 });

  // --- Basic page load ---
  console.log('\n--- Page Load ---');
  const title = await page.title();
  assert(title.length > 0, `Page has title: "${title}"`);

  // --- Console errors ---
  console.log('\n--- Console Errors ---');
  assert(consoleErrors.length === 0, `No console errors (found ${consoleErrors.length})`);
  for (const err of consoleErrors) console.log(`    ERROR: ${err}`);

  assert(pageErrors.length === 0, `No uncaught exceptions (found ${pageErrors.length})`);
  for (const err of pageErrors) console.log(`    EXCEPTION: ${err}`);

  assert(failedRequests.length === 0, `No failed network requests (found ${failedRequests.length})`);
  for (const req of failedRequests) console.log(`    FAILED: ${req}`);

  // --- SVG chart rendered ---
  console.log('\n--- Chart Rendering ---');
  const svgExists = await page.$('svg');
  assert(svgExists !== null, 'SVG chart element exists');

  const circleCount = await page.$$eval('svg circle', (els) => els.length);
  assert(circleCount > 10, `Chart has data points rendered (${circleCount} circles)`);

  const axisLabels = await page.$$eval('svg .axis-label', (els) => els.map((e) => e.textContent));
  assert(axisLabels.length >= 2, `Axis labels present (${axisLabels.join(', ')})`);

  // --- Pareto frontier line ---
  const paretoPath = await page.$('svg .pareto-path');
  assert(paretoPath !== null, 'Pareto frontier line rendered');

  // --- Legend ---
  console.log('\n--- UI Elements ---');
  const legendItems = await page.$$eval('.legend-item', (els) => els.length);
  assert(legendItems > 5, `Legend has organization entries (${legendItems} items)`);

  // --- Pareto info section ---
  const paretoInfo = await page.$('.pareto-models');
  assert(paretoInfo !== null, 'Pareto info section exists');

  const paretoModels = await page.$$eval('.pareto-model', (els) => els.length);
  assert(paretoModels > 0, `Pareto models listed (${paretoModels} models)`);

  // --- Token ratio controls ---
  const inputTokens = await page.$('#input-tokens');
  assert(inputTokens !== null, 'Input tokens control exists');

  const outputTokens = await page.$('#output-tokens');
  assert(outputTokens !== null, 'Output tokens control exists');

  // --- Preset buttons ---
  const presetButtons = await page.$$eval('.preset-button', (els) => els.length);
  assert(presetButtons >= 4, `Preset buttons present (${presetButtons} buttons)`);

  // --- Theme toggle ---
  const themeToggle = await page.$('.theme-toggle-button');
  assert(themeToggle !== null, 'Theme toggle button exists');

  // --- Interactive test: click a preset button ---
  console.log('\n--- Interactions ---');
  const firstPreset = await page.$('.preset-button');
  if (firstPreset) {
    await firstPreset.click();
    await delay(500);
    const circlesAfterPreset = await page.$$eval('svg circle', (els) => els.length);
    assert(circlesAfterPreset > 0, `Chart still renders after preset click (${circlesAfterPreset} circles)`);
  }

  // --- Interactive test: toggle theme ---
  if (themeToggle) {
    await themeToggle.click();
    await delay(300);
    const isDark = await page.$eval('body', (el) => el.classList.contains('dark-mode'));
    assert(typeof isDark === 'boolean', `Theme toggle works (dark mode: ${isDark})`);

    // Toggle back
    await themeToggle.click();
    await delay(300);
  }

  // --- Interactive test: toggle a legend item ---
  const firstLegendItem = await page.$('.legend-item');
  if (firstLegendItem) {
    const circlesBefore = await page.$$eval('svg circle', (els) => els.length);
    await firstLegendItem.click();
    await delay(500);
    const circlesAfterToggle = await page.$$eval('svg circle', (els) => els.length);
    assert(
      circlesAfterToggle < circlesBefore,
      `Legend filter works (${circlesBefore} → ${circlesAfterToggle} circles)`
    );

    // Click again to restore (re-query since DOM may have been rebuilt)
    const restoredLegendItem = await page.$('.legend-item');
    if (restoredLegendItem) {
      await restoredLegendItem.click();
      await delay(500);
    }
  }

  // --- Tooltip test: hover on a circle ---
  const firstCircle = await page.$('svg circle');
  if (firstCircle) {
    await firstCircle.hover();
    await delay(300);
    const tooltip = await page.$('.tooltip');
    const tooltipVisible = tooltip
      ? await page.$eval('.tooltip', (el) => el.style.opacity !== '0' && el.style.display !== 'none')
      : false;
    assert(tooltipVisible, 'Tooltip appears on hover');
  }

  // --- Responsive: mobile viewport ---
  console.log('\n--- Responsive ---');
  await page.setViewport({ width: 375, height: 667 });
  await delay(500);
  const mobileSvg = await page.$('svg');
  assert(mobileSvg !== null, 'Chart renders at mobile viewport (375px)');

  const mobileCircles = await page.$$eval('svg circle', (els) => els.length);
  assert(mobileCircles > 0, `Mobile chart has data points (${mobileCircles} circles)`);

  // Reset viewport
  await page.setViewport({ width: 1280, height: 900 });
  await delay(500);

  // --- Screenshot ---
  await page.screenshot({ path: 'tests/screenshot_test.png', fullPage: true });
  console.log('\n  📸 Screenshot saved to tests/screenshot_test.png');

  // --- Console warnings (informational) ---
  if (consoleWarnings.length > 0) {
    console.log(`\n--- Console Warnings (${consoleWarnings.length}) ---`);
    for (const w of consoleWarnings) console.log(`    WARN: ${w}`);
  }

  // --- Summary ---
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
