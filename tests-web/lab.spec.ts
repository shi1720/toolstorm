import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('real Python run exposes duplicate writes and the corrected policy', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/');
  await expect(
    page.getByRole('heading', { name: 'Give your agent a bad day.' }),
  ).toBeVisible();
  await expect(page.getByText('Recorded Python example')).toBeVisible();
  await page
    .getByRole('button', { name: 'Run the storm', exact: true })
    .click();
  await expect(page.getByText('Executed in browser')).toBeVisible({
    timeout: 90000,
  });
  await page.getByRole('tab', { name: 'Contracts', exact: true }).click();
  await expect(
    page.getByText('1 duplicate effect(s) across 2 commits'),
  ).toBeVisible();
  await page.getByRole('button', { name: /03 PASS The realist/ }).click();
  await expect(
    page.getByText('0 duplicate effect(s) across 1 commits'),
  ).toBeVisible();
  await page.getByRole('tab', { name: /Execution trace/ }).click();
  await page.getByRole('button', { name: /create_shipment attempt 1/ }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(
    page.getByText('Committed side effects', { exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Close', exact: true }).click();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export run' }).click();
  const file = await downloadPromise;
  expect(file.suggestedFilename()).toBe('toolstorm-lost_ack-resilient.json');
  const stream = await file.createReadStream();
  expect(stream).not.toBeNull();
  const chunks: Buffer[] = [];
  for await (const chunk of stream!) chunks.push(Buffer.from(chunk));
  const exported = JSON.parse(Buffer.concat(chunks).toString());
  expect(exported.contract.passed).toBe(true);
  expect(exported.stats.effects).toBe(1);
  expect(exported.report.calls).toHaveLength(3);
  expect(errors).toEqual([]);
  await page.screenshot({
    path: 'test-results/toolstorm-desktop.png',
    fullPage: true,
  });
});

test('scenario links, changed configuration and actual fault coverage', async ({
  page,
}) => {
  await page.goto('/?scenario=blackout&seed=1729&policy=resilient');
  await expect(
    page.getByRole('heading', { name: 'The service has left the chat' }),
  ).toBeVisible();
  await expect(page.getByLabel('Random seed', { exact: true })).toHaveValue(
    '1729',
  );
  await expect(page.getByText(/Configuration changed/)).toBeVisible();
  await page
    .getByRole('button', { name: 'Run the storm', exact: true })
    .click();
  await expect(page.getByText('Executed in browser')).toBeVisible({
    timeout: 90000,
  });
  await page.getByRole('tab', { name: 'Contracts', exact: true }).click();
  await expect(page.getByText('Honest outcome', { exact: true })).toBeVisible();
  await page.getByRole('radio', { name: 'Rate limit', exact: true }).check();
  await expect(
    page.getByRole('heading', { name: 'Everybody wants it now' }),
  ).toBeVisible();
  await expect(page.getByText(/Configuration changed/)).toBeVisible();
  await page.getByRole('slider', { name: 'Fault probability' }).focus();
  await page.keyboard.press('Home');
  await page
    .getByRole('button', { name: 'Run the storm', exact: true })
    .click();
  await expect(page.getByText('Triggered 0 time(s)')).toBeVisible();
});

test('docs and recipes navigation work', async ({ page }) => {
  await page.goto('/docs');
  await expect(
    page.getByRole('heading', { name: 'Make failure part of the test.' }),
  ).toBeVisible();
  await page.getByRole('link', { name: 'Recipes', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Pick your failure mode.' }),
  ).toBeVisible();
  await page
    .getByRole('link')
    .filter({ hasText: 'The lost acknowledgement' })
    .click();
  await expect(
    page.getByRole('heading', { name: 'The lost acknowledgement' }),
  ).toBeVisible();
});

test('mobile is usable without page overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(
    page.getByRole('button', { name: 'Run the storm', exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
  await page
    .getByRole('radio', { name: 'Malformed response', exact: true })
    .check();
  await expect(
    page.getByRole('heading', { name: "Looks like JSON. Isn't a contract." }),
  ).toBeVisible();
  await page.screenshot({
    path: 'test-results/toolstorm-mobile.png',
    fullPage: true,
  });
});

test('main pages have no serious or critical accessibility violations', async ({
  page,
}) => {
  const findings: unknown[] = [];
  for (const path of ['/', '/docs', '/recipes']) {
    await page.goto(path);
    const scan = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .analyze();
    const serious = scan.violations.filter(
      (v) => v.impact === 'serious' || v.impact === 'critical',
    );
    findings.push(
      ...serious.map((v) => ({
        path,
        id: v.id,
        nodes: v.nodes.map((n) => ({
          target: n.target,
          summary: n.failureSummary,
        })),
      })),
    );
  }
  expect(findings).toEqual([]);
});
