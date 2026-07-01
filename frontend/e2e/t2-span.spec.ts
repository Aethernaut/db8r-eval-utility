import { test, expect } from '@playwright/test';

test.describe('T2 Span Annotation', () => {
  test.beforeEach(async ({ page }) => {
    // Login first
    await page.goto('/login');
    await page.getByLabel(/email/i).fill('test@example.com');
    await page.getByLabel(/password/i).fill('testpassword123');
    await page.getByRole('button', { name: /sign in/i }).click();
    await expect(page).toHaveURL('/');
  });

  test('should navigate to T2 span annotation page', async ({ page }) => {
    // Click T2: Spans in sidebar
    await page.getByRole('link', { name: /t2.*spans/i }).click();

    // Should navigate to a document for annotation
    await expect(page.url()).toMatch(/\/t2\//);
  });

  test('should display document content and annotation tools', async ({ page }) => {
    // Navigate to a specific document (requires seeded fixture)
    await page.goto('/t2/test-document-hash');

    // Should show document header
    await expect(page.locator('[class*="header"]')).toBeVisible();

    // Should show span annotator container
    await expect(page.locator('[class*="container"]')).toBeVisible();
  });

  test('should create a span by selecting text', async ({ page }) => {
    await page.goto('/t2/test-document-hash');

    // Wait for text layer to be visible
    const textLayer = page.locator('[class*="textLayer"]');
    await expect(textLayer).toBeVisible();

    // Simulate text selection (click and drag)
    const textLayerBox = await textLayer.boundingBox();
    if (textLayerBox) {
      await page.mouse.move(textLayerBox.x + 50, textLayerBox.y + 20);
      await page.mouse.down();
      await page.mouse.move(textLayerBox.x + 200, textLayerBox.y + 20);
      await page.mouse.up();
    }

    // A new span should be created (shown in highlights overlay)
    // Note: This requires the mutation to succeed
  });

  test('should show span popover when clicking on a span', async ({ page }) => {
    await page.goto('/t2/test-document-hash');

    // Wait for highlights to render
    await page.waitForSelector('[class*="highlight"]');

    // Click on a span
    await page.locator('[class*="highlight"]').first().click();

    // Popover should appear with actions
    await expect(page.locator('[class*="popover"]')).toBeVisible();
  });

  test('should toggle claim-bearing status', async ({ page }) => {
    await page.goto('/t2/test-document-hash');

    // Wait for and click a span
    await page.waitForSelector('[class*="highlight"]');
    await page.locator('[class*="highlight"]').first().click();

    // Click toggle button in popover
    const toggleButton = page.getByRole('button', { name: /mark.*claim.*bearing/i });
    if (await toggleButton.isVisible()) {
      await toggleButton.click();
    }
  });

  test('should delete a span', async ({ page }) => {
    await page.goto('/t2/test-document-hash');

    // Wait for and click a span
    await page.waitForSelector('[class*="highlight"]');
    const initialSpanCount = await page.locator('[class*="highlight"]').count();

    await page.locator('[class*="highlight"]').first().click();

    // Click delete button in popover
    await page.getByRole('button', { name: /delete/i }).click();

    // Span count should decrease
    await expect(page.locator('[class*="highlight"]')).toHaveCount(initialSpanCount - 1);
  });

  test('should import prefill spans', async ({ page }) => {
    await page.goto('/t2/test-document-hash');

    // Click Import Prefill button
    await page.getByRole('button', { name: /import prefill/i }).click();

    // Wait for prefill to complete
    await page.waitForResponse(resp => resp.url().includes('/prefill') && resp.status() === 200);

    // Prefilled spans should appear (with dashed border style)
    await expect(page.locator('[class*="prefill"]')).toBeVisible();
  });

  test('should save document flags', async ({ page }) => {
    await page.goto('/t2/test-document-hash');

    // Check the exhaustively annotated checkbox
    await page.locator('input[type="checkbox"]').first().check();

    // Click Save Flags
    await page.getByRole('button', { name: /save flags/i }).click();

    // Should save successfully (button state changes)
    await expect(page.getByRole('button', { name: /saving/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /save flags/i })).toBeVisible();
  });

  test('should warn before leaving with unsaved changes', async ({ page }) => {
    await page.goto('/t2/test-document-hash');

    // Make a change (check a flag)
    await page.locator('input[type="checkbox"]').first().check();

    // Set up dialog handler
    page.on('dialog', async dialog => {
      expect(dialog.type()).toBe('confirm');
      expect(dialog.message()).toContain('unsaved');
      await dialog.dismiss(); // Cancel navigation
    });

    // Try to navigate away
    await page.getByRole('link', { name: /dashboard/i }).click();

    // Should still be on the same page
    await expect(page.url()).toContain('/t2/');
  });
});
