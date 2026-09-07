import { expect, test, type Page } from '@playwright/test';

const start = (page: Page) =>
  page.getByRole('button', { name: 'Run comparison', exact: true });
const executed = (page: Page) =>
  page.getByText('Executed in your browser', { exact: false });
const retry = (page: Page) => page.getByRole('button', { name: /^Retry\b/i });

async function exportedRun(page: Page) {
  const downloaded = page.waitForEvent('download');
  await page
    .getByRole('button', { name: 'Export selected result', exact: true })
    .click();
  const stream = await (await downloaded).createReadStream();
  expect(stream).not.toBeNull();
  const chunks: Buffer[] = [];
  for await (const chunk of stream!) chunks.push(Buffer.from(chunk));
  return JSON.parse(Buffer.concat(chunks).toString());
}

test('a transient runtime-import failure recovers with a fresh worker', async ({
  page,
  context,
}) => {
  let moduleRequests = 0;
  let workers = 0;
  const errors: string[] = [];
  page.on('worker', () => workers++);
  page.on('pageerror', (error) => errors.push(error.message));
  await context.route('**/runtime/pyodide.mjs', async (route) => {
    moduleRequests++;
    if (moduleRequests === 1) await route.abort('failed');
    else await route.continue();
  });
  await page.goto('/?scenario=lost_ack&seed=31337&policy=resilient');
  await start(page).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await retry(page).click();
  await expect(executed(page)).toBeVisible({ timeout: 90000 });
  await expect(page.getByRole('alert')).toHaveCount(0);
  expect(moduleRequests).toBeGreaterThanOrEqual(2);
  expect(workers).toBeGreaterThanOrEqual(2);
  const output = await exportedRun(page);
  expect(output.config.seed).toBe(31337); // Rules out prerecorded-example substitution.
  expect(output.report.seed).toBe(31337);
  expect(output.policy).toBe('resilient');
  expect(errors).toEqual([]);
});

test('cancelling startup settles the run and the next run can finish', async ({
  page,
  context,
}) => {
  let workers = 0;
  let firstRequest = true;
  let notifyBlocked!: () => void;
  let unblock!: () => void;
  const blocked = new Promise<void>((resolve) => {
    notifyBlocked = resolve;
  });
  const release = new Promise<void>((resolve) => {
    unblock = resolve;
  });
  const errors: string[] = [];
  page.on('worker', () => workers++);
  page.on('pageerror', (error) => errors.push(error.message));
  await context.route('**/runtime/pyodide.mjs', async (route) => {
    if (!firstRequest) {
      await route.continue();
      return;
    }
    firstRequest = false;
    notifyBlocked();
    await release;
    // A terminated worker may already have cancelled this request.
    try {
      await route.abort('aborted');
    } catch {
      /* request already disposed */
    }
  });
  try {
    await page.goto('/?scenario=lost_ack&seed=1729&policy=resilient');
    await start(page).click();
    await blocked;
    await page.getByRole('button', { name: /Cancel/i }).click();
    unblock();
    await expect(start(page)).toBeEnabled();
    // Intentional cancellation should be neutral, not a failed-run alert.
    await expect(page.getByRole('alert')).toHaveCount(0);
    await start(page).click();
    await expect(executed(page)).toBeVisible({ timeout: 90000 });
    expect(workers).toBeGreaterThanOrEqual(2);
    const output = await exportedRun(page);
    expect(output.config.seed).toBe(1729);
    expect(output.contract.passed).toBe(true);
    expect(errors).toEqual([]);
  } finally {
    unblock();
  }
});

