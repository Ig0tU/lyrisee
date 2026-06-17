const { test, expect } = require('@playwright/test');

test('Plot layer interaction', async ({ page }) => {
  await page.goto('file://' + process.cwd() + '/index.html');

  // Force intro to hide
  await page.evaluate(() => {
    document.getElementById('intro').style.display = 'none';
    document.getElementById('stage').classList.add('playing');
  });

  await page.waitForTimeout(1000);

  // Open editor
  await page.click('#editBtn');
  await page.waitForSelector('.ed-row', { state: 'visible' });

  // Add line to make sure there's an editable row
  await page.click('#edAdd');
  const rows = await page.$$('.ed-row');
  const row = rows[rows.length - 1];

  // Set text
  const textInput = await row.$('.ed-x');
  await textInput.fill('hello world');

  // Click plot
  const plotBtn = await row.$('.ed-plot');
  await plotBtn.click();

  // Plot layer should be visible
  await expect(page.locator('#plot-layer')).toBeVisible();

  // Click twice to place "hello" and "world"
  await page.mouse.click(100, 100);
  await page.mouse.click(200, 200);

  // Plot layer should hide
  await expect(page.locator('#plot-layer')).toBeHidden();

  // Dataset should be updated
  const customPos = await row.evaluate(node => node.dataset.customPos);
  const parsed = JSON.parse(customPos);
  expect(parsed.length).toBe(2);

  // Apply and verify
  await page.click('#edApply');

  // Need a bit of time to render
  await page.waitForTimeout(500);

});