test('same-route navigation and browser history reconcile URL configuration', async ({
  page,
}) => {
  await page.goto('/?scenario=blackout&seed=1729&policy=resilient');
  await expect(
    page.getByRole('radio', { name: 'Sustained outage', exact: true }),
  ).toBeChecked();
  await expect(page.getByLabel('Random seed', { exact: true })).toHaveValue(
    '1729',
  );
  await expect(
    page.getByRole('button', { name: /Validated retries/ }),
  ).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('link', { name: 'ToolStorm home', exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(
    page.getByRole('radio', { name: 'Lost acknowledgement', exact: true }),
  ).toBeChecked();
  await expect(page.getByLabel('Random seed', { exact: true })).toHaveValue(
    '42',
  );
  await expect(
    page.getByRole('button', { name: /Unchecked retries/ }),
  ).toHaveAttribute('aria-pressed', 'true');
  await page.goBack();
  await expect(page).toHaveURL(/scenario=blackout/);
  await expect(
    page.getByRole('radio', { name: 'Sustained outage', exact: true }),
  ).toBeChecked();
  await expect(page.getByLabel('Random seed', { exact: true })).toHaveValue(
    '1729',
  );
  await expect(
    page.getByRole('button', { name: /Validated retries/ }),
  ).toHaveAttribute('aria-pressed', 'true');
});

test('failed startup exposes retry within the mobile viewport', async ({
  page,
  context,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await context.route('**/runtime/pyodide.mjs', (route) =>
    route.abort('failed'),
  );
  await page.goto('/');
  await start(page).click();
  await expect(page.getByRole('alert')).toBeInViewport({ ratio: 0.25 });
  await expect(retry(page)).toBeInViewport();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
});

test('without JavaScript the example remains readable and unavailable controls explain why', async ({
  browser,
  baseURL,
}) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  try {
    const page = await context.newPage();
    await page.goto(baseURL!);
    await expect(page.getByRole('main')).toBeVisible();
    await expect(
      page.getByText('Recorded Python example', { exact: false }),
    ).toBeVisible();
    await expect(start(page)).toBeDisabled();
    // Prefer a visible noscript explanation with a link to CLI instructions.
    await expect(page.locator('.noscript-notice')).toContainText(/JavaScript/i);
    await expect(
      page.locator('.noscript-notice').getByRole('link'),
    ).toHaveAttribute('href', /docs/);
    for (const name of ['Copy settings link', 'Export selected result']) {
      const control = page.getByRole('button', { name, exact: true });
      // Hiding unavailable actions is acceptable too.
      if (await control.count()) await expect(control).toBeDisabled();
    }
    await page
      .getByRole('link', { name: 'Documentation', exact: true })
      .click();
    await expect(
      page.getByText('Requires Python 3.10 or newer.', { exact: false }),
    ).toBeVisible();
  } finally {
    await context.close();
  }
});

test('denied clipboard permission still exposes a shareable config URL', async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: async () => {
          throw new DOMException('Denied', 'NotAllowedError');
        },
      },
    });
  });
  await page.goto('/?scenario=latency&seed=123&policy=optimistic');
  await start(page).click();
  await expect(executed(page)).toBeVisible({ timeout: 90000 });
  await page
    .getByRole('button', { name: 'Copy settings link', exact: true })
    .click();
  await expect(page).toHaveURL(
    /scenario=latency&seed=123&p=1&budget=8&policy=optimistic/,
  );
  await expect(page.getByText(/Clipboard unavailable/i)).toBeVisible();
  await page.getByRole('link', { name: 'Documentation', exact: true }).click();
  await page.goBack();
  await expect(
    page.getByRole('radio', { name: 'Slow dependency', exact: true }),
  ).toBeChecked();
  await expect(page.getByLabel('Random seed', { exact: true })).toHaveValue(
    '123',
  );
});

test('a worker timeout settles and allows a new comparison', async ({
  page,
  context,
}) => {
  await page.clock.install();
  let blocked!: () => void;
  let release!: () => void;
  const requested = new Promise<void>((resolve) => {
    blocked = resolve;
  });
  const released = new Promise<void>((resolve) => {
    release = resolve;
  });
  let first = true;
  await context.route('**/runtime/pyodide.mjs', async (route) => {
    if (!first) {
      await route.continue();
      return;
    }
    first = false;
    blocked();
    await released;
    try {
      await route.abort('aborted');
    } catch {
      /* timed-out request */
    }
  });
  try {
    await page.goto('/');
    await start(page).click();
    await requested;
    await page.clock.runFor(90001);
    await expect(page.getByRole('alert')).toContainText('90 seconds');
    release();
    await retry(page).click();
    await expect(executed(page)).toBeVisible({ timeout: 90000 });
  } finally {
    release();
  }
});

test('invalid number drafts do not execute and shared links describe the displayed result', async ({
  page,
}) => {
  await page.addInitScript(() =>
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: async () => {
          throw new Error('denied');
        },
      },
    }),
  );
  await page.goto('/');
  await page.getByLabel('Random seed', { exact: true }).fill('');
  await start(page).click();
  await expect(page.getByRole('alert')).toContainText('whole-number seed');
  await expect(executed(page)).toHaveCount(0);
  await page.getByLabel('Random seed', { exact: true }).fill('123');
  await page.getByLabel('Call limit', { exact: true }).fill('20');
  await page
    .getByRole('button', { name: 'Copy settings link', exact: true })
    .click();
  await expect(page).toHaveURL(/seed=42&p=1&budget=8/);
});

test('clipboard completion cannot replace a later documentation route', async ({
  page,
}) => {
  await page.clock.install();
  await page.addInitScript(() =>
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: () =>
          new Promise<void>((resolve) => setTimeout(resolve, 5000)),
      },
    }),
  );
  await page.goto('/');
  await page
    .getByRole('button', { name: 'Copy settings link', exact: true })
    .click();
  await page.getByRole('link', { name: 'Documentation', exact: true }).click();
  await expect(page).toHaveURL(/\/docs$/);
  await page.clock.runFor(5001);
  await expect(page).toHaveURL(/\/docs$/);
  await expect(
    page.getByRole('heading', { name: 'Test a real recovery path.' }),
  ).toBeVisible();
});

test('Home resets settings after editing, executing and sharing a run', async ({
  page,
}) => {
  await page.goto('/');
  await page.getByLabel('Random seed', { exact: true }).fill('1729');
  await page
    .getByRole('radio', { name: 'Sustained outage', exact: true })
    .check();
  await start(page).click();
  await expect(executed(page)).toBeVisible({ timeout: 90000 });
  await page
    .getByRole('button', { name: 'Copy settings link', exact: true })
    .click();
  await expect(page).toHaveURL(/scenario=blackout&seed=1729/);
  await page.getByRole('link', { name: 'ToolStorm home', exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByLabel('Random seed', { exact: true })).toHaveValue(
    '42',
  );
  await expect(
    page.getByRole('radio', { name: 'Lost acknowledgement', exact: true }),
  ).toBeChecked();
});
